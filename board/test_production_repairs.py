import hashlib
import hmac
import json
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from .models import Employer, Job, Invoice, JobSeeker, PaymentGatewayConfig, PostingPackage, PurchasedPackage
from .views import _available_credits, _consume_employer_credit
from .payments import fulfill_checkout, InvalidCheckout

@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', STRIPE_WEBHOOK_SECRET='whsec_test_only')
class ProductionRepairTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('clinic',email='clinic@example.test')
        self.employer=Employer.objects.create(user=self.user,company_name='Clinic',email=self.user.email,is_approved=True,credits=2)
        self.package=PostingPackage.objects.create(code='test',name='Package',credits=2,price_cents=9900)
        PaymentGatewayConfig.objects.create(use_stripe=True,stripe_public_key='pk_dummy',stripe_secret_key='sk_dummy',use_paypal=True,paypal_client_id='dummy',paypal_client_secret='dummy')
        self.client.force_login(self.user)
    def purchase(self, **kw):
        return PurchasedPackage.objects.create(employer=self.employer,package=self.package,**kw)
    def data(self, **kw):
        d={'title':'PT','description':'Provide patient assessment and treatment','job_type':'full_time','location':'Toronto, ON','relocation_assistance':'no','action':'publish'}
        d.update(kw);return d
    def session(self, **kw):
        Employer.objects.filter(pk=self.employer.pk).update(credits=0)
        d={'id':'cs_test_repair','payment_status':'paid','amount_total':9900,'currency':'cad','metadata':{'employer_id':str(self.employer.pk),'package_id':str(self.package.pk),'terms_version':'1','credits':'2','duration_days':'30','package_expires_days':'365','amount_cents':'9900'}}
        d.update(kw);return d
    def test_dashboard_preserves_legacy_balance(self):
        self.assertEqual(self.client.get('/employer/dashboard/').status_code,200)
        self.employer.refresh_from_db();self.assertEqual(self.employer.credits,2)
    def test_legacy_credit_consumed_and_not_erased(self):
        self.client.post('/jobs/new/',self.data())
        self.employer.refresh_from_db();self.assertEqual(self.employer.credits,1)
    def test_expired_package_does_not_use_cache(self):
        p=self.purchase(expires_at=timezone.now()-timedelta(days=1))
        self.assertEqual(_available_credits(self.employer),0)
        self.assertFalse(_consume_employer_credit(self.employer))
        p.refresh_from_db();self.assertEqual(p.credits_remaining,2)
    def test_failed_create_restores_credit(self):
        p=self.purchase()
        with patch('board.views.Job.save',side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):self.client.post('/jobs/new/',self.data())
        p.refresh_from_db();self.assertEqual(p.credits_remaining,2)
        self.assertFalse(Job.objects.exists())
    def test_failed_edit_restores_credit(self):
        p=self.purchase();j=Job.objects.create(employer=self.employer,title='Draft',is_active=False)
        with patch('board.views.Job.save',side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):self.client.post(f'/jobs/{j.pk}/edit/',self.data())
        p.refresh_from_db();self.assertEqual(p.credits_remaining,2)
        j.refresh_from_db();self.assertFalse(j.is_active)
    def test_failed_duplicate_restores_credit(self):
        p=self.purchase();j=Job.objects.create(employer=self.employer,title='Original')
        with patch('board.views.Job.save',side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):self.client.post(f'/jobs/{j.pk}/duplicate/',self.data())
        p.refresh_from_db();self.assertEqual(p.credits_remaining,2)
        self.assertEqual(Job.objects.count(),1)
    def test_exhausted_package_cannot_use_stale_cache(self):
        p=self.purchase();PurchasedPackage.objects.filter(pk=p.pk).update(credits_remaining=0)
        self.assertFalse(_consume_employer_credit(self.employer))
    def test_active_edit_does_not_recharge(self):
        p=self.purchase();j=Job.objects.create(employer=self.employer,title='Live')
        self.client.post(f'/jobs/{j.pk}/edit/',self.data())
        p.refresh_from_db();self.assertEqual(p.credits_remaining,2)
    def test_republish_resets_expiration_notification(self):
        self.purchase();j=Job.objects.create(employer=self.employer,title='Old',is_active=False,expiry_email_sent=True)
        self.client.post(f'/jobs/{j.pk}/edit/',self.data())
        j.refresh_from_db();self.assertTrue(j.is_active);self.assertFalse(j.expiry_email_sent)
    def test_draft_private_but_owner_can_preview(self):
        j=Job.objects.create(employer=self.employer,title='Private draft',is_active=False)
        self.assertEqual(self.client.get(f'/jobs/{j.pk}/').status_code,200)
        self.client.logout();self.assertEqual(self.client.get(f'/jobs/{j.pk}/').status_code,404)
    def test_other_employer_cannot_preview_draft(self):
        j=Job.objects.create(employer=self.employer,title='Private draft',is_active=False)
        other=get_user_model().objects.create_user('other');self.client.force_login(other)
        self.assertEqual(self.client.get(f'/jobs/{j.pk}/').status_code,404)
    def test_expired_unpublished_draft_stays_private(self):
        j=Job.objects.create(employer=self.employer,title='Private',is_active=False,expiry_date=timezone.localdate()-timedelta(days=1))
        self.client.logout();self.assertEqual(self.client.get(f'/jobs/{j.pk}/').status_code,404)
    def test_previously_published_expired_page_still_readable(self):
        j=Job.objects.create(employer=self.employer,title='Expired',expiry_date=timezone.localdate()-timedelta(days=1))
        self.client.logout();self.assertEqual(self.client.get(f'/jobs/{j.pk}/').status_code,200)
    def test_invalid_resume_id_is_validation_error(self):
        u=get_user_model().objects.create_user('candidate');JobSeeker.objects.create(user=u,is_approved=True)
        self.client.force_login(u);j=Job.objects.create(employer=self.employer,title='PT')
        for value in ['not-a-number','9'*100,'-1']:
            self.assertContains(self.client.post(f'/jobs/{j.pk}/apply/',{'resume_id':value}), 'Please select a resume')
    def test_retired_paid_package_fulfills(self):
        self.package.is_active=False;self.package.save()
        invoice,pkg,created=fulfill_checkout(self.session())
        self.assertTrue(created);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,2)
    def test_snapshot_survives_package_changes(self):
        self.package.credits=10;self.package.duration_days=99;self.package.package_expires_days=1;self.package.save()
        fulfill_checkout(self.session());p=PurchasedPackage.objects.get()
        self.assertEqual(p.credits_granted,2);self.assertEqual(p.duration_days,30)
        self.assertGreater(p.expires_at,timezone.now()+timedelta(days=364))
    def test_zero_amount_is_not_replaced_by_list_price(self):
        s=self.session(amount_total=0);s['metadata']['amount_cents']='0'
        fulfill_checkout(s);self.assertEqual(Invoice.objects.get().amount,0)
    def test_wrong_amount_or_currency_rolls_back(self):
        for s in [self.session(amount_total=1),self.session(currency='usd')]:
            with self.assertRaises(InvalidCheckout):fulfill_checkout(s)
        self.assertFalse(Invoice.objects.exists())
    def test_browser_and_webhook_fulfill_only_once(self):
        s=self.session();fulfill_checkout(s)
        with patch('stripe.checkout.Session.retrieve',return_value=SimpleNamespace(**s)):
            self.assertEqual(self.client.get('/checkout/success/?session_id='+s['id']).status_code,200)
        self.assertEqual(Invoice.objects.count(),1);self.assertEqual(PurchasedPackage.objects.count(),1)
    def signed_event(self, obj, kind='checkout.session.completed'):
        payload=json.dumps({'id':'evt_test','type':kind,'data':{'object':obj}}).encode()
        timestamp=str(int(time.time()))
        sig=hmac.new(b'whsec_test_only',timestamp.encode()+b'.'+payload,hashlib.sha256).hexdigest()
        return Client(enforce_csrf_checks=True).post('/stripe/webhook/',payload,content_type='application/json',HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={sig}')
    def test_real_signature_webhook_without_login_fulfills_once(self):
        with patch('board.views.send_templated_email') as send, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.signed_event(self.session()).status_code,200)
            self.assertEqual(self.signed_event(self.session()).status_code,200)
        self.assertEqual(PurchasedPackage.objects.count(),1);self.assertEqual(send.call_count,2)
    def test_invalid_signature_never_grants_credit(self):
        r=Client(enforce_csrf_checks=True).post('/stripe/webhook/',b'{}',content_type='application/json',HTTP_STRIPE_SIGNATURE='invalid')
        self.assertEqual(r.status_code,400);self.assertFalse(Invoice.objects.exists())
    def test_unpaid_or_unrelated_webhook_ignored(self):
        self.assertEqual(self.signed_event(self.session(payment_status='unpaid')).status_code,200)
        self.assertEqual(self.signed_event({'id':'cs_other','payment_status':'paid','metadata':{}}).status_code,200)
        self.assertFalse(Invoice.objects.exists())
    def test_webhook_allocation_failure_rolls_back_for_retry(self):
        with patch('board.payments.PurchasedPackage.objects.create',side_effect=RuntimeError('failed')):
            self.assertEqual(self.signed_event(self.session()).status_code,500)
        self.assertFalse(Invoice.objects.exists());self.assertEqual(self.signed_event(self.session()).status_code,200)
    def test_paypal_hidden_and_forged_success_rejected(self):
        self.assertNotContains(self.client.get(f'/packages/{self.package.pk}/buy/select/'),'pm_paypal')
        r=self.client.post(f'/checkout/start/{self.package.pk}/',{'payment_method':'paypal'})
        self.assertEqual(r.status_code,302)
        r=self.client.get('/checkout/paypal/success/')
        self.assertEqual(r.status_code,302);self.assertFalse(Invoice.objects.exists())
    def test_invoice_renders_dollars(self):
        invoice=Invoice.objects.create(employer=self.employer,amount=9900)
        self.assertContains(self.client.get(f'/invoices/{invoice.pk}/'),'$99.00')
    def test_checkout_snapshots_terms(self):
        with patch('stripe.checkout.Session.create',return_value=SimpleNamespace(url='https://checkout.stripe.com/test')) as create:
            self.client.post(f'/checkout/start/{self.package.pk}/',{'payment_method':'card'})
        self.assertEqual(create.call_args.kwargs['metadata']['credits'],'2')
    def test_first_purchase_keeps_legacy_credits(self):
        s=self.session();Employer.objects.filter(pk=self.employer.pk).update(credits=3)
        fulfill_checkout(s)
        self.employer.refresh_from_db();self.assertEqual(self.employer.credits,5)
        self.assertEqual(PurchasedPackage.objects.get(source='legacy').expires_at,None)
    def test_browser_first_webhook_second_fulfills_once(self):
        s=self.session()
        with patch('stripe.checkout.Session.retrieve',return_value=SimpleNamespace(**s)):
            self.client.get('/checkout/success/?session_id='+s['id'])
        self.assertEqual(self.signed_event(s).status_code,200)
        self.assertEqual(PurchasedPackage.objects.count(),1)
    def test_existing_expiry_stays_iso_on_edit(self):
        expiry=timezone.localdate()+timedelta(days=10)
        j=Job.objects.create(employer=self.employer,title='PT',expiry_date=expiry)
        self.assertContains(self.client.get(f'/jobs/{j.pk}/edit/'),f'value="{expiry.isoformat()}"')
    def test_other_candidates_resume_rejected(self):
        from .models import Resume
        u=get_user_model().objects.create_user('candidate');js=JobSeeker.objects.create(user=u,is_approved=True)
        other=get_user_model().objects.create_user('othercandidate');otherjs=JobSeeker.objects.create(user=other,is_approved=True)
        resume=Resume.objects.create(jobseeker=otherjs,file='private.pdf')
        self.client.force_login(u);j=Job.objects.create(employer=self.employer,title='PT')
        self.assertContains(self.client.post(f'/jobs/{j.pk}/apply/',{'resume_id':resume.pk}), 'Please select a resume')
