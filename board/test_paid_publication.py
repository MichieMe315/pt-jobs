from datetime import timedelta
from types import SimpleNamespace
from io import StringIO
from unittest.mock import patch
import uuid
from django.test import TestCase,Client,override_settings
from django.contrib.auth import get_user_model
from django.core.management import call_command,CommandError
from django.urls import reverse
from django.utils import timezone
from .models import Employer,Job,PostingPackage,PurchasedPackage,Invoice,PaymentGatewayConfig,JobPublicationRequest
from .publication import request_publication,checkout_idempotency_key
from .payments import fulfill_checkout

@override_settings(ALLOWED_HOSTS=['testserver'],EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',STRIPE_WEBHOOK_SECRET='whsec_test_only')
class PaidPublicationTests(TestCase):
 def setUp(self):
  self.user=get_user_model().objects.create_user('posting-clinic',email='posting@example.test')
  self.e=Employer.objects.create(user=self.user,company_name='Posting Clinic',email=self.user.email,is_approved=True,credits=0)
  self.p=PostingPackage.objects.create(code='paid-posting',name='30 day posting',credits=1,price_cents=7500,duration_days=30)
  PaymentGatewayConfig.objects.create(use_stripe=True,stripe_public_key='pk_test',stripe_secret_key='sk_test')
  self.client.force_login(self.user)
 def data(self,**changes):
  d={'title':'Physiotherapist','description':'Assessment and treatment in our clinic.','job_type':'full_time','location':'Okotoks, AB','relocation_assistance':'no','action':'publish'};d.update(changes);return d
 def draft(self):
  r=self.client.post(reverse('job_create'),self.data());self.assertEqual(r.status_code,302)
  job=Job.objects.get();intent=JobPublicationRequest.objects.get(job=job,status='waiting');return job,intent
 def session(self,intent=None,**changes):
  s={'id':'cs_paid_publication','payment_status':'paid','currency':'cad','amount_total':7500,'metadata':{'employer_id':str(self.e.pk),'package_id':str(self.p.pk),'credits':'1','duration_days':'30','package_expires_days':'365','amount_cents':'7500','terms_version':'1'}}
  if intent:s['metadata'].update(publication_request_id=str(intent.pk),publish_after_payment='1')
  s.update(changes);return s
 def webhook(self,session):
  event={'type':'checkout.session.completed','data':{'object':session}}
  with patch('stripe.Webhook.construct_event',return_value=event):return self.client.post(reverse('stripe_webhook'),b'{}',content_type='application/json',HTTP_STRIPE_SIGNATURE='test')
 def test_publish_without_credit_creates_durable_request(self):
  job,intent=self.draft();self.assertFalse(job.is_active);self.assertEqual(intent.employer,self.e)
 def test_both_stripe_entry_points_include_publication_metadata(self):
  job,intent=self.draft()
  for path in (reverse('checkout_start',args=[self.p.pk]),reverse('stripe_create_session',args=[self.p.pk])):
   with patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_start',url='https://checkout.stripe.com/test')) as create:r=self.client.post(path,{'payment_method':'card'})
   self.assertIn(r.status_code,(200,302));self.assertEqual(create.call_args.kwargs['metadata']['publication_request_id'],str(intent.pk));self.assertTrue(create.call_args.kwargs['idempotency_key'].startswith('ptjc-posting-'));self.assertEqual(create.call_args.kwargs['metadata']['publish_after_payment'],'1')
 def test_checkout_selection_survives_missing_browser_keys(self):
  job,intent=self.draft();s=self.client.session
  for key in ('pending_create_job_id','pending_publish_job_id','pending_duplicate_job_id'):s.pop(key,None)
  s.save();r=self.client.get(reverse('checkout_select',args=[self.p.pk]));self.assertContains(r,job.title);self.assertEqual(r.context['publication'],intent)
 def test_webhook_publishes_only_linked_job_without_browser_return(self):
  job,intent=self.draft();old=Job.objects.create(employer=self.e,title='Old Access post',is_active=False)
  self.client.logout();r=self.webhook(self.session(intent));self.assertEqual(r.status_code,200)
  job.refresh_from_db();intent.refresh_from_db();old.refresh_from_db();self.e.refresh_from_db()
  self.assertTrue(job.is_active);self.assertFalse(old.is_active);self.assertEqual(intent.status,'published');self.assertEqual(self.e.credits,0)
  self.assertEqual(PurchasedPackage.objects.get().credits_remaining,0);self.assertEqual(job.expiry_date,timezone.localdate()+timedelta(days=29))
 def test_browser_return_publishes_linked_job_and_shows_confirmation(self):
  job,intent=self.draft()
  with patch('stripe.checkout.Session.retrieve',return_value=SimpleNamespace(**self.session(intent))):r=self.client.get('/checkout/success/?session_id=cs_paid_publication')
  job.refresh_from_db();self.assertTrue(job.is_active);self.assertContains(r,'Your job is published');self.assertContains(r,reverse('job_detail',args=[job.pk]))
 def test_repeated_webhook_and_return_publish_once_and_consume_one_credit(self):
  job,intent=self.draft();s=self.session(intent)
  with patch('board.publication.notify_publication') as notice,patch('board.payments.notify_order'):
   with self.captureOnCommitCallbacks(execute=True):self.webhook(s)
   with self.captureOnCommitCallbacks(execute=True):self.webhook(s)
   with patch('stripe.checkout.Session.retrieve',return_value=SimpleNamespace(**s)):
    with self.captureOnCommitCallbacks(execute=True):self.client.get('/checkout/success/?session_id='+s['id'])
   self.assertEqual(notice.call_count,1)
  job.refresh_from_db();self.assertTrue(job.is_active);self.assertEqual(Invoice.objects.count(),1);self.assertEqual(PurchasedPackage.objects.count(),1);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,0)
 def test_second_distinct_payment_never_republishes_same_job(self):
  job,intent=self.draft();self.webhook(self.session(intent));self.webhook(self.session(intent,id='cs_second_real_payment'))
  self.assertEqual(Invoice.objects.count(),2);self.assertEqual(sum(PurchasedPackage.objects.values_list('credits_remaining',flat=True)),1);self.assertEqual(JobPublicationRequest.objects.filter(status='published').count(),1)
 def test_save_draft_cancels_pending_publication(self):
  job,intent=self.draft();self.client.post(reverse('job_edit',args=[job.pk]),self.data(action='draft'));self.webhook(self.session(intent));job.refresh_from_db();intent.refresh_from_db();self.assertFalse(job.is_active);self.assertEqual(intent.status,'cancelled');self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)
 def test_changed_content_preserves_credit_and_requires_review(self):
  job,intent=self.draft();Job.objects.filter(pk=job.pk).update(description='A changed position requiring review.');self.webhook(self.session(intent));job.refresh_from_db();intent.refresh_from_db();self.assertFalse(job.is_active);self.assertEqual(intent.status,'review');self.assertIn('changed',intent.last_error);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)
 def test_unapproved_employer_not_published_but_payment_is_honoured(self):
  job,intent=self.draft();Employer.objects.filter(pk=self.e.pk).update(is_approved=False);self.webhook(self.session(intent));intent.refresh_from_db();job.refresh_from_db();self.assertFalse(job.is_active);self.assertEqual(intent.status,'review');self.assertEqual(Invoice.objects.count(),1);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)
 def test_invalid_saved_content_requires_review_without_spending(self):
  job=Job.objects.create(employer=self.e,title='',description='',is_active=False);intent=request_publication(job);self.webhook(self.session(intent));intent.refresh_from_db();self.assertEqual(intent.status,'review');self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)
 def test_foreign_job_cannot_be_selected_for_checkout(self):
  u=get_user_model().objects.create_user('other-clinic');e=Employer.objects.create(user=u,is_approved=True);job=Job.objects.create(employer=e,title='Not yours',is_active=False)
  with patch('stripe.checkout.Session.create') as create:r=self.client.post(reverse('checkout_start',args=[self.p.pk]),{'publish_job_id':job.pk})
  self.assertEqual(r.status_code,302);create.assert_not_called();self.assertFalse(JobPublicationRequest.objects.exists())
 def test_foreign_publication_metadata_never_publishes_foreign_job(self):
  u=get_user_model().objects.create_user('other-clinic');e=Employer.objects.create(user=u,is_approved=True);j=Job.objects.create(employer=e,title='Other',is_active=False);intent=request_publication(j)
  self.webhook(self.session(intent));j.refresh_from_db();self.assertFalse(j.is_active);self.assertEqual(PurchasedPackage.objects.get().employer,self.e);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)
 def test_old_job_not_published_by_unlinked_package_purchase(self):
  old=Job.objects.create(employer=self.e,title='2025 advert',description='Old advert',is_active=False,posting_date=timezone.localdate()-timedelta(days=500));self.webhook(self.session());old.refresh_from_db();self.assertFalse(old.is_active);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)
 def test_package_first_success_has_create_job_and_saved_job_next_steps(self):
  with patch('stripe.checkout.Session.retrieve',return_value=SimpleNamespace(**self.session())):r=self.client.get('/checkout/success/?session_id=cs_paid_publication')
  self.assertContains(r,'Create a job posting');self.assertContains(r,'No job was published');self.assertFalse(Job.objects.exists());self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)
 def test_old_paid_return_finds_saved_job_without_session_keys(self):
  job=Job.objects.create(employer=self.e,title='Saved Access position',is_active=False)
  with patch('stripe.checkout.Session.retrieve',return_value=SimpleNamespace(**self.session())):r=self.client.get('/checkout/success/?session_id=cs_paid_publication')
  self.assertContains(r,job.title);self.assertContains(r,'Review and publish');self.assertContains(self.client.get(reverse('employer_dashboard')),'Saved Access position')
 def test_direct_publish_existing_paid_credit_resets_old_expiry(self):
  fulfill_checkout(self.session());job=Job.objects.create(employer=self.e,title='Saved',description='Patient assessment and treatment.',location='Okotoks',is_active=False,posting_date=timezone.localdate()-timedelta(days=21),expiry_date=timezone.localdate()+timedelta(days=5))
  r=self.client.post(reverse('job_edit',args=[job.pk]),self.data());self.assertEqual(r.status_code,302);job.refresh_from_db();self.assertTrue(job.is_active);self.assertEqual(job.expiry_date,timezone.localdate()+timedelta(days=29));self.assertEqual(PurchasedPackage.objects.get().credits_remaining,0)
 def test_unused_credit_prevents_second_payment_for_selected_job(self):
  job,intent=self.draft();fulfill_checkout(self.session())
  with patch('stripe.checkout.Session.create') as create:r=self.client.post(reverse('checkout_start',args=[self.p.pk]),{'publish_job_id':job.pk})
  self.assertEqual(r.status_code,302);create.assert_not_called();self.assertIn('/edit/',r.url)
 def test_double_checkout_reuses_intent_and_stripe_idempotency_key(self):
  job,intent=self.draft();keys=[];ids=[]
  for _ in range(2):
   with patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_same',url='https://checkout.stripe.com/test')) as create:self.client.post(reverse('checkout_start',args=[self.p.pk]),{'publish_job_id':job.pk})
   keys.append(create.call_args.kwargs['idempotency_key']);ids.append(create.call_args.kwargs['metadata']['publication_request_id'])
  self.assertEqual(keys[0],keys[1]);self.assertEqual(ids[0],ids[1]);self.assertEqual(ids[0],str(intent.pk))
 def test_credit_only_repeated_checkout_has_stable_key_until_payment_returns(self):
  keys=[]
  for _ in range(2):
   with patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_credit_only',url='https://checkout.stripe.com/test')) as create:self.client.post(reverse('checkout_start',args=[self.p.pk]),{'publish_job_id':''})
   keys.append(create.call_args.kwargs['idempotency_key'])
  self.assertEqual(keys[0],keys[1])
 def test_snapshot_duration_survives_package_edit(self):
  job,intent=self.draft();PostingPackage.objects.filter(pk=self.p.pk).update(duration_days=90,is_active=False);s=self.session(intent);s['metadata']['duration_days']='60';self.webhook(s);job.refresh_from_db();self.assertTrue(job.is_active);self.assertEqual(job.expiry_date,timezone.localdate()+timedelta(days=59))
 def test_checkout_publish_request_is_csrf_protected(self):
  browser=Client(enforce_csrf_checks=True);browser.force_login(self.user);self.assertEqual(browser.post(reverse('checkout_start',args=[self.p.pk]),{}).status_code,403)
 def test_paid_unposted_report_permission_and_content(self):
  fulfill_checkout(self.session());staff=get_user_model().objects.create_superuser('monitor','monitor@example.test','Test-only-421!');self.client.force_login(staff)
  self.assertContains(self.client.get(reverse('paid_postings_report')),self.e.company_name)
  self.client.force_login(self.user);self.assertEqual(self.client.get(reverse('paid_postings_report')).status_code,302)
 def test_active_long_posting_edit_does_not_truncate_paid_duration(self):
  job=Job.objects.create(employer=self.e,title='Long paid job',description='Assessment and treatment.',location='Calgary',is_active=True,posting_date=timezone.localdate()-timedelta(days=1),expiry_date=timezone.localdate()+timedelta(days=58))
  r=self.client.post(reverse('job_edit',args=[job.pk]),self.data(expiry_date=job.expiry_date.isoformat()));self.assertEqual(r.status_code,302);job.refresh_from_db();self.assertEqual(job.expiry_date,timezone.localdate()+timedelta(days=58));self.assertFalse(PurchasedPackage.objects.exists())
 def test_missing_signing_secret_fails_read_only_readiness_check(self):
  with self.settings(STRIPE_WEBHOOK_SECRET=''):
   with self.assertRaises(CommandError):call_command('check_posting_readiness',stdout=StringIO())
  self.assertFalse(Invoice.objects.exists())
 def test_readiness_verifies_stripe_url_and_completed_event(self):
  endpoint={'status':'enabled','url':'https://physiotherapyjobscanada.ca/stripe/webhook/','enabled_events':['checkout.session.completed']}
  with patch('stripe.WebhookEndpoint.list') as listed:
   listed.return_value.auto_paging_iter.return_value=iter([endpoint]);out=StringIO();call_command('check_posting_readiness',verify_stripe=True,stdout=out)
  self.assertIn('registered and enabled',out.getvalue());self.assertFalse(Invoice.objects.exists())
 def test_readiness_rejects_other_sites_webhooks(self):
  with patch('stripe.WebhookEndpoint.list') as listed:
   listed.return_value.auto_paging_iter.return_value=iter([{'status':'enabled','url':'https://another-site.example/stripe/webhook/','enabled_events':['*']}])
   with self.assertRaises(CommandError):call_command('check_posting_readiness',verify_stripe=True,stdout=StringIO())
 def test_failed_receipt_link_is_retryable_without_duplicate_payment(self):
  job,intent=self.draft();s=self.session(intent)
  with patch('board.publication.JobPublicationRequest.save',side_effect=RuntimeError('simulated write failure')):
   with self.captureOnCommitCallbacks(execute=True):r=self.webhook(s)
  self.assertEqual(r.status_code,500);self.assertFalse(Invoice.objects.exists());self.assertFalse(PurchasedPackage.objects.exists())
  self.assertEqual(self.webhook(s).status_code,200);job.refresh_from_db();self.assertTrue(job.is_active);self.assertEqual(Invoice.objects.count(),1)
 def test_direct_publish_honours_long_credit_duration(self):
  PurchasedPackage.objects.create(employer=self.e,package=self.p,duration_days=60)
  r=self.client.post(reverse('job_create'),self.data());self.assertEqual(r.status_code,302);self.assertEqual(Job.objects.get().expiry_date,timezone.localdate()+timedelta(days=59))
 def test_empty_optional_posting_choice_never_uses_another_pending_job(self):
  job,intent=self.draft()
  with patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_credit_intent',url='https://checkout.stripe.com/test')) as create:self.client.post(reverse('checkout_start',args=[self.p.pk]),{'publish_job_id':''})
  self.assertEqual(create.call_args.kwargs['metadata']['publication_request_id'],'')

 def test_final_publish_requires_csrf(self):
  job,intent=self.draft();self.webhook(self.session());browser=Client(enforce_csrf_checks=True);browser.force_login(self.user)
  self.assertEqual(browser.post(reverse('job_edit',args=[job.pk]),self.data()).status_code,403)
  job.refresh_from_db();self.assertFalse(job.is_active);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)

 def test_missing_publish_action_cannot_activate_saved_job(self):
  job,intent=self.draft();self.webhook(self.session());data=self.data();data.pop('action')
  self.client.post(reverse('job_edit',args=[job.pk]),data)
  job.refresh_from_db();self.assertFalse(job.is_active);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)

 def test_old_checkout_without_new_instruction_never_publishes(self):
  job,intent=self.draft();s=self.session(intent);s['metadata'].pop('publish_after_payment')
  self.webhook(s);job.refresh_from_db();self.assertFalse(job.is_active);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)
 def test_previously_paid_request_never_retroactively_publishes(self):
  job,intent=self.draft();intent.status='ready';intent.save();self.webhook(self.session(intent))
  job.refresh_from_db();self.assertFalse(job.is_active);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,1)
 def test_publication_failure_rolls_back_payment_and_credit_for_retry(self):
  job,intent=self.draft();s=self.session(intent)
  with patch('board.publication.Job.save',side_effect=RuntimeError('simulated publication failure')):self.assertEqual(self.webhook(s).status_code,500)
  job.refresh_from_db();self.assertFalse(job.is_active);self.assertFalse(Invoice.objects.exists());self.assertFalse(PurchasedPackage.objects.exists())
  self.assertEqual(self.webhook(s).status_code,200);job.refresh_from_db();self.assertTrue(job.is_active)

 def test_existing_draft_checkout_publishes_only_selected_job(self):
  job=Job.objects.create(employer=self.e,title='Saved role',description='Assessment and treatment.',location='Calgary',is_active=False)
  self.client.post(reverse('job_edit',args=[job.pk]),self.data())
  intent=JobPublicationRequest.objects.get(job=job);self.webhook(self.session(intent))
  job.refresh_from_db();self.assertTrue(job.is_active);self.assertEqual(PurchasedPackage.objects.get().credits_remaining,0)
 def test_cancelled_checkout_does_not_publish_or_create_credit(self):
  job,intent=self.draft();self.client.get(reverse('checkout_select',args=[self.p.pk])+'?publication='+str(intent.pk))
  job.refresh_from_db();self.assertFalse(job.is_active);self.assertFalse(Invoice.objects.exists());self.assertFalse(PurchasedPackage.objects.exists())
 def test_unpaid_session_cannot_publish(self):
  job,intent=self.draft();s=self.session(intent,payment_status='unpaid')
  from .payments import InvalidCheckout
  with self.assertRaises(InvalidCheckout):fulfill_checkout(s)
  job.refresh_from_db();self.assertFalse(job.is_active);self.assertFalse(Invoice.objects.exists())
