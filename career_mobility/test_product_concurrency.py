"""Run the payment callback race on PostgreSQL, where row locking is available."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import close_old_connections,connections
from django.test import TransactionTestCase,skipUnlessDBFeature
from .models import DigitalProduct,ProductOrder
from .product_payments import fulfill
@skipUnlessDBFeature('has_select_for_update')
class ProductPaymentConcurrencyTests(TransactionTestCase):
 def test_webhook_and_browser_return_confirm_one_order_once(self):
  u=get_user_model().objects.create_user('resource-buyer');p=DigitalProduct.objects.create(title='Resource',slug='resource',price_cad=25)
  order=ProductOrder.objects.create(user=u,product=p,stripe_session_id='cs_concurrent_resource')
  data={'id':order.stripe_session_id,'payment_status':'paid','amount_total':2500,'currency':'cad','metadata':{'mobility_product_id':str(p.pk),'mobility_user_id':str(u.pk),'mobility_amount_cents':'2500'}}
  gate=Barrier(2)
  def run():
   close_old_connections()
   try:gate.wait(timeout=10);return fulfill(data).paid
   finally:connections.close_all()
  with patch('career_mobility.international_notifications.confirm_purchase') as receipt,ThreadPoolExecutor(max_workers=2) as pool:
   futures=[pool.submit(run) for _ in range(2)];self.assertEqual([f.result(timeout=30) for f in futures],[True,True]);self.assertEqual(receipt.call_count,1)
  order.refresh_from_db();self.assertTrue(order.paid);self.assertEqual(ProductOrder.objects.count(),1)

@skipUnlessDBFeature('has_select_for_update')
class DigitalAccessConcurrencyTests(TransactionTestCase):
 def parallel(self,operation):
  gate=Barrier(2)
  def run(n):
   close_old_connections()
   try:gate.wait(timeout=10);return operation(n)
   finally:connections.close_all()
  with ThreadPoolExecutor(max_workers=2) as pool:
   jobs=[pool.submit(run,n) for n in range(2)]
   return [job.result(timeout=30) for job in jobs]
 def test_one_workbook_credit_cannot_be_consumed_twice(self):
  from .models import StoreGrant,StoreEntitlement
  from .store_access import activate_grant,consume_workbook
  u=get_user_model().objects.create_user('credit-race')
  p=DigitalProduct.objects.create(title='Workbook',slug='race-workbook',kind='workbook')
  g=StoreGrant.objects.create(user=u,product=p,quantity=1,reason='Race test');activate_grant(g)
  results=self.parallel(lambda n:consume_workbook(u,p,lambda:b'%PDF-test'))
  self.assertEqual(sum(item is not None for item in results),1)
  self.assertEqual(StoreEntitlement.objects.get(grant=g).remaining,0)
 def test_last_discount_use_can_only_be_reserved_once(self):
  from django.db import transaction
  from django.utils import timezone
  from datetime import timedelta
  from .models import StoreDiscount
  from .store_offers import quote,OfferError
  users=[get_user_model().objects.create_user('offer-race-'+str(n)) for n in range(2)]
  product=DigitalProduct.objects.create(title='Resource',slug='offer-race',price_cad=10)
  StoreDiscount.objects.create(name='Last use',code='LAST',kind='percent',value=50,max_uses=1)
  def reserve(n):
   try:
    with transaction.atomic():
     base,amount,offer=quote(product,users[n],'LAST',lock=True)
     ProductOrder.objects.create(user=users[n],product=product,stripe_session_id='cs_race_'+str(n),discount=offer,amount_cents=amount,checkout_expires_at=timezone.now()+timedelta(minutes=10))
    return True
   except OfferError:return False
  self.assertEqual(sorted(self.parallel(reserve)),[False,True])
  self.assertEqual(ProductOrder.objects.count(),1)
 def test_checkout_retry_and_paid_callback_cannot_deadlock_on_customer_fk(self):
  import os
  from threading import Event
  from datetime import timedelta
  from types import SimpleNamespace
  from django.utils import timezone
  from django.test import RequestFactory
  from .store_checkout import start
  from .store_access import snapshot,activate_order
  from .models import StoreEntitlement
  user=get_user_model().objects.create_user('callback-lock-race')
  product=DigitalProduct.objects.create(title='Resource',slug='callback-lock-race',price_cad=25)
  items=snapshot(product);items[0].update(code='',checkout_name=product.title)
  order=ProductOrder.objects.create(user=user,product=product,stripe_session_id='cs_callback_lock',amount_cents=2500,checkout_snapshot=items,checkout_expires_at=timezone.now()+timedelta(minutes=35))
  user_locked=Event();order_locked=Event()
  def provider(**kwargs):
   user_locked.set();assert order_locked.wait(10),'Callback did not acquire its order lock'
   return SimpleNamespace(id=order.stripe_session_id,url='https://checkout.stripe.com/lock-test')
  def activate(locked_order):
   order_locked.set();return activate_order(locked_order)
  def checkout():
   close_old_connections()
   try:
    request=RequestFactory().post('/checkout/');request.user=user;request.session={'store_pending_order':order.pk}
    return start(request,product)[0].pk
   finally:connections.close_all()
  def callback():
   close_old_connections()
   try:
    assert user_locked.wait(10),'Checkout did not acquire the account lock'
    return fulfill({'id':order.stripe_session_id,'payment_status':'paid','amount_total':2500,'currency':'cad'}).paid
   finally:connections.close_all()
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'sk_test_lock','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_lock'}),patch('stripe.checkout.Session.create',side_effect=provider),patch('career_mobility.store_access.activate_order',side_effect=activate),patch('career_mobility.international_notifications.confirm_purchase'),ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(checkout);second=pool.submit(callback)
   self.assertEqual(first.result(timeout=30),order.pk);self.assertTrue(second.result(timeout=30))
  self.assertEqual(StoreEntitlement.objects.filter(order=order).count(),1)
