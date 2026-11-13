from django.utils import timezone
from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.urls import reverse
from django.core.files.base import ContentFile
from .models import InternationalProfile,DigitalProduct,ProductOrder
from .admin import DigitalProductAdminForm
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',ALLOWED_HOSTS=['testserver'])
class SecondJourneyAuditTests(TestCase):
 def test_product_signup_return_and_answers_survive(self):
  p=DigitalProduct.objects.create(title='Kit',slug='signup-kit',price_cad=25,is_published=True)
  target=reverse('mobility_product_detail',args=[p.slug])
  data={'email':'signup@example.test','password':'New-Private-Audit-482!','country_of_education':'India','citizenship_country':'India','residence_country':'India','destination_province':'Alberta','canadian_immigration_status':'none','graduation_year':2024,'registered_in_education_country':'yes','application_history':'new','next':target}
  response=self.client.post(reverse('mobility_international_signup'),data)
  self.assertEqual(response.url,reverse('mobility_verify_pending'));self.assertEqual(self.client.session['international_verified_next'],target)
 def test_country_resources_carry_destination_into_signup_link(self):
  response=self.client.get(reverse('mobility_country_resources',args=['india']),{'province':'Alberta','applied':'after','registration':'previous'})
  self.assertContains(response,'destination_province=Alberta');self.assertContains(response,'application_history=after')
 def test_published_product_can_be_made_free_from_list_edit(self):
  from django.forms import modelform_factory
  product=DigitalProduct.objects.create(title='Kit',slug='price-kit',price_cad=25,is_published=True)
  product.download.save('kit.pdf',ContentFile(b'%PDF-example'))
  formclass=modelform_factory(DigitalProduct,form=DigitalProductAdminForm,fields=['price_cad'])
  form=formclass({'price_cad':'0'},instance=product)
  self.assertTrue(form.is_valid(),form.errors)
 def test_signup_does_not_allow_external_redirect(self):
  data={'email':'safe@example.test','password':'New-Private-Audit-482!','country_of_education':'India','citizenship_country':'India','residence_country':'India','destination_province':'Alberta','canadian_immigration_status':'none','graduation_year':2024,'registered_in_education_country':'yes','application_history':'new','next':'https://evil.example/'}
  self.assertEqual(self.client.post(reverse('mobility_international_signup'),data).url,reverse('mobility_verify_pending'));self.assertEqual(self.client.session['international_verified_next'],'')
 def test_explicit_signup_country_overrides_old_pending_plan(self):
  self.client.post(reverse('mobility_international_capture'),{'country':'India','province':'Alberta','applied':'not-applied','registration':'yes'})
  response=self.client.get(reverse('mobility_international_signup'),{'country_of_education':'Pakistan','destination_province':'Ontario'})
  self.assertEqual(response.context['form']['country_of_education'].value(),'Pakistan');self.assertEqual(response.context['form']['destination_province'].value(),'Ontario')
 def test_resource_download_does_not_silently_use_wrong_destination(self):
  u=get_user_model().objects.create_user('route');InternationalProfile.objects.create(email_verified_at=timezone.now(),user=u,country_of_education='India',destination_province='Ontario',application_history='new',registered_in_education_country='yes');self.client.force_login(u)
  response=self.client.get(reverse('mobility_country_resources',args=['india']),{'province':'Alberta','applied':'not-applied','registration':'yes'})
  self.assertContains(response,'Review and save this India plan');self.assertNotContains(response,'Download checklist PDF')
 def test_unknown_country_resources_state_research_gap(self):
  self.assertContains(self.client.get(reverse('mobility_country_resources',args=['brazil'])),'Document delivery requirements depend on your school and qualification')
 def test_checkout_amount_survives_admin_price_change(self):
  from .product_payments import fulfill,InvalidProductCheckout
  u=get_user_model().objects.create_user('buyer');p=DigitalProduct.objects.create(title='Kit',slug='amount-kit',price_cad=25)
  order=ProductOrder.objects.create(user=u,product=p,stripe_session_id='cs_snapshot',amount_cents=2500)
  p.price_cad=99;p.save()
  data={'id':order.stripe_session_id,'payment_status':'paid','amount_total':2500,'currency':'cad','metadata':{'mobility_amount_cents':'2500'}}
  fulfill(data);order.refresh_from_db();self.assertTrue(order.paid);self.assertEqual(order.amount_cents,2500)
 def test_checkout_amount_must_match_saved_order(self):
  from .product_payments import fulfill,InvalidProductCheckout
  u=get_user_model().objects.create_user('mismatch');p=DigitalProduct.objects.create(title='Kit',slug='mismatch-kit',price_cad=25)
  o=ProductOrder.objects.create(user=u,product=p,stripe_session_id='cs_wrong',amount_cents=2500)
  with self.assertRaises(InvalidProductCheckout):fulfill({'id':o.stripe_session_id,'payment_status':'paid','amount_total':1,'currency':'cad','metadata':{'mobility_amount_cents':'1'}})
  o.refresh_from_db();self.assertFalse(o.paid)
 def test_shop_report_requires_permissions_and_uses_recorded_amounts(self):
  staff=get_user_model().objects.create_user('staff',is_staff=True);self.client.force_login(staff);self.assertEqual(self.client.get(reverse('ptjc_shop_admin')).status_code,403)
  admin=get_user_model().objects.create_superuser('sales','sales@example.test','Private-Test-482!');self.client.force_login(admin)
  p=DigitalProduct.objects.create(title='Changed price',slug='old-price',price_cad=99)
  ProductOrder.objects.create(user=staff,product=p,stripe_session_id='cs_known',paid=True,amount_cents=2500)
  ProductOrder.objects.create(user=staff,product=p,stripe_session_id='cs_legacy',paid=True)
  response=self.client.get(reverse('ptjc_shop_admin'));self.assertEqual(response.context['revenue_estimate'],Decimal('25'));self.assertEqual(response.context['orders_missing_amount'],1)
 def test_real_admin_product_editor_accepts_free_canadian_price(self):
  admin=get_user_model().objects.create_superuser('price-admin','price@example.test','Private-Test-482!');self.client.force_login(admin)
  p=DigitalProduct.objects.create(title='Price list',slug='actual-list',price_cad=25,is_published=True);p.download.save('list.pdf',ContentFile(b'%PDF-example'))
  response=self.client.post(reverse('admin:career_mobility_digitalproduct_change',args=[p.pk]), {
      'title':p.title, 'slug':p.slug, 'kind':'file', 'audience':'both', 'is_published':'on',
      'price_cad':'25', 'canadian_price_cad':'0', 'international_price_cad':'30',
      'gallery_images-TOTAL_FORMS':'0', 'gallery_images-INITIAL_FORMS':'0',
      'gallery_images-MIN_NUM_FORMS':'0', 'gallery_images-MAX_NUM_FORMS':'1000', '_save':'Save',
  })
  self.assertEqual(response.status_code,302);p.refresh_from_db()
  self.assertEqual(p.price_cad,25);self.assertEqual(p.canadian_price_cad,0)
  self.assertEqual(p.international_price_cad,30)
 def test_paid_orders_cannot_be_added_or_deleted_in_admin(self):
  admin=get_user_model().objects.create_superuser('order-admin','order@example.test','Private-Test-482!');self.client.force_login(admin)
  p=DigitalProduct.objects.create(title='Kit',slug='order-kit',price_cad=25);o=ProductOrder.objects.create(user=admin,product=p,stripe_session_id='cs_history',paid=True,amount_cents=2500)
  self.assertEqual(self.client.get(reverse('admin:career_mobility_productorder_add')).status_code,403)
  self.assertEqual(self.client.post(reverse('admin:career_mobility_productorder_delete',args=[o.pk]),{'post':'yes'}).status_code,403);self.assertTrue(ProductOrder.objects.filter(pk=o.pk).exists())
 def test_country_collection_admin_uses_a_country_dropdown(self):
  from .admin import CountryResourceCollectionForm
  from django.forms import Select
  form=CountryResourceCollectionForm();self.assertIsInstance(form.fields['country_slug'].widget,Select);self.assertIn(('india','India'),form.fields['country_slug'].choices)
