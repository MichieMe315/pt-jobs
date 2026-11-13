import json
from io import BytesIO
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from career_mobility.models import InternationalProfile,DigitalProduct,StoreGrant
from career_mobility.store_access import activate_grant
from .models import BusinessCardDraft,ResumeDraft
from .schema import normalize,EXAMPLE
from .pdf import render_pdf
from .cards import normalize as card_normalize,svg,pdf

@override_settings(ALLOWED_HOSTS=['testserver'],CAREER_TOOLS_PREVIEW=True,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',SECURE_SSL_REDIRECT=False)
class ResourceBuilderUpgradeTests(TestCase):
 def setUp(self):
  self.user=get_user_model().objects.create_user('builder-upgrade',email='builder@example.test')
  InternationalProfile.objects.create(user=self.user,country_of_education='Philippines',email_verified_at=timezone.now(),email_verified_address=self.user.email)
  self.client.force_login(self.user)
 def test_all_four_resume_layouts_preserve_location_and_text(self):
  from pypdf import PdfReader
  blobs=[]
  for layout in ('classic','clinical','editorial','sidebar'):
   raw=dict(EXAMPLE,layout=layout,specialties='Musculoskeletal');raw['experience']=[dict(EXAMPLE['experience'][0],location='Pune, Maharashtra')]
   data=normalize(raw);self.assertEqual(data['experience'][0]['location'],'Pune, Maharashtra')
   blob=render_pdf(data);text='\n'.join(p.extract_text() for p in PdfReader(BytesIO(blob)).pages)
   self.assertIn('Pune, Maharashtra',text);self.assertIn('Musculoskeletal',text);self.assertIn(EXAMPLE['name'],text);blobs.append(blob)
  self.assertEqual(len(set(blobs)),4)
 def test_layout_selection_rejects_unknown_values(self):
  with self.assertRaises(ValidationError):normalize({'layout':'untrusted'})
 def test_card_draft_save_does_not_require_purchase(self):
  response=self.client.post(reverse('ptjc_resumes:card_create'));self.assertEqual(response.status_code,302)
  card=BusinessCardDraft.objects.get(owner=self.user)
  response=self.client.post(reverse('ptjc_resumes:card_save',args=[card.pk]),json.dumps({'revision':1,'data':{'name':'My real name','design':'community','city':'Pune, Maharashtra'}}),content_type='application/json')
  self.assertEqual(response.status_code,200);card.refresh_from_db();self.assertEqual(card.data['city'],'Pune, Maharashtra')
  self.assertEqual(self.client.get(reverse('ptjc_resumes:card_download',args=[card.pk])).status_code,403)
 def test_card_purchase_entitlement_unlocks_all_four_designs(self):
  product=DigitalProduct.objects.get(slug='international-business-card-builder-access');grant=StoreGrant.objects.create(user=self.user,product=product,reason='Welcome bundle');activate_grant(grant)
  card=BusinessCardDraft.objects.create(owner=self.user,data=card_normalize({'name':'My real name'}))
  for design in ('clinical','community','editorial','networking'):
   card.data=card_normalize({'name':'My real name','design':design});card.save()
   response=self.client.get(reverse('ptjc_resumes:card_download',args=[card.pk]));self.assertEqual(response.status_code,200);self.assertTrue(response.content.startswith(b'%PDF'))
 def test_cards_are_private_and_save_conflicts_are_rejected(self):
  other=get_user_model().objects.create_user('someone-else');card=BusinessCardDraft.objects.create(owner=other,data=card_normalize({}))
  for endpoint in ('card_edit','card_preview','card_download'):self.assertEqual(self.client.get(reverse('ptjc_resumes:'+endpoint,args=[card.pk])).status_code,404)
  card.owner=self.user;card.save()
  response=self.client.post(reverse('ptjc_resumes:card_save',args=[card.pk]),json.dumps({'revision':0,'data':{}}),content_type='application/json');self.assertEqual(response.status_code,409)
 def test_card_svg_escapes_customer_text_and_removes_fictional_details(self):
  text=svg(card_normalize({'name':'<script>alert(1)</script>','design':'clinical'}),'front').decode()
  self.assertIn('&lt;script&gt;',text);self.assertNotIn('<script>',text);self.assertNotIn('Alex Morgan',text)
 def test_all_card_designs_are_two_sided_at_print_size(self):
  from pypdf import PdfReader
  for design in ('clinical','community','editorial','networking'):
   reader=PdfReader(BytesIO(pdf(card_normalize({'name':'Alex','design':design}))));self.assertEqual(len(reader.pages),2);self.assertEqual(tuple(reader.pages[0].mediabox[2:]),(252,144))
 def test_card_custom_colours_and_distinct_typeface_export(self):
  from xml.etree import ElementTree
  from pypdf import PdfReader
  data=card_normalize({'name':'Alex Morgan','design':'clinical','typeface':'mono','paper':'#f8f5ea','ink':'#263f33','accent':'#a8b6a0'})
  from .cards import svg
  root=ElementTree.fromstring(svg(data,'front'))
  self.assertEqual(root[0].get('fill'),'#f8f5ea')
  self.assertIn('#a8b6a0',[node.get('fill') for node in root])
  self.assertTrue(any('Courier' in (node.get('font-family') or '') for node in root))
  reader=PdfReader(BytesIO(pdf(data)))
  self.assertTrue(any('Courier' in str(font.get_object().get('/BaseFont')) for font in reader.pages[0]['/Resources']['/Font'].values()))
 def test_shop_separates_audiences(self):
  international=DigitalProduct.objects.create(title='International-only',slug='intl-only',preview_editor='planning-spreadsheet',audience='international',is_published=True)
  canadian=DigitalProduct.objects.create(title='Canadian-only',slug='canadian-only',preview_editor='planning-spreadsheet',audience='canadian',is_published=True)
  response=self.client.get(reverse('mobility_international_shop'));self.assertContains(response,'International-only');self.assertNotContains(response,'Canadian-only')
  response=self.client.get(reverse('mobility_canadian_shop'));self.assertContains(response,'Canadian-only');self.assertNotContains(response,'International-only')
 def test_admin_card_preview_needs_no_candidate_account(self):
  admin=get_user_model().objects.create_superuser('preview-upgrade','admin@example.test','Local-Test-482!');self.client.force_login(admin)
  product=DigitalProduct.objects.get(slug='international-business-card-builder-access');url=reverse('admin:career_mobility_digitalproduct_demo',args=[product.pk])
  self.assertContains(self.client.get(url),'Admin preview')
  response=self.client.post(url+'?side=front',json.dumps({'data':{'name':'Preview only','design':'editorial'}}),content_type='application/json');self.assertEqual(response.status_code,200);self.assertIn(b'Preview only',response.content);self.assertFalse(BusinessCardDraft.objects.exists())
