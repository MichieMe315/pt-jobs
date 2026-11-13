"""Checkout regression cases: old snapshot versions, delayed payments and retries."""
import hashlib,hmac,json,os,time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings,RequestFactory
from django.urls import reverse
from django.utils import timezone
from career_mobility.models import ProductOrder,InternationalProfile,StoreDiscount,StoreEntitlement
from career_mobility.store_access import workbook_product,snapshot,credits
from career_mobility.store_offers import eligible
from career_mobility.store_checkout import start

@override_settings(ALLOWED_HOSTS=['testserver'],EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',CAREER_TOOLS_PREVIEW=True,SECURE_SSL_REDIRECT=False)
class CheckoutCompletionTests(TestCase):
 def setUp(self):
  self.user=get_user_model().objects.create_user('payment-completion',email='completion@example.test')
  InternationalProfile.objects.create(user=self.user,country_of_education='India',email_verified_at=timezone.now(),email_verified_address=self.user.email)
  self.product=workbook_product();self.client.force_login(self.user)
  self.order=ProductOrder.objects.create(user=self.user,product=self.product,stripe_session_id='cs_completion',amount_cents=199,checkout_snapshot=snapshot(self.product),checkout_expires_at=timezone.now()+timedelta(minutes=35))
 def session(self,**changes):
  result={'id':self.order.stripe_session_id,'status':'complete','payment_status':'paid','amount_total':199,'currency':'cad','metadata':{'mobility_product_id':str(self.product.pk),'mobility_user_id':str(self.user.pk),'mobility_amount_cents':'199'}};result.update(changes);return result
 def event(self,kind,obj):
  raw=json.dumps({'id':'evt_completion','object':'event','type':kind,'data':{'object':obj}});stamp=str(int(time.time()));secret='whsec_completion';sig=hmac.new(secret.encode(),(stamp+'.'+raw).encode(),hashlib.sha256).hexdigest()
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_WEBHOOK_SECRET':secret}):return self.client.post(reverse('mobility_stripe_webhook'),raw,content_type='application/json',HTTP_STRIPE_SIGNATURE='t='+stamp+',v1='+sig)
 @override_settings(ROOT_URLCONF='career_mobility.test_release_routes',CAREER_TOOLS_PREVIEW=False,INTERNATIONAL_PLANNER_ENABLED=False)
 def test_signed_payment_fulfills_while_new_checkout_is_hidden(self):
  self.client.logout()
  self.assertEqual(self.client.get('/career-resources/shop/').status_code,200)
  self.assertEqual(self.client.post(f'/career-resources/international/product/{self.product.pk}/checkout/').status_code,404)
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_WEBHOOK_SECRET':''}):
   self.assertEqual(self.client.post(reverse('mobility_stripe_webhook'),data='{}',content_type='application/json').status_code,503)
  with self.captureOnCommitCallbacks(execute=True):
   for _ in range(2):self.assertEqual(self.event('checkout.session.completed',self.session()).status_code,200)
  self.assertEqual(credits(self.user,self.product),1)
 def test_old_snapshot_retrieves_current_checkout_before_activation(self):
  old={'id':self.order.stripe_session_id,'metadata':{'mobility_product_id':str(self.product.pk)}}
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'sk_test_completion'}),patch('stripe.checkout.Session.retrieve',return_value=self.session()) as fetch:
   self.assertEqual(self.event('checkout.session.completed',old).status_code,200)
  self.assertEqual(fetch.call_args.args[0],self.order.stripe_session_id);self.assertEqual(credits(self.user,self.product),1)
 def test_unreadable_legacy_snapshot_returns_retry_not_false_success(self):
  with patch('career_mobility.store_config.stripe_key',return_value=''),patch('stripe.checkout.Session.retrieve') as fetch:
   self.assertEqual(self.event('checkout.session.completed',{'id':self.order.stripe_session_id}).status_code,503)
  fetch.assert_not_called();self.assertFalse(StoreEntitlement.objects.exists())
 def test_delayed_payment_keeps_offer_reserved_and_does_not_charge_again(self):
  offer=StoreDiscount.objects.create(name='Limited',code='LIMITED',kind='percent',value=10,max_uses=1)
  self.order.discount=offer;self.order.save()
  self.assertEqual(self.event('checkout.session.completed',self.session(payment_status='unpaid')).status_code,200)
  self.order.refresh_from_db();self.assertEqual(self.order.checkout_state,'processing');self.assertIsNone(self.order.checkout_expires_at);self.assertFalse(eligible(offer,self.product,self.user))
  request=RequestFactory().post('/checkout/');request.user=self.user;request.session={}
  with patch('stripe.checkout.Session.create') as create:
   order,url=start(request,self.product,'ANOTHER-CODE')
  create.assert_not_called();self.assertEqual(order.pk,self.order.pk);self.assertIn(self.order.stripe_session_id,url);self.assertEqual(credits(self.user,self.product),0)
  for _ in range(2):self.assertEqual(self.event('checkout.session.async_payment_succeeded',self.session()).status_code,200)
  self.assertEqual(credits(self.user,self.product),1)
 def test_failure_releases_reservation_and_late_unpaid_event_cannot_restore_it(self):
  offer=StoreDiscount.objects.create(name='Limited',code='FAIL-LIMIT',kind='percent',value=10,max_uses=1);self.order.discount=offer;self.order.save()
  self.event('checkout.session.completed',self.session(payment_status='unpaid'))
  self.event('checkout.session.async_payment_failed',{'id':self.order.stripe_session_id})
  self.event('checkout.session.completed',self.session(payment_status='unpaid'))
  self.order.refresh_from_db();self.assertEqual(self.order.checkout_state,'failed');self.assertTrue(eligible(offer,self.product,self.user));self.assertEqual(credits(self.user,self.product),0)
 def test_late_expiry_cannot_release_processing_payment(self):
  self.event('checkout.session.completed',self.session(payment_status='unpaid'))
  self.event('checkout.session.expired',{'id':self.order.stripe_session_id})
  self.order.refresh_from_db();self.assertEqual(self.order.checkout_state,'processing')
 def test_product_rename_cannot_change_retry_payload(self):
  self.order.delete();requests=[]
  for _ in range(2):
   request=RequestFactory().post('/checkout/');request.user=self.user;request.session={};requests.append(request)
  old=self.product.title
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'sk_test_completion','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_completion'}),patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_rename',url='https://checkout.stripe.com/rename')) as create:
   start(requests[0],self.product);self.product.title='Renamed workbook';self.product.save();start(requests[1],self.product)
  self.assertEqual(create.call_args_list[0].kwargs['line_items'],create.call_args_list[1].kwargs['line_items']);self.assertEqual(create.call_args.kwargs['line_items'][0]['price_data']['product_data']['name'],old)
 def test_invalid_discount_admin_form_returns_validation_errors(self):
  from django.forms import modelform_factory
  Form=modelform_factory(StoreDiscount,fields=['name','code','kind','value','is_active'])
  for value in ('','not-a-number','101'):
   form=Form({'name':'Check','kind':'percent','value':value,'is_active':'on'})
   self.assertFalse(form.is_valid());self.assertIn('value',form.errors)

 def test_quote_keeps_cents_when_another_library_changes_decimal_precision(self):
  from decimal import localcontext
  from career_mobility.store_offers import quote
  self.product.price_cad='12345.67'
  with localcontext() as ctx:
   ctx.prec=4
   base,final,offer=quote(self.product,self.user)
  self.assertEqual((base,final),(1234567,1234567))
 def test_processing_payment_is_visible_only_in_its_owners_library(self):
  self.order.checkout_state='processing';self.order.save()
  response=self.client.get(reverse('mobility_resource_library'));self.assertContains(response,'Your payment is processing');self.assertContains(response,self.order.stripe_session_id)
  other=get_user_model().objects.create_user('different-customer');self.client.force_login(other)
  response=self.client.get(reverse('mobility_resource_library'));self.assertNotContains(response,self.order.stripe_session_id)
