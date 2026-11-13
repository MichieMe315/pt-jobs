import json
from decimal import Decimal
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from .models import InternationalProfile,DigitalProduct,ProductOrder
from .planning import build
from ptjc_resumes.models import ResumeTemplate,ResumeDraft

@override_settings(ALLOWED_HOSTS=['testserver'])
class RouteClarityTests(TestCase):
 def setUp(self):
  self.user=get_user_model().objects.create_user('australian-candidate',email='australia@example.test')
  self.profile=InternationalProfile.objects.create(user=self.user,country_of_education='Australia',destination_province='New Brunswick',application_history='new',registered_in_education_country='yes',email_verified_at=timezone.now())
 def test_australian_exemption_is_specific_and_scores_are_hidden(self):
  plan=build(self.profile);self.assertTrue(plan['language_exempt']);self.assertIsNone(plan['language_policy']);self.assertFalse(any(x['title'].startswith('Language results') for x in plan['document_tasks']))
  r=self.client.get(reverse('mobility_country',args=['australia']),{'province':'New Brunswick','applied':'not-applied','registration':'yes'})
  self.assertContains(r,'A CAPR language test is not required');self.assertNotContains(r,'IELTS');self.assertContains(r,'Canadian Alliance of Physiotherapy Regulators');self.assertContains(r,'Canadian Physiotherapy Examination');self.assertContains(r,'Complete an approved Canadian healthcare course');self.assertContains(r,'including those educated in Australia');self.assertNotContains(r,'education-country guidance')
 def test_nonexempt_country_keeps_language_score_help(self):
  self.profile.country_of_education='Pakistan';self.profile.save();plan=build(self.profile)
  self.assertFalse(plan['language_exempt']);self.assertIsNotNone(plan['language_policy']);self.assertTrue(any(x['title'].startswith('Language results') for x in plan['document_tasks']))
 def test_budget_displays_one_addition_and_registration_choice(self):
  self.client.force_login(self.user);r=self.client.get(reverse('mobility_international_dashboard'))
  self.assertContains(r,'id="registration-budget-option"');self.assertContains(r,'$3,950.00');self.assertContains(r,'Total: assessment, exam and selected registration');self.assertNotContains(r,'Total of these listed fees')
 def test_product_admin_has_popout_preview_for_draft_product(self):
  admin=get_user_model().objects.create_superuser('preview-admin','admin@example.test','Test-password-482!');self.client.force_login(admin)
  product=DigitalProduct.objects.create(title='Resume product',slug='previewable-builder',price_cad=Decimal('39.99'))
  template=ResumeTemplate.objects.get(key='international-professional');template.access_product=product;template.is_enabled=True;template.save()
  response=self.client.get(reverse('admin:career_mobility_digitalproduct_change',args=[product.pk]));url=reverse('admin:career_mobility_digitalproduct_demo',args=[product.pk])
  self.assertContains(response,url);self.assertContains(response,'target="_blank"');self.assertContains(response,'Open interactive resume builder')
  r=self.client.get(url);self.assertContains(r,'Admin product preview');self.assertContains(r,'Back to product settings');self.assertNotContains(r,'Buy access and unlock PDF')
  from ptjc_resumes.schema import EXAMPLE
  counts=(ResumeDraft.objects.count(),ProductOrder.objects.count())
  r=self.client.post(url,json.dumps({'data':EXAMPLE,'revision':1}),content_type='application/json');self.assertEqual(r.status_code,200)
  pdf=self.client.post(reverse('admin:career_mobility_digitalproduct_demo_pdf',args=[product.pk]),json.dumps({'data':EXAMPLE,'revision':2}),content_type='application/json');self.assertEqual(pdf['Content-Type'],'application/pdf');self.assertTrue(pdf.content.startswith(b'%PDF'))
  self.assertEqual(counts,(ResumeDraft.objects.count(),ProductOrder.objects.count()))
  self.client.force_login(self.user);self.assertEqual(self.client.get(url).status_code,302)
 def test_signup_pre_notice_removed_verification_gate_retained(self):
  response=self.client.get(reverse('mobility_international_signup'));self.assertNotContains(response,'We will email you a verification link before you can use your dashboard.')
  self.profile.email_verified_at=None;self.profile.save();self.client.force_login(self.user)
  self.assertRedirects(self.client.get(reverse('mobility_international_dashboard')),reverse('mobility_verify_pending'))
 def test_copy_update_preserves_admin_prices_publication_and_custom_copy(self):
  from django.apps import apps
  from importlib import import_module
  migration=import_module('ptjc_resumes.migrations.0004_resume_product_copy')
  product=DigitalProduct.objects.get(slug='international-resume-builder-access')
  product.title='My custom resume title';product.description='Owner-written description';product.price_cad=Decimal('31.99');product.is_published=True;product.save()
  migration.update_copy(apps,None);product.refresh_from_db()
  self.assertEqual(product.title,'My custom resume title');self.assertEqual(product.description,'Owner-written description');self.assertEqual(product.price_cad,Decimal('31.99'));self.assertTrue(product.is_published)
