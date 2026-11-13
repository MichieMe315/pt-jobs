from django.utils import timezone
"""User journeys and ownership/payment regressions found during the career audit."""
import json,os,tempfile,re
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch
from zipfile import ZipFile
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.base import ContentFile
from django.test import TestCase,Client,override_settings
from django.urls import reverse
from board.models import JobSeeker
from .models import InternationalProfile,DigitalProduct,ProductOrder,SavedCareerPlan
from .planning import build
from .private_storage import PrivateMobilityStorage

@override_settings(ALLOWED_HOSTS=['testserver'],EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CareerFlowAuditTests(TestCase):
 def setUp(self):
  self.u=get_user_model().objects.create_user('audit',email='audit@example.test',password='Audit-Private-482!')
  self.p=InternationalProfile.objects.create(email_verified_at=timezone.now(),user=self.u,country_of_education='India',citizenship_country='India',residence_country='India',destination_province='Alberta',application_history='new',registered_in_education_country='yes',graduation_year=2024)
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  field=DigitalProduct._meta.get_field('download');old=field.storage;field.storage=PrivateMobilityStorage(location=self.temp.name);self.addCleanup(setattr,field,'storage',old)
  self.product=DigitalProduct.objects.create(title='Resume',slug='audit-resume',price_cad=Decimal('24.99'),is_published=True)
  b=BytesIO()
  with ZipFile(b,'w') as z:z.writestr('resume.html','<h1>Editable resume</h1>')
  self.product.download.save('resume.zip',ContentFile(b.getvalue()))
  self.answers={'country':'India','province':'Alberta','applied':'not-applied','registration':'yes'}
 def order(self,**kwargs):return ProductOrder.objects.create(user=self.u,product=self.product,stripe_session_id='cs_audit',**kwargs)
 def session(self,**changes):
  d={'id':'cs_audit','payment_status':'paid','amount_total':2499,'currency':'cad','metadata':{'mobility_product_id':str(self.product.pk),'mobility_user_id':str(self.u.pk),'mobility_amount_cents':'2499'}};d.update(changes);return d
 def profile_data(self,**changes):
  d={'country_of_education':'India','citizenship_country':'India','residence_country':'India','destination_province':'Alberta','canadian_immigration_status':'none','graduation_year':'2024','registered_in_education_country':'yes','application_history':'new'};d.update(changes);return d
 def test_invalid_profile_preserves_library_and_shows_error_tab(self):
  self.order(paid=True);self.client.force_login(self.u)
  r=self.client.post(reverse('mobility_international_profile_update'),self.profile_data(country_of_education='Invalid country'))
  self.assertEqual(r.status_code,400);self.assertEqual(list(r.context['owned_products']),[self.product]);self.assertIn('country_of_education',r.context['profile_form'].errors);self.assertEqual(r.context['active_tab'],'profile')
  self.p.refresh_from_db();self.assertEqual(self.p.country_of_education,'India')
 def test_signup_respects_final_form_destination(self):
  key=next(x['key'] for x in build(self.p)['steps'] if x['key'].startswith('province_'))
  self.client.post(reverse('mobility_international_capture'),dict(self.answers,completed=[key]))
  d=self.profile_data(destination_province='Ontario');d.update(email='new@example.test',password='Different-Private-482!')
  self.client.post(reverse('mobility_international_signup'),d)
  p=InternationalProfile.objects.get(user__email=d['email']);self.assertEqual(p.destination_province,'Ontario');self.assertFalse(p.checklist_items.filter(key=key,completed=True).exists());self.assertFalse(JobSeeker.objects.filter(user=p.user).exists())
 def test_signin_returns_to_product_but_not_external_url(self):
  target=reverse('mobility_product_detail',args=[self.product.slug]);credentials={'username':self.u.username,'password':'Audit-Private-482!'}
  self.assertRedirects(self.client.post(reverse('mobility_international_login')+'?next='+target,credentials),target);self.client.logout()
  self.assertEqual(self.client.post(reverse('mobility_international_login')+'?next=https://evil.example/',credentials).url,reverse('mobility_international_dashboard'))
 def test_account_conflict_offers_post_signout(self):
  u=get_user_model().objects.create_user('candidate');JobSeeker.objects.create(user=u,is_approved=True);self.client.force_login(u)
  r=self.client.get(reverse('mobility_international_signup'));self.assertContains(r,'method="post"');self.assertContains(r,reverse('mobility_international_logout'));self.assertEqual(self.client.post(reverse('mobility_international_logout')).status_code,302)
 def test_checklist_stays_in_correct_tab(self):
  self.client.force_login(self.u);key=build(self.p)['steps'][0]['key'];r=self.client.post(reverse('mobility_checklist_toggle'),{'key':key});self.assertTrue(r.url.endswith('#checklist'));self.assertTrue(self.p.checklist_items.get(key=key).completed)
 def test_private_library_includes_retired_purchase_only_for_owner(self):
  self.order(paid=True);DigitalProduct.objects.filter(pk=self.product.pk).update(is_published=False)
  self.assertEqual(self.client.get(reverse('mobility_resource_library')).status_code,302);self.client.force_login(self.u);self.assertContains(self.client.get(reverse('mobility_resource_library')),'Resume')
  other=get_user_model().objects.create_user('other');self.client.force_login(other);self.assertNotContains(self.client.get(reverse('mobility_resource_library')),reverse('mobility_product_download',args=[self.product.pk]))
 def test_international_shop_keeps_standalone_shell(self):
  self.client.force_login(self.u)
  for name in ['mobility_international_shop','mobility_resource_library']:
   r=self.client.get(reverse(name),follow=True);self.assertContains(r,'Physiotherapy Jobs Canada <span>International</span>');self.assertNotContains(r,'Browse jobs')
 def test_missing_file_is_404_and_purchase_disabled(self):
  self.order(paid=True);self.product.download.storage.delete(self.product.download.name);self.client.force_login(self.u)
  self.assertEqual(self.client.get(reverse('mobility_product_download',args=[self.product.pk])).status_code,404)
  self.assertContains(self.client.get(reverse('mobility_product_detail',args=[self.product.slug])),'temporarily unavailable')
 def test_country_resource_does_not_offer_wrong_profile_pdf(self):
  self.client.force_login(self.u);r=self.client.get(reverse('mobility_country_resources',args=['pakistan']));self.assertContains(r,'Your saved plan is for India');self.assertNotContains(r,'Download checklist PDF')
 def test_profile_and_capture_require_csrf(self):
  c=Client(enforce_csrf_checks=True);c.force_login(self.u)
  self.assertEqual(c.post(reverse('mobility_international_profile_update'),self.profile_data()).status_code,403);self.assertEqual(c.post(reverse('mobility_international_capture'),self.answers).status_code,403)
 def test_checkout_uses_snapshot_and_stable_idempotency_key(self):
  self.client.force_login(self.u)
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'test','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'test'}),patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_audit',url='https://checkout.stripe.com/test')) as create:
   keys=[]
   for _ in range(2):
    self.assertEqual(self.client.post(reverse('mobility_product_checkout',args=[self.product.pk])).status_code,302);kw=create.call_args.kwargs;keys.append(kw['idempotency_key']);self.assertEqual(kw['metadata']['mobility_amount_cents'],'2499');self.assertIn('api_key',kw);self.assertIn('session_id={CHECKOUT_SESSION_ID}',kw['success_url'])
   self.assertEqual(keys[0],keys[1]);self.assertEqual(ProductOrder.objects.count(),1)
 def test_verified_return_and_webhook_fulfill_once(self):
  o=self.order();self.client.force_login(self.u)
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'test','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'test'}),patch('stripe.checkout.Session.retrieve',return_value=self.session()):
   with self.captureOnCommitCallbacks(execute=True):r=self.client.get(reverse('mobility_product_success')+'?session_id=cs_audit')
   self.assertContains(r,'Your resource is ready')
   with patch('stripe.Webhook.construct_event',return_value={'type':'checkout.session.completed','data':{'object':self.session()}}):
    with self.captureOnCommitCallbacks(execute=True):self.assertEqual(self.client.post(reverse('mobility_stripe_webhook'),b'{}',content_type='application/json').status_code,200)
  o.refresh_from_db();self.assertTrue(o.paid);self.assertEqual(sum('Your download is ready' in m.subject for m in mail.outbox),1)
 def test_unpaid_return_never_grants_access(self):
  o=self.order();self.client.force_login(self.u)
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'test'}),patch('stripe.checkout.Session.retrieve',return_value=self.session(payment_status='unpaid')):self.assertContains(self.client.get(reverse('mobility_product_success')+'?session_id=cs_audit'),'payment is processing')
  o.refresh_from_db();self.assertFalse(o.paid);self.assertEqual(self.client.get(reverse('mobility_product_download',args=[self.product.pk])).status_code,403)
 def test_foreign_return_never_reveals_or_grants_order(self):
  o=self.order();self.client.force_login(get_user_model().objects.create_user('intruder'))
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'test'}),patch('stripe.checkout.Session.retrieve',return_value=self.session()):self.assertEqual(self.client.get(reverse('mobility_product_success')+'?session_id=cs_audit').status_code,400)
  o.refresh_from_db();self.assertFalse(o.paid)
 def test_amount_currency_and_metadata_must_match(self):
  o=self.order();from .product_payments import fulfill,InvalidProductCheckout
  for d in [{'amount_total':1},{'currency':'usd'},{'metadata':{'mobility_product_id':'999','mobility_amount_cents':'2499'}}]:
   with self.assertRaises(InvalidProductCheckout):fulfill(self.session(**d))
  o.refresh_from_db();self.assertFalse(o.paid)
 def test_admin_price_change_does_not_break_paid_snapshot(self):
  o=self.order();DigitalProduct.objects.filter(pk=self.product.pk).update(price_cad=99)
  from .product_payments import fulfill
  fulfill(self.session());o.refresh_from_db();self.assertTrue(o.paid)
 def test_unknown_return_reference_is_400(self):
  self.client.force_login(self.u)
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'test'}),patch('stripe.checkout.Session.retrieve',return_value=self.session()):self.assertEqual(self.client.get(reverse('mobility_product_success')+'?session_id=cs_audit').status_code,400)
 def test_unconfigured_checkout_creates_no_order(self):
  self.client.force_login(self.u)
  with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':''}):self.assertEqual(self.client.post(reverse('mobility_product_checkout',args=[self.product.pk])).status_code,503)
  self.assertFalse(ProductOrder.objects.exists())
 def test_canadian_purchaser_gets_receipt(self):
  u=get_user_model().objects.create_user('canadian',email='canadian@example.test');JobSeeker.objects.create(user=u,is_approved=True);self.order();ProductOrder.objects.update(user=u)
  data=self.session();data['metadata']['mobility_user_id']=str(u.pk)
  from .product_payments import fulfill
  with self.captureOnCommitCallbacks(execute=True):fulfill(data,site_base='https://testserver/')
  self.assertTrue(any(u.email in m.to and 'Your download is ready' in m.subject for m in mail.outbox))
 def test_saved_plan_privacy_invalid_id_and_delete_return(self):
  u=get_user_model().objects.create_user('candidate-finance');JobSeeker.objects.create(user=u,is_approved=True)
  p=SavedCareerPlan.objects.create(user=u,plan_type='relocation',title='Private',inputs={'origin':'Toronto','destination':'Calgary'})
  self.client.force_login(self.u);self.assertEqual(self.client.get(reverse('mobility_canadian_full')).status_code,403);self.assertEqual(self.client.get(reverse('mobility_plan_pdf',args=[p.pk])).status_code,404)
  self.client.force_login(u);self.assertEqual(self.client.get(reverse('mobility_canadian_full')+'?saved=garbage').status_code,404)
  self.assertEqual(self.client.post(reverse('mobility_delete_plan',args=[p.pk])).url,reverse('mobility_relocation_comparisons'))
 def test_password_reset_roundtrip_and_reused_link(self):
  from urllib.parse import urlsplit
  self.assertEqual(self.client.post(reverse('mobility_international_password_reset'),{'email':self.u.email}).status_code,302);self.assertEqual(len(mail.outbox),1)
  path=urlsplit(re.search(r'https?://[^\s]+/international/reset/[^\s]+',mail.outbox[0].body).group()).path
  response=self.client.get(path);self.assertEqual(response.status_code,302)
  self.assertEqual(self.client.post(response.url,{'new_password1':'Brand-New-Private-632!','new_password2':'Brand-New-Private-632!'}).status_code,302)
  self.u.refresh_from_db();self.assertTrue(self.u.check_password('Brand-New-Private-632!'));self.assertContains(self.client.get(path),'reset link has expired')
 def test_reset_does_not_email_noninternational_accounts(self):
  u=get_user_model().objects.create_user('candidate-reset',email='candidate@example.test',password='Candidate-Private-482!');JobSeeker.objects.create(user=u,is_approved=True)
  for email in [u.email,'unknown@example.test']:self.assertEqual(self.client.post(reverse('mobility_international_password_reset'),{'email':email}).status_code,302)
  self.assertEqual(len(mail.outbox),0)
 def test_nonfinite_saved_values_return_400(self):
  u=get_user_model().objects.create_user('candidate-budget');JobSeeker.objects.create(user=u,is_approved=True);self.client.force_login(u)
  for value in [float('nan'),float('inf')]:self.assertEqual(self.client.post(reverse('mobility_save_plan'),json.dumps({'plan_type':'relocation','inputs':{'new-salary':value}}),content_type='application/json').status_code,400)
  self.assertFalse(SavedCareerPlan.objects.exists())
 def test_saved_relocation_pdf_has_results_instead_of_raw_fields(self):
  u=get_user_model().objects.create_user('report-candidate');JobSeeker.objects.create(user=u,is_approved=True);self.client.force_login(u)
  data={'origin':'Toronto','destination':'Grande Prairie','current-salary':'80000','new-salary':'90000','current-rent':'2500','new-rent':'1500','current-living':'1600','new-living':'1400','moving':'2000'}
  p=SavedCareerPlan.objects.create(user=u,plan_type='relocation',inputs=data)
  response=self.client.get(reverse('mobility_plan_pdf',args=[p.pk]));self.assertEqual(response.status_code,200)
  from pypdf import PdfReader
  text=''.join(x.extract_text() for x in PdfReader(BytesIO(response.content)).pages)
  self.assertIn('Monthly difference:',text);self.assertIn('2,033.33',text);self.assertIn('First-year difference',text)
 def test_pdf_zero_takehome_and_itemized_costs(self):
  from .relocation_pdf import comparison_response
  data={'origin':'A','destination':'B','current-salary':80000,'new-salary':90000,'current-rent':1000,'new-rent':1000,'current-net':0,'new-net':0,'expense_mode':'itemized','current-groceries':500,'new-groceries':400}
  response=comparison_response(data);self.assertEqual(response.status_code,200)
  from pypdf import PdfReader
  text=''.join(x.extract_text() for x in PdfReader(BytesIO(response.content)).pages);self.assertIn('take-home pay',text);self.assertIn('CAD $100.00',text)
 def test_all_education_countries_have_working_pages(self):
  from .countries import COUNTRIES
  from .country_content import get_country
  for name in COUNTRIES:
   with self.subTest(country=name):
    country=get_country(name);self.assertIsNotNone(country)
    response=self.client.get(reverse('mobility_country',args=[country['slug']]),{'province':'Alberta','applied':'not-applied','registration':'yes'})
    self.assertEqual(response.status_code,200);self.assertEqual(response.context['answers']['country'],name)
 def test_fillable_workbook_field_values_and_widget_appearances_agree(self):
  from .planning_pdf import render
  from pypdf import PdfReader,PdfWriter
  steps=build(self.p)['steps'];first=steps[0]['key'];reader=PdfReader(BytesIO(render(self.p,{first})))
  self.assertEqual(reader.get_fields()['done_'+first]['/V'],'/Yes')
  writer=PdfWriter();writer.clone_document_from_reader(reader);writer.update_page_form_field_values(None,{'notes_'+first:'School records requested'},auto_regenerate=False)
  out=BytesIO();writer.write(out);check=PdfReader(BytesIO(out.getvalue()));self.assertEqual(check.get_fields()['notes_'+first]['/V'],'School records requested')
  widgets=[a.get_object() for page in check.pages for a in page.get('/Annots',[]) if a.get_object().get('/Subtype')=='/Widget']
  found=[w for w in widgets if w.get('/T')=='notes_'+first];self.assertEqual(len(found),1);self.assertEqual(found[0]['/V'],'School records requested');self.assertTrue(found[0].get('/AP',{}).get('/N'))
 def test_admin_resume_import_is_post_only_private_and_preserves_prices(self):
  from pathlib import Path
  from .management.commands import import_pt_resume_v6 as command
  root=Path(self.temp.name)/'imports';root.mkdir()
  for name in ['03_Internationally_Educated.zip','Annotated_PT_Resume_Examples.pdf','PT_Application_Studio.pdf','PT_Resume_Writing_and_Personalization.pdf','PT_Personal_Brand_Graphics.zip','PT_Resume_Complete_Collection.zip']:(root/name).write_bytes(b'audit package')
  staff=get_user_model().objects.create_superuser('importer','importer@example.test','Private-Audit-482!');self.client.force_login(staff)
  url=reverse('admin:career_mobility_digitalproduct_resume_import');self.assertEqual(self.client.get(url).status_code,405)
  with patch.object(command,'ASSETS',root):
   self.assertEqual(self.client.post(url).status_code,302)
   product=DigitalProduct.objects.get(slug='pt-v6-03_internationally_educated');self.assertFalse(product.is_published);self.assertEqual(product.category,'International resumes')
   product.price_cad=29;product.is_published=True;product.save();old_file=product.download.name
   self.client.post(url);product.refresh_from_db();self.assertEqual(product.price_cad,29);self.assertTrue(product.is_published);self.assertEqual(product.download.name,old_file)
  self.client.logout();self.assertEqual(self.client.post(url).status_code,302)
