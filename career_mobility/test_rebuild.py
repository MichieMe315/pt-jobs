from django.utils import timezone
from io import BytesIO
from zipfile import ZipFile
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.files.base import ContentFile
from board.models import Employer,JobSeeker
from .models import InternationalProfile,InternationalChecklistItem,DigitalProduct,ProductOrder,DataSource,SalaryBenchmark
from .planning import build,from_answers

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RebuiltFlowTests(TestCase):
 def setUp(self):
  self.u=get_user_model().objects.create_user('intl',email='intl@example.test',password='Independent-Testing-482!')
  self.p=InternationalProfile.objects.create(email_verified_at=timezone.now(),user=self.u,country_of_education='India',destination_province='Alberta',registered_in_education_country='yes',application_history='new')
  self.answers={'country':'India','province':'Alberta','applied':'not-applied','registration':'yes'}
 def test_countries_and_redirect(self):
  from .countries import COUNTRIES
  self.assertEqual(len(COUNTRIES),249)
  with self.assertRaises(ValueError):from_answers(dict(self.answers,country='FakePlace'))
  r=self.client.get(reverse('mobility_international'),dict(self.answers,build='1'));self.assertEqual(r.status_code,302);self.assertIn('/countries/india/',r.url);self.assertIn('province=Alberta',r.url)
 def test_generic_country_honest_and_separate_shell(self):
  self.assertContains(self.client.get(reverse('mobility_country',args=['brazil'])),'WES document delivery depends on your exact school and qualification')
  self.assertContains(self.client.get(reverse('mobility_international')),reverse('mobility_international_jobs'))
 def test_pending_progress_into_signup(self):
  key=build(self.p)['steps'][0]['key'];self.client.post(reverse('mobility_international_capture'),dict(self.answers,completed=[key]))
  data={'email':'new@example.test','password':'Fresh-Independent-482!','country_of_education':'India','citizenship_country':'India','residence_country':'India','destination_province':'Alberta','canadian_immigration_status':'none','graduation_year':2024,'registered_in_education_country':'yes','application_history':'new'}
  self.client.post(reverse('mobility_international_signup'),data);p=InternationalProfile.objects.get(user__email='new@example.test')
  self.assertTrue(p.checklist_items.get(key=key).completed);self.assertFalse(JobSeeker.objects.filter(user=p.user).exists())
 def test_pending_into_existing_login(self):
  key=build(self.p)['steps'][0]['key'];self.client.post(reverse('mobility_international_capture'),dict(self.answers,completed=[key]))
  self.client.post(reverse('mobility_international_login'),{'username':'intl','password':'Independent-Testing-482!'})
  self.assertTrue(self.p.checklist_items.get(key=key).completed)
 def test_browsing_does_not_overwrite_profile(self):
  self.client.force_login(self.u);self.client.get(reverse('mobility_country',args=['pakistan']),{'province':'Quebec'})
  self.p.refresh_from_db();self.assertEqual(self.p.country_of_education,'India');self.assertEqual(self.p.destination_province,'Alberta')
 def test_save_can_reopen_checkbox(self):
  self.client.force_login(self.u);key=build(self.p)['steps'][0]['key'];InternationalChecklistItem.objects.create(profile=self.p,key=key,completed=True)
  self.client.post(reverse('mobility_checklist_toggle'),{'key':key});self.assertFalse(self.p.checklist_items.get(key=key).completed)
 def test_public_saved_pdf_match_and_fields_roundtrip(self):
  self.client.force_login(self.u);public=self.client.get(reverse('mobility_country',args=['india']),self.answers).context['steps'];saved=self.client.get(reverse('mobility_international_dashboard')).context['checklist']
  self.assertEqual([x['key'] for x in public],[x['key'] for x in saved])
  from .planning_pdf import render
  from pypdf import PdfReader,PdfWriter
  reader=PdfReader(BytesIO(render(self.p,{saved[0]['key']})));fields=reader.get_fields();self.assertEqual(len(fields),len(saved)*2+5)
  self.assertEqual(fields['done_'+saved[0]['key']]['/V'],'/Yes')
  writer=PdfWriter();writer.clone_document_from_reader(reader);key='notes_'+saved[0]['key'];writer.update_page_form_field_values(None,{key:'School records requested'},auto_regenerate=False);out=BytesIO();writer.write(out)
  self.assertEqual(PdfReader(BytesIO(out.getvalue())).get_fields()[key]['/V'],'School records requested')
 def test_wrong_country_pdf_rejected(self):
  self.client.force_login(self.u);self.assertEqual(self.client.get(reverse('mobility_country_guide',args=['pakistan'])).status_code,400)
 def test_route_fees_are_separate(self):
  for dest,history in [('Quebec','new'),('Alberta','existing')]:
   self.p.destination_province=dest;self.p.application_history=history;self.assertEqual(build(self.p)['cost_examples'],[])
  self.p.destination_province='Alberta';self.p.application_history='new';self.p.country_of_education='Australia';self.p.registered_in_education_country='no'
  self.assertEqual(build(self.p)['route_code'],'registration-check');self.assertEqual(build(self.p)['cost_examples'],[])
 def test_profile_validates_country(self):
  from .forms import InternationalProfileUpdateForm
  form=InternationalProfileUpdateForm({'country_of_education':'Fake','citizenship_country':'India','residence_country':'India','registered_in_education_country':'yes'},instance=self.p)
  self.assertFalse(form.is_valid());self.assertIn('country_of_education',form.errors)
 def test_offer_workbook_private(self):
  self.assertNotContains(self.client.get(reverse('mobility_clinic_offer_guide')),'data-offer-field');self.assertEqual(self.client.get(reverse('mobility_offer_review')).status_code,302)
  self.client.force_login(self.u);self.assertEqual(self.client.get(reverse('mobility_offer_review')).status_code,403)
 def test_grande_prairie_rent_provincial_wage(self):
  r=self.client.get(reverse('mobility_canadian'));self.assertEqual(r.context['costs']['Grande Prairie, Alberta']['rent'],'1444.5');self.assertEqual(r.context['wage_references']['Alberta']['hourly'],46)
  self.assertContains(r,'reference-hours');self.assertNotContains(r,'<select id="rural-housing-choice"')

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RebuiltAdminTests(TestCase):
 def setUp(self):
  self.staff=get_user_model().objects.create_superuser('staff','staff@example.test','Admin-Testing-482!');self.client.force_login(self.staff)
 def test_both_profile_approvals_post_only(self):
  from django.core import mail
  for cls in (Employer,JobSeeker):
   u=get_user_model().objects.create_user(cls.__name__,email=cls.__name__+'@example.test');p=cls.objects.create(user=u,is_approved=False);name='admin:board_'+cls._meta.model_name
   self.assertContains(self.client.get(reverse(name+'_change',args=[p.pk])),'Approve saved profile')
   with self.captureOnCommitCallbacks(execute=True):self.client.post(reverse(name+'_approve_profile',args=[p.pk]))
   p.refresh_from_db();self.assertTrue(p.is_approved);self.assertTrue(p.login_active);count=len(mail.outbox)
   self.client.post(reverse(name+'_approve_profile',args=[p.pk]));self.assertEqual(len(mail.outbox),count);self.assertEqual(self.client.get(reverse(name+'_approve_profile',args=[p.pk])).status_code,405)
 def test_private_preview_and_path_guards(self):
  from reportlab.pdfgen.canvas import Canvas
  pdf=BytesIO();c=Canvas(pdf);c.drawString(40,700,'Resume preview');c.save();b=BytesIO()
  with ZipFile(b,'w') as z:z.writestr('resume.pdf',pdf.getvalue())
  p=DigitalProduct.objects.create(title='Test',slug='test');p.download.save('test.zip',ContentFile(b.getvalue()))
  self.assertContains(self.client.get(reverse('admin:career_mobility_digitalproduct_catalogue'), {'q':'Test','status':'draft'}),'Test');self.assertContains(self.client.get(reverse('admin:career_mobility_digitalproduct_review',args=[p.pk])),'resume.pdf')
  r=self.client.get(reverse('admin:career_mobility_digitalproduct_asset',args=[p.pk]),{'file':'resume.pdf'});self.assertEqual(r['Content-Type'],'image/png');self.assertTrue(r.content.startswith(b'\x89PNG'))
  self.assertEqual(self.client.get(reverse('admin:career_mobility_digitalproduct_asset',args=[p.pk]),{'file':'../secret'}).status_code,404)
  self.client.logout();self.assertEqual(self.client.get(reverse('admin:career_mobility_digitalproduct_review',args=[p.pk])).status_code,302);self.assertEqual(self.client.get(reverse('mobility_product_detail',args=[p.slug])).status_code,404)
 def test_paid_unpublished_file_available(self):
  p=DigitalProduct.objects.create(title='Retired',slug='retired');p.download.save('retired.pdf',ContentFile(b'%PDF-example'));ProductOrder.objects.create(user=self.staff,product=p,paid=True,stripe_session_id='test-retired')
  self.assertEqual(self.client.get(reverse('mobility_product_download',args=[p.pk])).status_code,200)

class RebuiltSourceTests(TestCase):
 def test_queue_then_approve(self):
  from .research_refresh import URL,queue,approve
  body=b'<table><tr><td>Alberta</td><td>30</td><td>46</td><td>60</td></tr><tr><td>North Region</td><td>32</td><td>47</td><td>61</td></tr></table><p>2023-2024</p>';s=DataSource.objects.create(name='PT wage source',category='wages',url=URL)
  review=queue(s,body);self.assertFalse(SalaryBenchmark.objects.exists());self.assertEqual(approve(review),2);self.assertEqual(SalaryBenchmark.objects.get(region='Alberta').median_hourly,46);self.assertEqual(approve(review),0)
 def test_missing_table_rejected(self):
  from .research_refresh import extract
  with self.assertRaises(ValueError):extract('<html>Publication unavailable</html>')
