from decimal import Decimal
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
import json
from django.test import TestCase,override_settings,Client,RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import DigitalProduct,ProductOrder,InternationalProfile,StoreDiscount,StoreBundleItem,StoreGrant,StoreEntitlement
from .store_access import activate_grant,activate_order,has_access,credits,consume_workbook,snapshot,workbook_product
from .store_offers import quote,OfferError
from .product_payments import fulfill,InvalidProductCheckout
from ptjc_resumes.models import ResumeTemplate,ResumeDraft,ResumeAdPlacement

@override_settings(ALLOWED_HOSTS=['testserver'],EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',CAREER_TOOLS_PREVIEW=True,SECURE_SSL_REDIRECT=False)
class DigitalStoreReleaseTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('store-user',email='store@example.test',password='Local-Store-482!')
        InternationalProfile.objects.create(user=self.user,email_verified_at=timezone.now(),email_verified_address=self.user.email,country_of_education='Philippines',destination_province='British Columbia',application_history='new',registered_in_education_country='yes')
        self.resume=DigitalProduct.objects.create(title='Resume access',slug='resume-store-test',price_cad='20.00',is_published=True)
        self.template=ResumeTemplate.objects.get(key='international-professional');self.template.access_product=self.resume;self.template.is_enabled=True;self.template.save()
        self.workbook=workbook_product()
        self.bundle=DigitalProduct.objects.create(title='Starter bundle',slug='starter-test',kind='bundle',price_cad='25',is_published=True)
        StoreBundleItem.objects.create(bundle=self.bundle,product=self.resume)
        StoreBundleItem.objects.create(bundle=self.bundle,product=self.workbook,quantity=2)
        self.client.force_login(self.user)
    def order(self,product=None,amount=2500):
        p=product or self.bundle
        return ProductOrder.objects.create(user=self.user,product=p,stripe_session_id='cs_release_'+str(ProductOrder.objects.count()),amount_cents=amount,list_amount_cents=amount,checkout_snapshot=snapshot(p))
    def paid_session(self,order,**changes):
        d={'id':order.stripe_session_id,'payment_status':'paid','amount_total':order.amount_cents,'currency':'cad','metadata':{'mobility_user_id':str(order.user_id),'mobility_product_id':str(order.product_id),'mobility_amount_cents':str(order.amount_cents)}};d.update(changes);return d
    def test_percent_fixed_and_product_scopes(self):
        offer=StoreDiscount.objects.create(name='Half',code='half',kind='percent',value=50);offer.products.add(self.resume)
        self.assertEqual(quote(self.resume,self.user,'HALF')[:2],(2000,1000))
        with self.assertRaises(OfferError):quote(self.workbook,self.user,'half')
        offer.kind='fixed';offer.value=Decimal('3.25');offer.save();self.assertEqual(quote(self.resume,self.user,'half')[1],1675)
    def test_expired_offer_rejected_and_best_auto_offer_used(self):
        StoreDiscount.objects.create(name='old',code='old',kind='percent',value=10,ends_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(OfferError):quote(self.resume,self.user,'old')
        StoreDiscount.objects.create(name='ten',kind='percent',value=10)
        StoreDiscount.objects.create(name='five',kind='fixed',value=5)
        self.assertEqual(quote(self.resume,self.user)[1],1500)
    def test_discount_limits_include_pending_orders_until_expiry(self):
        offer=StoreDiscount.objects.create(name='one',code='one',kind='percent',value=20,max_uses=1)
        o=self.order();o.discount=offer;o.checkout_expires_at=timezone.now()+timedelta(minutes=35);o.save()
        with self.assertRaises(OfferError):quote(self.bundle,self.user,'one')
        o.checkout_expires_at=timezone.now()-timedelta(seconds=1);o.save();self.assertEqual(quote(self.bundle,self.user,'one')[1],2000)
    def test_per_account_limit_and_zero_price_validation(self):
        offer=StoreDiscount.objects.create(name='one each',code='one-each',kind='percent',value=100,max_uses_per_user=1)
        o=self.order();o.discount=offer;o.paid=True;o.save()
        with self.assertRaises(OfferError):quote(self.resume,self.user,'one-each')
        other=get_user_model().objects.create_user('other-store');self.assertEqual(quote(self.resume,other,'one-each')[1],0)
        offer.value=101
        with self.assertRaises(ValidationError):offer.full_clean()
    def test_bundle_fulfillment_is_idempotent_and_uses_purchase_snapshot(self):
        order=self.order();session=self.paid_session(order)
        StoreBundleItem.objects.filter(bundle=self.bundle,product=self.workbook).update(quantity=9)
        fulfill(session,expected_user=self.user.pk);fulfill(session,expected_user=self.user.pk)
        self.assertTrue(has_access(self.user,self.resume));self.assertEqual(credits(self.user,self.workbook),2)
        self.assertEqual(StoreEntitlement.objects.filter(order=order).count(),3)
    def test_wrong_amount_currency_account_and_metadata_never_activate(self):
        order=self.order()
        for changes in [{'amount_total':1},{'currency':'usd'},{'metadata':{'mobility_user_id':'999'}},{'payment_status':'no_payment_required','amount_total':2500}]:
            with self.assertRaises(InvalidProductCheckout):fulfill(self.paid_session(order,**changes))
        with self.assertRaises(InvalidProductCheckout):fulfill(self.paid_session(order),expected_user=999)
        self.assertFalse(StoreEntitlement.objects.filter(order=order).exists())
    def test_unpaid_session_does_not_activate(self):
        order=self.order();fulfill(self.paid_session(order,payment_status='unpaid'));self.assertFalse(StoreEntitlement.objects.exists())
    def test_gift_bundle_activates_once_and_revocation_removes_access(self):
        grant=StoreGrant.objects.create(user=self.user,product=self.bundle,reason='Complimentary starter bundle')
        activate_grant(grant);activate_grant(grant)
        self.assertTrue(has_access(self.user,self.resume));self.assertEqual(credits(self.user,self.workbook),2)
        grant.active=False;grant.save();self.assertFalse(has_access(self.user,self.resume));self.assertEqual(credits(self.user,self.workbook),0)
    def test_workbook_get_does_not_download_or_consume_credit(self):
        response=self.client.get(reverse('mobility_personalized_checklist'));self.assertEqual(response.status_code,200);self.assertNotEqual(response['Content-Type'],'application/pdf')
        response=self.client.post(reverse('mobility_personalized_checklist'));self.assertEqual(response.status_code,402)
        grant=StoreGrant.objects.create(user=self.user,product=self.workbook,reason='one');activate_grant(grant)
        self.client.get(reverse('mobility_personalized_checklist'));self.assertEqual(credits(self.user,self.workbook),1)
    def test_workbook_consumes_once_and_generation_failure_keeps_credit(self):
        grant=StoreGrant.objects.create(user=self.user,product=self.workbook,reason='one');activate_grant(grant)
        with self.assertRaises(RuntimeError):consume_workbook(self.user,self.workbook,lambda:(_ for _ in ()).throw(RuntimeError('PDF failed')))
        self.assertEqual(credits(self.user,self.workbook),1)
        self.assertEqual(consume_workbook(self.user,self.workbook,lambda:b'%PDF'),b'%PDF')
        self.assertIsNone(consume_workbook(self.user,self.workbook,lambda:b'%PDF'))
    def test_full_discount_code_unlocks_bundle(self):
        StoreDiscount.objects.create(name='Gift',code='GIFT',kind='percent',value=100)
        with patch('stripe.checkout.Session.create') as api:
            response=self.client.post(reverse('mobility_product_checkout',args=[self.bundle.pk]),{'discount_code':'gift'})
        self.assertEqual(response.status_code,200);api.assert_not_called();self.assertTrue(has_access(self.user,self.resume));self.assertEqual(credits(self.user,self.workbook),2)
        self.assertEqual(ProductOrder.objects.get(product=self.bundle).amount_cents,0)
    def test_paid_checkout_uses_discounted_snapshot_and_existing_account_key(self):
        from board.models import PaymentGatewayConfig
        PaymentGatewayConfig.objects.all().delete();PaymentGatewayConfig.objects.create(use_stripe=True,stripe_secret_key='sk_test_existing')
        StoreDiscount.objects.create(name='Half',code='HALF',kind='percent',value=50)
        with patch.dict('os.environ',{'PT_MOBILITY_STRIPE_SECRET_KEY':'','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_digital'}),patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_discounted',url='https://checkout.stripe.com/test')) as api:
            response=self.client.post(reverse('mobility_product_checkout',args=[self.resume.pk]),{'discount_code':'half'})
        self.assertEqual(response.status_code,302);self.assertEqual(api.call_args.kwargs['api_key'],'sk_test_existing');self.assertEqual(api.call_args.kwargs['line_items'][0]['price_data']['unit_amount'],1000)
        order=ProductOrder.objects.get(stripe_session_id='cs_discounted');self.assertEqual(order.discount_amount_cents,1000)
        self.assertFalse(has_access(self.user,self.resume));fulfill(self.paid_session(order));self.assertTrue(has_access(self.user,self.resume))
    def test_missing_webhook_fails_before_provider_call(self):
        with patch.dict('os.environ',{'PT_MOBILITY_STRIPE_WEBHOOK_SECRET':''}),patch('stripe.checkout.Session.create') as api:
            response=self.client.post(reverse('mobility_product_checkout',args=[self.resume.pk]))
        self.assertEqual(response.status_code,503);api.assert_not_called();self.assertFalse(ProductOrder.objects.exists())
    def test_pdf_purchase_does_not_require_a_finished_draft(self):
        self.assertFalse(ResumeDraft.objects.exists())
        with patch.dict('os.environ', {'PT_MOBILITY_STRIPE_SECRET_KEY':'sk_test_ready','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_ready'}), patch('stripe.checkout.Session.create', return_value=SimpleNamespace(id='cs_ready',url='https://checkout.stripe.com/ready')):
            self.assertEqual(self.client.post(reverse('mobility_product_checkout',args=[self.resume.pk])).status_code,302)
        order=ProductOrder.objects.get(stripe_session_id='cs_ready')
        fulfill(self.paid_session(order))
        self.assertTrue(has_access(self.user,self.resume))
    def test_gifted_resume_access_appears_in_library_and_works_after_editing(self):
        grant=StoreGrant.objects.create(user=self.user,product=self.resume,reason='promotion');activate_grant(grant)
        response=self.client.get(reverse('mobility_resource_library'));self.assertContains(response,'Open resume builder')
        from ptjc_resumes.views import owned
        self.assertTrue(owned(self.user,self.template))
    def test_unverified_profile_cannot_bypass_workbook_gate(self):
        profile=self.user.international_pt_profile;profile.email_verified_at=None;profile.save()
        self.assertRedirects(self.client.post(reverse('mobility_personalized_checklist')),reverse('mobility_verify_pending'),fetch_redirect_response=False)
    def test_signed_webhook_replay_and_expired_reservation(self):
        order=self.order();event={'type':'checkout.session.completed','data':{'object':self.paid_session(order)}}
        with patch.dict('os.environ',{'PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_test'}),patch('stripe.Webhook.construct_event',return_value=event):
            for _ in range(2):self.assertEqual(self.client.post(reverse('mobility_stripe_webhook'),data=b'{}',content_type='application/json').status_code,200)
        self.assertEqual(credits(self.user,self.workbook),2)
    def test_invalid_webhook_signature_does_not_activate(self):
        import stripe
        self.order()
        with patch.dict('os.environ',{'PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_test'}),patch('stripe.Webhook.construct_event',side_effect=stripe.error.SignatureVerificationError('bad','signature')):
            self.assertEqual(self.client.post(reverse('mobility_stripe_webhook'),data=b'{}',content_type='application/json').status_code,400)
        self.assertFalse(StoreEntitlement.objects.exists())

    def test_real_stripe_signature_validation_and_replay(self):
        import hmac,hashlib,time,os
        order=self.order();event={'id':'evt_signed_release','object':'event','type':'checkout.session.completed','data':{'object':self.paid_session(order)}}
        raw=json.dumps(event);stamp=str(int(time.time()));secret='whsec_release_only'
        digest=hmac.new(secret.encode(),(stamp+'.'+raw).encode(),hashlib.sha256).hexdigest()
        with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_WEBHOOK_SECRET':secret}):
            for _ in range(2):
                r=self.client.post(reverse('mobility_stripe_webhook'),raw,content_type='application/json',HTTP_STRIPE_SIGNATURE='t='+stamp+',v1='+digest)
                self.assertEqual(r.status_code,200)
            self.assertEqual(StoreEntitlement.objects.filter(order=order).count(),3)
            self.assertEqual(self.client.post(reverse('mobility_stripe_webhook'),raw,content_type='application/json',HTTP_STRIPE_SIGNATURE='t='+stamp+',v1=bad').status_code,400)

    def test_stale_session_retry_reuses_same_checkout_order(self):
        from .store_checkout import start
        requests=[]
        for n in range(2):
            request=RequestFactory().post('/checkout/');request.user=self.user;request.session={};requests.append(request)
        with patch.dict('os.environ',{'PT_MOBILITY_STRIPE_SECRET_KEY':'sk_test_retry','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_retry'}),patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_retry',url='https://checkout.stripe.com/retry')) as api:
            first=start(requests[0],self.resume);second=start(requests[1],self.resume)
        self.assertEqual(first[0].pk,second[0].pk)
        self.assertEqual(ProductOrder.objects.count(),1)
        self.assertEqual(api.call_args_list[0].kwargs['idempotency_key'],api.call_args_list[1].kwargs['idempotency_key'])

    def test_paid_checkout_records_visitor_country_once_across_retries(self):
        from .models import InternationalActivity
        with patch.dict('os.environ',{'PT_MOBILITY_STRIPE_SECRET_KEY':'sk_test_activity','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_activity'}),patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_activity',url='https://checkout.stripe.com/activity')),patch('career_mobility.geolocation.visitor_country',return_value='PH'):
            for _ in range(2):
                self.assertEqual(self.client.post(reverse('mobility_product_checkout',args=[self.resume.pk])).status_code,302)
        event=InternationalActivity.objects.get(event_key='checkout:cs_activity')
        self.assertEqual(event.action,'checkout_started');self.assertEqual(event.visitor_country,'PH')
        self.assertEqual(event.profile.user_id,self.user.pk)
        order=ProductOrder.objects.get(stripe_session_id='cs_activity')
        with self.captureOnCommitCallbacks(execute=True):fulfill(self.paid_session(order),site_base='https://example.test/')
        paid=InternationalActivity.objects.get(event_key='paid:'+str(order.pk))
        self.assertEqual(paid.visitor_country,'PH')

    def test_shop_missing_file_count_ignores_online_access_and_bundles(self):
        admin=get_user_model().objects.create_superuser('shop-audit','shop-audit@example.test','Local-Store-482!')
        self.client.force_login(admin)
        before=DigitalProduct.objects.filter(kind='file',download='').exclude(resumetemplate__is_enabled=True).exclude(slug='international-business-card-builder-access').count()
        response=self.client.get(reverse('ptjc_shop_admin'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['products_missing_files'],before)
        self.assertLess(before,DigitalProduct.objects.filter(download='').count())

    def test_admin_bundle_grant_activates_all_resources_immediately(self):
        admin=get_user_model().objects.create_superuser('gift-admin','gift-admin@example.test','Local-Store-482!')
        self.client.force_login(admin)
        response=self.client.post(reverse('admin:career_mobility_storegrant_add'),{'user':self.user.pk,'product':self.bundle.pk,'quantity':1,'reason':'Admin welcome bundle','active':'on','_save':'Save'})
        self.assertEqual(response.status_code,302)
        self.assertTrue(has_access(self.user,self.resume));self.assertEqual(credits(self.user,self.workbook),2)

    def test_failed_or_expired_checkout_releases_discount_reservation(self):
        from .store_offers import eligible
        offer=StoreDiscount.objects.create(name='One reserved use',code='RESERVED',kind='percent',value=50,max_uses=1)
        for event_type in ('checkout.session.expired','checkout.session.async_payment_failed'):
            order=self.order();order.discount=offer;order.checkout_expires_at=timezone.now()+timedelta(minutes=35);order.save()
            self.assertFalse(eligible(offer,self.bundle,self.user))
            event={'type':event_type,'data':{'object':{'id':order.stripe_session_id}}}
            with patch.dict('os.environ',{'PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_test'}),patch('stripe.Webhook.construct_event',return_value=event):
                self.assertEqual(self.client.post(reverse('mobility_stripe_webhook'),b'{}',content_type='application/json').status_code,200)
            self.assertTrue(eligible(offer,self.bundle,self.user));self.assertFalse(has_access(self.user,self.resume))

    def test_shop_reports_paid_sales_at_checkout_amount(self):
        admin=get_user_model().objects.create_superuser('sales-audit','sales-audit@example.test','Local-Store-482!')
        order=self.order();order.paid=True;order.save()
        self.resume.price_cad=99;self.resume.save()
        self.client.force_login(admin)
        response=self.client.get(reverse('ptjc_shop_admin'))
        self.assertEqual(response.context['revenue_estimate'],Decimal('25'))
        self.assertEqual(response.context['paid_orders'],1)
