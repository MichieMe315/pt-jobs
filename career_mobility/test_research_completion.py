import json
from pathlib import Path
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from .research_refresh import extract,extract_alberta,queue,approve,URL,ALBERTA_URL
from .models import DataSource,ReferenceCost,SalaryBenchmark
from .planning import build,from_answers

class ResearchCompletionTests(TestCase):
 def test_real_table_shape_and_region_names_are_province_scoped(self):
  body='''<table><tr><th>ProvinceCode</th><th>Community/Area</th><th>Low ($/hour)</th><th>Median ($/hour)</th><th>High ($/hour)</th><th>Note</th></tr><tr><td>ON</td><th>Northeast Region</th><td>30</td><td>45</td><td>60</td><td>Reference period: 2024</td></tr><tr><td>BC</td><th>Northeast Region</th><td>32</td><td>47</td><td>62</td><td>Reference period: 2023-2024</td></tr></table>'''
  rows=extract(body);self.assertEqual([r['province'] for r in rows],['Ontario','British Columbia']);self.assertEqual([r['reference_period'] for r in rows],['2024','2023-2024'])
  s=DataSource.objects.create(name='Test wage source',url=URL,category='wages');review=queue(s,body.encode());self.assertFalse(SalaryBenchmark.objects.exists());self.assertEqual(approve(review),2);self.assertEqual(SalaryBenchmark.objects.filter(region='Northeast Region').count(),2);self.assertEqual(queue(s,body.encode()).pk,review.pk)
 def test_withdrawn_wage_is_not_reused_from_old_snapshot(self):
  from django.utils import timezone
  from .views import _canadian_context
  old=SalaryBenchmark.objects.create(region='Northeast Region',province='Ontario',median_hourly=45,source_url=URL,reference_period='2024',verified_on=timezone.localdate(),is_published=True)
  body=b'<table><tr><td>ON</td><th>Ontario</th><td>30</td><td>46</td><td>60</td><td>Reference period: 2024</td></tr><tr><td>ON</td><th>Northeast Region</th><td>N/A</td><td>N/A</td><td>N/A</td><td>Reference period: 2024</td></tr></table>'
  source=DataSource.objects.create(name='Withdrawal test',url=URL,category='wages');review=queue(source,body);approve(review);old.refresh_from_db();self.assertFalse(old.is_published)
  values=_canadian_context()['regional_wage_references'];self.assertIsNone(next(r for r in values if r['area']=='Northeast Region' and r['province']=='Ontario')['hourly'])
 def test_approved_regional_wage_is_used_by_comparison(self):
  from django.utils import timezone
  from .views import _canadian_context
  SalaryBenchmark.objects.create(region='Toronto Region',province='Ontario',median_hourly=49,source_url=URL,reference_period='2024',verified_on=timezone.localdate(),is_published=True)
  rows=_canadian_context()['regional_wage_references'];self.assertEqual(next(r for r in rows if r['area']=='Toronto Region' and r['province']=='Ontario')['hourly'],'49.00')
 def test_alberta_official_binary_content_type_is_validated_as_json(self):
  from unittest.mock import patch
  from .research_refresh import fetch
  class Response:
   url=ALBERTA_URL
   headers={'Content-Type':'application/octet-stream'}
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,limit):return json.dumps([{'CSD':'Source Town','Period':'2025','Dimensions':[{'Value':'2 - bedroom'}],'OriginalValue':1200}]).encode()
  source=DataSource.objects.create(name='Official content-type test',url=ALBERTA_URL,category='housing')
  with patch('career_mobility.research_refresh.urlopen',return_value=Response()):review=fetch(source)
  self.assertEqual(json.loads(review.detail)['rows'][0]['city'],'Source Town')
 def test_rent_import_uses_latest_year_and_requires_review(self):
  body=json.dumps([{'CSD':'Test Town','Period':year,'Dimensions':[{'Value':'2 - bedroom'}],'OriginalValue':value} for year,value in [('2024',900),('2025',1000.5)]]).encode()
  self.assertEqual(extract_alberta(body)[0]['reference_period'],'2025')
  s=DataSource.objects.create(name='Test rent source',url=ALBERTA_URL,category='housing');review=queue(s,body);self.assertFalse(ReferenceCost.objects.exists());self.assertEqual(approve(review),1);r=ReferenceCost.objects.get(city='Test Town');self.assertEqual(r.reference_period,'2025');self.assertEqual(float(r.amount_cad),1000.5)
 def test_new_rent_reference_preserves_other_existing_costs(self):
  from django.utils import timezone
  from .views import _canadian_context
  ReferenceCost.objects.create(kind='living',city='Brooks',province='Alberta',amount_cad=777,source_url='https://example.test/source',verified_on=timezone.localdate(),is_published=True)
  costs=_canadian_context()['costs']['Brooks, Alberta'];self.assertEqual(costs['living'],'777.00');self.assertIn('rent',costs)
 def test_shipped_rent_and_geography_coverage(self):
  root=Path(__file__).parent/'data';housing=json.loads((root/'community_updates_2026_10_28.json').read_text());geo=json.loads((root/'community_economic_regions_2021.json').read_text())
  self.assertEqual(len(housing),81);self.assertEqual(len(geo['records']),5161)
  self.assertEqual(next(r for r in geo['records'] if r['city']=='Grande Prairie' and r['province']=='Alberta')['regions'],['Athabasca--Grande Prairie--Peace River'])
 def test_all_country_and_destination_pairs_have_documents_and_steps(self):
  from .countries import COUNTRIES
  from .forms import PROVINCES
  for country in COUNTRIES:
   for province in PROVINCES:
    plan=build(from_answers({'country':country,'province':province,'applied':'not-applied','registration':'yes'}))
    self.assertTrue(plan['document_tasks'],(country,province));self.assertTrue(plan['steps'],(country,province))
    if province in ('Northwest Territories','Nunavut'):self.assertEqual(plan['route_code'],'employer-credentials');self.assertEqual(plan['cost_examples'],[])
 def test_nb_and_manitoba_have_confirmed_application_fees(self):
  from .research_library import records
  rows=records('licensing_fees')
  for province,amount in [('New Brunswick',150),('Manitoba',200)]:self.assertTrue(any(r['province_or_territory']==province and r['amount_cad']==amount and r['fee_type']=='application' for r in rows))

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',DEFAULT_FROM_EMAIL='site@example.test')
class NotificationCompletionTests(TestCase):
 def test_both_template_senders_use_branded_layout_and_correct_reply(self):
  from board.models import EmailTemplate
  from board.emails import send_templated_email
  from django.core import mail
  EmailTemplate.objects.create(key='admin_revision_test',subject='Registration update',html='<p>Saved custom text</p>',is_enabled=True)
  self.assertTrue(send_templated_email('admin_revision_test',['owner@example.test'],{'email':'candidate@example.test'}));self.assertEqual(mail.outbox[-1].reply_to,['candidate@example.test']);self.assertIn('role="presentation"',mail.outbox[-1].alternatives[0].content);self.assertNotIn('Skilled Trade Jobs',mail.outbox[-1].alternatives[0].content)

@override_settings(CAREER_TOOLS_PREVIEW=True,SECURE_SSL_REDIRECT=False)
class ProductReviewCompletionTests(TestCase):
 def test_pdf_can_be_chosen_as_store_image_without_publishing(self):
  import tempfile,zipfile
  from io import BytesIO
  from django.core.files.base import ContentFile
  from career_mobility.models import DigitalProduct
  from career_mobility.private_storage import PrivateMobilityStorage
  from reportlab.pdfgen.canvas import Canvas
  with tempfile.TemporaryDirectory() as folder:
   field=DigitalProduct._meta.get_field('download');imagefield=DigitalProduct._meta.get_field('preview_image');old=field.storage;oldimage=imagefield.storage
   field.storage=PrivateMobilityStorage(location=folder);imagefield.storage=PrivateMobilityStorage(location=folder)
   try:
    u=get_user_model().objects.create_superuser('catalogue-review-user','catalogue@example.test','Local-Testing-482!');self.client.force_login(u)
    stream=BytesIO();canvas=Canvas(stream);canvas.drawString(40,700,'A fictional resume for preview testing');canvas.showPage();canvas.save();archive=BytesIO()
    with zipfile.ZipFile(archive,'w') as z:z.writestr('resume.pdf',stream.getvalue())
    product=DigitalProduct.objects.create(title='Review test',slug='review-test',price_cad=25,is_published=False);product.download.save('test.zip',ContentFile(archive.getvalue()))
    r=self.client.post(reverse('admin:career_mobility_digitalproduct_review',args=[product.pk]),{'preview':'resume.pdf'})
    self.assertEqual(r.status_code,302);product.refresh_from_db();self.assertTrue(product.preview_image);self.assertFalse(product.is_published)
    url=reverse('admin:career_mobility_digitalproduct_store_image',args=[product.pk]);r=self.client.get(url);self.assertEqual(r.status_code,200);self.assertEqual(r['Content-Type'],'image/jpeg');r.close();self.client.logout();self.assertEqual(self.client.get(url).status_code,302)
   finally:field.storage=old;imagefield.storage=oldimage
