import csv,io
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from board.models import Employer,Job,Invoice,EmployerMarketingProfile,MarketingAudience,MarketingDraft,MarketingSuppression
from board.marketing.contacts import annotate_employers,exportable
from board.marketing.bulk_actions import mark_rural,mark_clinics
from django.contrib import admin

class MarketingWorkspaceTests(TestCase):
 def setUp(self):
  U=get_user_model();self.admin=U.objects.create_superuser('marketing-admin','admin@example.test','Test-password-482!')
  self.client.force_login(self.admin)
  self.rural=self.employer('Rural Clinic','rural@example.test','Moosonee, ON, Canada')
  self.urban=self.employer('City Clinic','urban@example.test','Toronto, Ontario')
  self.unknown=self.employer('Unclassified','unknown@example.test','Grande Prairie, Alberta')
  self.profile=EmployerMarketingProfile.objects.create(employer=self.rural,settlement='remote',organization_type='clinic',contact_status='ready',outreach_basis='Existing clinic relationship recorded for this test.')
 def employer(self,name,email,location):
  u=get_user_model().objects.create_user(username=email,email=email)
  return Employer.objects.create(user=u,company_name=name,email=email,location=location,is_approved=True)
 def test_province_aliases_and_city_sort_use_existing_location(self):
  qs=annotate_employers(Employer.objects.all())
  self.assertEqual(qs.get(pk=self.rural.pk)._marketing_province,'Ontario')
  self.assertEqual(qs.get(pk=self.urban.pk)._marketing_city,'Toronto')
  self.assertEqual(qs.get(pk=self.unknown.pk)._marketing_province,'Alberta')
  r=self.client.get(reverse('admin:marketing_contacts'),{'province':'ON','sort':'_marketing_city'})
  self.assertEqual([x['employer'].pk for x in r.context['rows']],[self.rural.pk,self.urban.pk])
 def test_rural_is_explicit_not_inferred_from_research_coverage(self):
  r=self.client.get(reverse('admin:marketing_contacts'),{'community':'rural_remote','organization':'clinic'})
  self.assertEqual([x['employer'].pk for x in r.context['rows']],[self.rural.pk])
  self.assertFalse(EmployerMarketingProfile.objects.filter(employer=self.unknown).exists())
 def test_exports_dedupe_and_exclude_unreviewed_blocked_and_disabled(self):
  duplicate=self.employer('Same address','RURAL@EXAMPLE.TEST','Another place, ON')
  EmployerMarketingProfile.objects.create(employer=duplicate,contact_status='ready',outreach_basis='Test basis')
  rows=list(exportable(Employer.objects.all().order_by('pk')))
  self.assertEqual([email for _,email in rows],['rural@example.test'])
  MarketingSuppression.objects.create(email='RURAL@example.test',reason='unsubscribed')
  self.assertEqual(list(exportable(Employer.objects.all())),[])
 def test_block_on_duplicate_profile_blocks_same_address(self):
  duplicate=self.employer('Do not email duplicate','RURAL@EXAMPLE.TEST','Another place, ON')
  EmployerMarketingProfile.objects.create(employer=duplicate,contact_status='do_not_email')
  self.assertEqual(list(exportable(Employer.objects.all())),[])
 def test_outreach_approval_requires_recorded_basis(self):
  p=EmployerMarketingProfile(employer=self.urban,contact_status='ready')
  with self.assertRaises(ValidationError):p.full_clean()
 def test_save_audience_exact_filters_without_sending(self):
  before=len(mail.outbox)
  r=self.client.post(reverse('admin:marketing_contacts'),{'community':'rural_remote','organization':'clinic','audience_name':'Rural relocation launch'})
  self.assertEqual(r.status_code,302)
  audience=MarketingAudience.objects.get(name='Rural relocation launch')
  self.assertEqual(list(audience.employers.values_list('pk',flat=True)),[self.rural.pk])
  self.assertEqual(before,len(mail.outbox))
 def test_invalid_filters_cannot_save_or_export_everyone(self):
  r=self.client.post(reverse('admin:marketing_contacts'),{'community':'invented','audience_name':'Wrong'})
  self.assertEqual(r.status_code,200);self.assertFalse(MarketingAudience.objects.filter(name='Wrong').exists())
  self.assertEqual(self.client.get(reverse('admin:marketing_contacts'),{'province':'invalid','export':'csv'}).status_code,400)
 def test_draft_preview_escapes_content_and_sends_nothing(self):
  audience=MarketingAudience.objects.create(name='Selected rural clinics');audience.employers.add(self.rural)
  draft=MarketingDraft.objects.create(name='Relocation launch',audience=audience,subject='Plan your next hire',body='<script>alert(1)</script>\nRural recruitment update')
  before=len(mail.outbox)
  response=self.client.get(reverse('admin:marketing_draft_preview',args=[draft.pk]))
  self.assertContains(response,'&lt;script&gt;');self.assertNotContains(response,'<script>');self.assertEqual(before,len(mail.outbox))
 def test_native_admin_search_filters_sort_and_bulk_classification(self):
  adminobj=admin.site._registry[Employer]
  from django.test import RequestFactory
  request=RequestFactory().post('/admin/board/employer/');request.user=self.admin
  mark_rural(adminobj,request,Employer.objects.filter(pk=self.urban.pk));mark_clinics(adminobj,request,Employer.objects.filter(pk=self.urban.pk))
  r=self.client.get(reverse('admin:board_employer_changelist'),{'q':'City Clinic','community':'rural','province':'ON'})
  self.assertContains(r,'City Clinic');self.assertNotContains(r,'Rural Clinic')
  self.assertEqual(Employer.objects.get(pk=self.urban.pk).location,'Toronto, Ontario')
 def test_view_permissions_do_not_grant_exports_or_audience_writes(self):
  u=get_user_model().objects.create_user('limited-marketing',is_staff=True)
  u.user_permissions.add(Permission.objects.get(codename='view_employer',content_type__app_label='board'));self.client.force_login(u)
  self.assertEqual(self.client.get(reverse('admin:marketing_contacts')).status_code,200)
  self.assertEqual(self.client.get(reverse('admin:marketing_contacts'),{'export':'csv'}).status_code,403)
  self.assertEqual(self.client.post(reverse('admin:marketing_contacts'),{'audience_name':'Unauthorized'}).status_code,403)
 def test_formula_safe_csv(self):
  self.rural.company_name='=HYPERLINK("test")';self.rural.save()
  r=self.client.get(reverse('admin:marketing_contacts'),{'export':'csv'})
  rows=list(csv.reader(io.StringIO(r.content.decode('utf-8-sig'))))
  self.assertTrue(rows[1][1].startswith("'="))
 def test_route_submit_starts_at_top_with_plain_registration_explanation(self):
  r=self.client.get(reverse('mobility_international'),{'build':'1','country':'Australia','province':'New Brunswick','applied':'not-applied','registration':'yes'})
  self.assertNotIn('#',r.url)
  page=self.client.get(r.url)
  self.assertContains(page,'ASSESSMENT PATHWAY');self.assertContains(page,'current registration there with no restrictions')

 def test_last_payment_sort_and_job_counts_do_not_multiply_across_joins(self):
  Invoice.objects.create(employer=self.rural,status='paid',order_date=timezone.now()-timedelta(days=20),amount=7500)
  Invoice.objects.create(employer=self.rural,status='paid',order_date=timezone.now()-timedelta(days=5),amount=7500)
  Invoice.objects.create(employer=self.urban,status='paid',order_date=timezone.now()-timedelta(days=1),amount=7500)
  Job.objects.create(employer=self.rural,title='Test PT',location='Moosonee, ON',is_active=True,posting_date=timezone.localdate(),expiry_date=timezone.localdate()+timedelta(days=10))
  r=self.client.get(reverse('admin:marketing_contacts'),{'sort':'-_last_paid'})
  self.assertEqual([x['employer'].pk for x in r.context['rows']],[self.urban.pk,self.rural.pk,self.unknown.pk])
  self.assertEqual(annotate_employers(Employer.objects.filter(pk=self.rural.pk)).get()._active_jobs,1)

 def test_scan_fills_supported_matches_and_preserves_reviewed_records(self):
  from board.marketing.classify import classify_employers
  self.urban.company_description = 'Located in an urban community.'
  self.urban.save(update_fields=['company_description'])
  self.assertGreater(classify_employers()['matched'], 0)
  self.assertFalse(EmployerMarketingProfile.objects.filter(employer=self.urban).exists())
  classify_employers(apply=True)
  profile = EmployerMarketingProfile.objects.get(employer=self.urban)
  self.assertEqual((profile.city, profile.province, profile.organization_type, profile.settlement), ('Toronto', 'ON', 'clinic', 'urban'))
  self.assertNotEqual(profile.contact_status, 'ready')
  self.profile.refresh_from_db()
  self.assertEqual((self.profile.settlement, self.profile.contact_status), ('remote', 'ready'))
  self.assertEqual(classify_employers()['matched'], 0)

 def test_registered_admin_lists_load_and_employer_shows_one_toolbar(self):
  for model in admin.site._registry:
   with self.subTest(model=model._meta.label):
    response = self.client.get(reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist'))
    self.assertEqual(response.status_code, 200)
    if model is Employer:
     self.assertContains(response, '<div class="actions">', count=1)
     self.assertContains(response, 'Location')
