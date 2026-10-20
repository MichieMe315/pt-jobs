import csv
import io
import json
import re
from datetime import timedelta
from unittest.mock import patch
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, RequestFactory, override_settings
from django.urls import reverse, resolve, Resolver404
from django.utils import timezone
from .models import Employer, JobSeeker, Job, Invoice, PurchasedPackage, PostingPackage, JobAlert, Resume, Application, SiteSettings
from .operations import RECORDS, duplicate_queryset
from .seo_pages import PAGES, matching_jobs
from .templatetags.pt_seo import job_schema


@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdminWorkspaceTests(TestCase):
    def setUp(self):
        self.staff=get_user_model().objects.create_superuser('admin','admin@example.test','TestOnly123!')
        self.client.force_login(self.staff)
        self.employer=self.make_employer('North Clinic','owner@northclinic.test',location='Toronto, ON',is_approved=True)
        self.job=Job.objects.create(employer=self.employer,title='Physiotherapist',description='Patient care',location='Toronto, ON')
    def make_employer(self, name, email, **kwargs):
        user=get_user_model().objects.create_user('employer'+str(get_user_model().objects.count()))
        return Employer.objects.create(user=user,company_name=name,email=email,**kwargs)
    def staff_with(self, *permissions):
        user=get_user_model().objects.create_user('limited',is_staff=True)
        user.user_permissions.set(Permission.objects.filter(codename__in=permissions,content_type__app_label='board'))
        self.client.force_login(user);return user
    def test_admin_index_and_workspace_keep_model_directory_and_existing_reports(self):
        for url in ['/admin/','/admin/operations/']:
            response=self.client.get(url);self.assertEqual(response.status_code,200)
            for value in ['Search','Marketing graphics','Date-based business report']:
                self.assertContains(response,value)
        self.assertContains(self.client.get('/admin/'),'Recent Job Postings')
    def test_all_record_lists_and_csv_render(self):
        for kind in RECORDS:
            with self.subTest(kind=kind):
                self.assertEqual(self.client.get(f'/admin/operations/{kind}/').status_code,200)
                self.assertEqual(self.client.get(f'/admin/operations/{kind}/?export=csv').status_code,200)
    def test_every_existing_board_admin_list_and_search_still_work(self):
        for model in admin.site._registry:
            if model._meta.app_label!='board':continue
            url=reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist')
            for suffix in ['', '?q=North']:
                with self.subTest(model=model.__name__,suffix=suffix):self.assertEqual(self.client.get(url+suffix).status_code,200)
    def test_existing_employer_job_and_billing_forms_render(self):
        package=PostingPackage.objects.create(code='test',name='Test',price_cents=9900)
        purchased=PurchasedPackage.objects.create(employer=self.employer,package=package)
        invoice=Invoice.objects.create(employer=self.employer,amount=9900)
        for obj in [self.employer,self.job,package,purchased,invoice]:
            self.assertEqual(self.client.get(reverse(f'admin:board_{obj._meta.model_name}_change',args=[obj.pk])).status_code,200)
    def test_existing_approval_and_duplicate_actions_available(self):
        employer=self.client.get('/admin/board/employer/').context['cl'].model_admin
        job=self.client.get('/admin/board/job/').context['cl'].model_admin
        request=RequestFactory().get('/admin/');request.user=self.staff
        self.assertIn('approve_selected_employers',employer.get_actions(request))
        self.assertIn('duplicate_selected_jobs',job.get_actions(request))
    def test_employer_bulk_approval_still_sends_existing_notification(self):
        pending=self.make_employer('Pending clinic','pending@clinic.test')
        with patch('board.admin._send_employer_approved_email',return_value=True) as send:
            response=self.client.post('/admin/board/employer/',{'action':'approve_selected_employers','_selected_action':[pending.pk]})
        self.assertEqual(response.status_code,302)
        pending.refresh_from_db();self.assertTrue(pending.is_approved);self.assertTrue(pending.login_active)
        send.assert_called_once()
    def test_global_search_finds_employer_email_and_invoice_reference(self):
        Invoice.objects.create(employer=self.employer,amount=9900,processor_reference='cs_North_123')
        self.assertContains(self.client.get('/admin/operations/search/?q=northclinic.test'),'North Clinic')
        self.assertContains(self.client.get('/admin/operations/search/?q=cs_North_123'),'Invoices')
    def test_record_id_search_in_workspace_and_standard_admin(self):
        for url in ['/admin/operations/employers/','/admin/board/employer/']:
            response=self.client.get(url,{'q':'#'+str(self.employer.pk)})
            self.assertContains(response,'North Clinic')
        self.assertContains(self.client.get('/admin/operations/employers/',{'q':'#'+'9'*100}),'No matching records')
    def test_multiword_search_matches_across_fields(self):
        response=self.client.get('/admin/operations/employers/',{'q':'North Toronto'})
        self.assertContains(response,'North Clinic')
    def test_search_does_not_bypass_filters(self):
        self.assertNotContains(self.client.get('/admin/operations/employers/',{'q':'#'+str(self.employer.pk),'status':'pending'}),'Open #'+str(self.employer.pk))
    def test_pending_and_disabled_are_separate(self):
        pending=self.make_employer('Pending only','pending@clinic.test')
        disabled=self.make_employer('Disabled only','disabled@clinic.test',login_active=False)
        response=self.client.get('/admin/operations/employers/?status=pending')
        self.assertContains(response,'Pending only');self.assertNotContains(response,'Disabled only')
    def test_missing_description_checks_both_existing_description_fields(self):
        self.employer.description='Legacy description';self.employer.save()
        response=self.client.get('/admin/operations/employers/?quality=missing-description')
        self.assertNotContains(response,'Open #'+str(self.employer.pk))
    def test_quality_filters_match_blank_whitespace(self):
        self.employer.company_description='  ';self.employer.location='  ';self.employer.save()
        for quality in ['missing-description','missing-location','missing-logo']:
            self.assertContains(self.client.get('/admin/operations/employers/',{'quality':quality}),'Open #'+str(self.employer.pk))
    def test_date_range_is_inclusive_for_posting_date(self):
        today=timezone.localdate().isoformat()
        self.assertContains(self.client.get('/admin/operations/jobs/',{'start':today,'end':today}),self.job.title)
    def test_invalid_dates_and_statuses_do_not_export_wrong_records(self):
        for values in [{'start':'not-a-date'},{'start':'2026-12-02','end':'2026-01-01'},{'status':'not-valid'},{'end':'9999-12-31'}]:
            response=self.client.get('/admin/operations/jobs/',values)
            self.assertEqual(response.status_code,200);self.assertTrue(response.context['filter_form'].errors)
            self.assertEqual(self.client.get('/admin/operations/jobs/',{**values,'export':'csv'}).status_code,400)
    def test_csv_only_exports_filtered_rows_and_escapes_spreadsheet_formulas(self):
        self.make_employer('=EVIL','formula@clinic.test')
        response=self.client.get('/admin/operations/employers/',{'q':'formula','export':'csv'})
        rows=list(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows),2);self.assertIn("'=EVIL",rows[1]);self.assertNotIn('North Clinic',response.content.decode())
    def test_billing_dollars_and_original_csv_cents(self):
        Invoice.objects.create(employer=self.employer,amount=9900)
        self.assertContains(self.client.get('/admin/operations/billing/'),'CAD 99.00')
        self.assertContains(self.client.get('/admin/operations/billing/?export=csv'),'9900')
    def test_sort_and_pagination_preserve_all_filters(self):
        for i in range(32):self.make_employer(f'Other Clinic {i}','other@clinic.test')
        response=self.client.get('/admin/operations/employers/',{'q':'Clinic','quality':'missing-logo','status':'pending','start':'2020-01-01'})
        self.assertTrue(response.context['page_obj'].has_next())
        self.assertIn('quality=missing-logo',response.context['next_query'])
        self.assertIn('start=2020-01-01',response.context['next_query'])
    def test_email_duplicates_ignore_case_spaces_and_blank_values(self):
        self.make_employer('Second clinic',' OWNER@NORTHCLINIC.TEST ')
        self.make_employer('Blank 1','');self.make_employer('Blank 2',' ')
        response=self.client.get('/admin/operations/duplicates/?kind=employer-email')
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertContains(response,'North Clinic');self.assertContains(response,'Second clinic')
    def test_duplicate_company_names_are_review_only(self):
        self.make_employer(' north clinic ','other@clinic.test')
        before=list(Employer.objects.values_list('pk','is_approved','credits'))
        response=self.client.get('/admin/operations/duplicates/?kind=employer-name')
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertEqual(list(Employer.objects.values_list('pk','is_approved','credits')),before)
        self.assertNotContains(response,'Compare possible duplicates without changing accounts, jobs or payments.')
        self.assertEqual(Employer.objects.count(),2)
    def test_domain_duplicates_exclude_personal_mail_providers(self):
        self.make_employer('Business B','two@northclinic.test')
        self.make_employer('Gmail A','a@gmail.com');self.make_employer('Gmail B','b@gmail.com')
        response=self.client.get('/admin/operations/duplicates/?kind=employer-domain')
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertEqual(response.context['groups'][0]['key'],'northclinic.test')
    def test_job_duplicate_review_requires_same_employer_title_and_location(self):
        Job.objects.create(employer=self.employer,title=' physiotherapist ',location=' toronto, on ')
        Job.objects.create(employer=self.employer,title='Physiotherapist',location='Vancouver, BC')
        other=self.make_employer('Another clinic','another@clinic.test')
        Job.objects.create(employer=other,title='Physiotherapist',location='Toronto, ON')
        response=self.client.get('/admin/operations/duplicates/?kind=job-title')
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertEqual(response.context['groups'][0]['count'],2)
        self.assertEqual(Job.objects.count(),4)
    def test_candidate_duplicates_stay_separate_from_employers(self):
        for i in range(2):
            user=get_user_model().objects.create_user('candidate'+str(i))
            JobSeeker.objects.create(user=user,email='duplicate@example.test')
        response=self.client.get('/admin/operations/duplicates/?kind=candidate-email')
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertNotContains(response,'North Clinic')
    def test_invoice_reference_duplicates_preserve_case_and_processor(self):
        for processor,reference in [('stripe','cs_Same'),('stripe','cs_Same'),('paypal','cs_Same'),('stripe','cs_same')]:
            Invoice.objects.create(employer=self.employer,processor=processor,processor_reference=reference)
        response=self.client.get('/admin/operations/duplicates/?kind=invoice-reference')
        self.assertEqual(response.context['page_obj'].paginator.count,1)
        self.assertEqual(response.context['groups'][0]['count'],2)
    def test_unprivileged_staff_cannot_view_search_counts_exports_or_duplicates(self):
        self.staff_with()
        self.assertNotContains(self.client.get('/admin/operations/'),'Employer approvals')
        self.assertNotContains(self.client.get('/admin/operations/search/?q=North'),'North Clinic')
        self.assertEqual(self.client.get('/admin/operations/employers/').status_code,403)
        self.assertEqual(self.client.get('/admin/operations/employers/?export=csv').status_code,403)
        self.assertEqual(self.client.get('/admin/operations/duplicates/').status_code,403)
    def test_employer_only_permission_does_not_expose_candidates_or_billing(self):
        self.staff_with('view_employer')
        self.assertEqual(self.client.get('/admin/operations/employers/').status_code,200)
        for kind in ['candidate-email','invoice-reference']:
            self.assertEqual(self.client.get('/admin/operations/duplicates/',{'kind':kind}).status_code,403)
        self.assertEqual(self.client.get('/admin/operations/billing/').status_code,403)
    def test_anonymous_and_nonstaff_cannot_open_workspace(self):
        self.client.logout();self.assertEqual(self.client.get('/admin/operations/').status_code,302)
        self.client.force_login(self.employer.user);self.assertEqual(self.client.get('/admin/operations/').status_code,302)
    def test_duplicate_job_opens_unsaved_copy_without_credit_use(self):
        before=self.employer.credits
        response=self.client.get(reverse('admin:board_job_duplicate',args=[self.job.pk]),follow=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(Job.objects.count(),1)
        self.assertTrue(response.context['adminform'].form.initial['is_active'])
        self.assertIsNone(response.context['adminform'].form.instance.pk)
        self.employer.refresh_from_db();self.assertEqual(self.employer.credits,before)
    def test_view_only_staff_cannot_duplicate_job(self):
        self.staff_with('view_job')
        path=reverse('admin:board_job_duplicate',args=[self.job.pk])
        self.assertEqual(self.client.get(path).status_code,403)
        self.assertEqual(self.client.post(path).status_code,403)
        self.assertEqual(Job.objects.count(),1)
    def test_unknown_record_or_duplicate_kind_returns_404(self):
        self.assertEqual(self.client.get('/admin/operations/unknown/').status_code,404)
        self.assertEqual(self.client.get('/admin/operations/duplicates/?kind=unknown').status_code,404)


@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SEOReleaseTests(TestCase):
    def setUp(self):
        u=get_user_model().objects.create_user('clinic')
        self.employer=Employer.objects.create(user=u,company_name='Clinic Test',location='Toronto, ON',is_approved=True)
    def job(self, **kwargs):
        values={'employer':self.employer,'title':'Physiotherapist','description':'Assess and treat patients safely.','location':'Toronto, ON, Canada','expiry_date':timezone.localdate()+timedelta(days=10)}
        values.update(kwargs);return Job.objects.create(**values)
    def test_all_twelve_landings_render_and_have_one_canonical(self):
        self.assertEqual(len(PAGES),12)
        for slug in PAGES:
            path=reverse('career_landing',args=[slug]);response=self.client.get(path)
            self.assertEqual(response.status_code,200);self.assertContains(response,'No current matches')
            self.assertEqual(response.content.decode().count('rel="canonical"'),1)
            self.assertContains(response,'https://www.physiotherapyjobscanada.ca'+path)
    def test_sitemap_host_matches_canonical_from_any_request_host(self):
        job=self.job();response=self.client.get('/sitemap.xml')
        self.assertNotContains(response,'testserver');self.assertContains(response,f'https://www.physiotherapyjobscanada.ca/jobs/{job.pk}/')
        for slug in PAGES:self.assertContains(response,reverse('career_landing',args=[slug]))
    def test_sitemap_excludes_expired_and_drafts(self):
        expired=self.job(expiry_date=timezone.localdate()-timedelta(days=1));draft=self.job(is_active=False)
        response=self.client.get('/sitemap.xml')
        for job in [expired,draft]:self.assertNotContains(response,f'/jobs/{job.pk}/')
    def test_schema_is_valid_and_escapes_script_content(self):
        job=self.job(description='Patient care </script><script>alert(1)</script>')
        response=self.client.get(f'/jobs/{job.pk}/')
        scripts=re.findall(r'<script type="application/ld\+json">(.*?)</script>',response.content.decode(),re.S)
        data=next(json.loads(x) for x in scripts if json.loads(x).get('@type')=='JobPosting')
        self.assertEqual(data['jobLocation']['address']['addressRegion'],'ON')
        self.assertNotIn('</script><script>alert(1)', ''.join(scripts))
    def test_split_not_rendered_as_salary_or_fake_location(self):
        job=self.job(compensation_type='split',compensation_min=55,compensation_max=70)
        self.assertNotIn('baseSalary',job_schema(job))
        job.location='Unspecified';self.assertIsNone(job_schema(job))
    def test_expired_and_inactive_have_no_job_schema(self):
        for job in [self.job(expiry_date=timezone.localdate()-timedelta(days=1)),self.job(is_active=False)]:self.assertIsNone(job_schema(job))
    def test_search_and_private_pages_noindex(self):
        self.assertContains(self.client.get('/jobs/?q=locum'),'noindex,follow')
        self.assertContains(self.client.get('/login/'),'noindex,follow')
        self.assertContains(self.client.get('/job-alerts/signup/'),'noindex,follow')
    def test_home_preserves_admin_hero_and_uses_existing_seo_fields(self):
        SiteSettings.objects.create(hero_title='Our original hero',seo_meta_title='Configured SEO title',seo_meta_description='Configured search description')
        response=self.client.get('/')
        for text in ['Our original hero','Configured SEO title','Configured search description']:self.assertContains(response,text)
    def test_city_matches_province_and_excludes_unrelated_professions(self):
        good=self.job(location='London, ON, Canada')
        self.job(location='London, UK');self.job(location='New London, PE, Canada');self.job(title='Chiropractor',location='London, ON')
        self.assertEqual(list(matching_jobs(PAGES['physiotherapy-jobs-london']).values_list('pk',flat=True)),[good.pk])
    def test_topics_match_actual_current_listings(self):
        good=self.job(title='Locum Physiotherapist',job_type='locum')
        self.job(title='Locum Chiropractor',job_type='locum');self.job(title='Expired Locum Physiotherapist',job_type='locum',expiry_date=timezone.localdate()-timedelta(days=1))
        self.assertEqual(list(matching_jobs(PAGES['locum-physiotherapy-jobs-canada']).values_list('pk',flat=True)),[good.pk])
    def test_employer_dashboard_still_original_no_hiring_tools(self):
        self.client.force_login(self.employer.user)
        response=self.client.get('/employer/dashboard/')
        self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'Job description writer');self.assertNotContains(response,'pt-tools-grid')
        self.assertNotContains(self.client.get('/physiotherapy-careers/'),'Open employer tools')
    def test_held_back_tools_routes_not_added(self):
        with self.assertRaises(Resolver404):resolve('/employer/tools/job-description/')
    def test_existing_employer_view_on_site_link_now_resolves(self):
        self.assertEqual(self.employer.get_absolute_url(),f'/employers/{self.employer.pk}/')
        self.assertEqual(self.client.get(self.employer.get_absolute_url()).status_code,200)
    def test_province_metadata_has_single_canonical(self):
        response=self.client.get('/physiotherapy-jobs-ontario/')
        self.assertEqual(response.status_code,200);self.assertEqual(response.content.decode().count('rel="canonical"'),1)

    def test_sports_collection_does_not_match_transportation(self):
        good=self.job(title='Sports Physiotherapist')
        self.job(title='Physiotherapist',description='Transportation allowance is provided.')
        self.assertEqual(list(matching_jobs(PAGES['sports-physiotherapy-jobs-canada']).values_list('pk',flat=True)),[good.pk])
    def test_physiology_role_is_not_a_physiotherapist_match(self):
        good=self.job(title='Physiotherapist',location='London, ON')
        self.job(title='Physiology researcher',location='London, ON')
        self.assertEqual(list(matching_jobs(PAGES['physiotherapy-jobs-london']).values_list('pk',flat=True)),[good.pk])
