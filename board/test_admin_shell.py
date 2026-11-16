from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Employer, Job, Invoice

@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdminShellTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('shell-admin', 'admin@example.test', 'TestOnly123!')
        self.client.force_login(self.user)
        self.employer = Employer.objects.create(user=get_user_model().objects.create_user('clinic'), company_name='Example Clinic', email='clinic@example.test')
        self.job = Job.objects.create(employer=self.employer, title='Physiotherapist', description='Patient care', location='Toronto')

    def test_shell_on_overview_lists_forms_history_and_operations(self):
        for url in ['/admin/', '/admin/board/', '/admin/board/job/', reverse('admin:board_job_change', args=[self.job.pk]), reverse('admin:board_job_history', args=[self.job.pk]), '/admin/operations/', '/admin/operations/duplicates/']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="pt-sidebar"')
                self.assertContains(response, 'class="admin-topbar"')
                self.assertNotContains(response, 'id="header"')
                self.assertContains(response, 'board/ptjc-operations.css')
                self.assertContains(response, 'board/admin-shell.css')
                self.assertContains(response, 'Job Postings')
                self.assertContains(response, 'eCommerce')
        response = self.client.get(reverse('admin:board_job_change', args=[self.job.pk]))
        for value in ['csrfmiddlewaretoken', 'name="_save"', 'admin/js/change_form.js', 'id="id_title"']:
            self.assertContains(response, value)

    def test_navigation_respects_existing_model_permissions(self):
        limited = get_user_model().objects.create_user('limited-shell', is_staff=True)
        limited.user_permissions.add(Permission.objects.get(codename='view_job', content_type__app_label='board'))
        self.client.force_login(limited)
        response = self.client.get('/admin/board/job/')
        self.assertContains(response, 'Job Postings')
        self.assertNotContains(response, 'href="/admin/board/employer/"')
        self.assertNotContains(response, 'href="/admin/board/invoice/"')
        self.assertEqual(self.client.get('/admin/board/employer/').status_code, 403)
        self.assertNotContains(response, 'href="/admin/board/job/add/"')

    def test_popup_keeps_related_widget_workflow_without_sidebar(self):
        response = self.client.get(reverse('admin:board_employer_add'), {'_popup':'1'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'class="pt-sidebar"')
        self.assertContains(response, 'name="_popup"')
        self.assertContains(response, 'csrfmiddlewaretoken')

    def test_admin_reads_do_not_change_customer_records(self):
        from django.apps import apps
        models = list(apps.get_app_config('board').get_models())
        def snapshot():
            return {m._meta.label: list(m.objects.order_by('pk').values()) for m in models}
        before = snapshot()
        for url in ['/admin/', '/admin/operations/', '/admin/operations/duplicates/', '/admin/board/employer/', reverse('admin:board_job_change', args=[self.job.pk])]:
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(before, snapshot())

    def test_existing_form_controls_remain_available(self):
        # Existing complete form handling is exercised by the release suite;
        # the shell must not replace its form action or the original submit buttons.
        response = self.client.get(reverse('admin:board_job_change', args=[self.job.pk]))
        self.assertContains(response, 'id="job_form"')
        for name in ['_save', '_continue', '_addanother']:
            self.assertContains(response, 'name="'+name+'"')

    def test_duplicate_is_unsaved_until_save_and_retains_duration(self):
        from datetime import timedelta
        from django.utils import timezone
        from django.forms import BooleanField
        today = timezone.localdate()
        for duration in [30, 60, 90]:
            self.job.posting_date = today - timedelta(days=120)
            self.job.expiry_date = self.job.posting_date + timedelta(days=duration)
            self.job.is_active = False
            self.job.application_email = "legacy-apply@example.test"
            self.job.views_count = 42
            self.job.save()
            before = Job.objects.filter(pk=self.job.pk).values().get()
            credits = Employer.objects.get(pk=self.employer.pk).credits
            count = Job.objects.count()
            response = self.client.get(reverse('admin:board_job_duplicate', args=[self.job.pk]), follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(Job.objects.count(), count)
            form = response.context['adminform'].form
            self.assertTrue(form.initial['is_active'])
            self.assertEqual(form.initial['expiry_date'], today + timedelta(days=duration))
            self.assertIsNone(form.instance.pk)
            data = {}
            for name, field in form.fields.items():
                value = form[name].value()
                if isinstance(field, BooleanField):
                    if value: data[name] = 'on'
                elif value is not None:
                    data[name] = value.isoformat() if hasattr(value, 'isoformat') else value
            data['_save'] = 'Save'
            saved = self.client.post(response.redirect_chain[-1][0], data)
            self.assertEqual(saved.status_code, 302, getattr(saved, 'context', None))
            self.assertEqual(Job.objects.count(), count + 1)
            duplicate = Job.objects.order_by('-pk').first()
            self.assertTrue(duplicate.is_active)
            self.assertEqual(duplicate.posting_date, today)
            self.assertEqual(duplicate.expiry_date, today + timedelta(days=duration))
            self.assertEqual(duplicate.views_count, 0)
            self.assertEqual(duplicate.application_email, "legacy-apply@example.test")
            self.assertEqual(before, Job.objects.filter(pk=self.job.pk).values().get())
            self.assertEqual(credits, Employer.objects.get(pk=self.employer.pk).credits)

    def test_new_job_expiry_uses_site_posting_duration(self):
        from .models import SiteSettings
        from datetime import timedelta
        from django.utils import timezone
        settings = SiteSettings.objects.create(posting_duration_days=60)
        response = self.client.get(reverse('admin:board_job_add'))
        self.assertEqual(response.context['adminform'].form.initial['expiry_date'], timezone.localdate() + timedelta(days=60))
        self.assertEqual(response.context['admin_posting_duration'], 60)

    def test_duplicate_link_and_save_csrf(self):
        from django.test import Client
        response = self.client.get(reverse('admin:board_job_change', args=[self.job.pk]))
        self.assertContains(response, 'Duplicate job')
        self.assertNotContains(response, 'Create draft copy')
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.user)
        self.assertEqual(secure.post(reverse('admin:board_job_add') + '?duplicate_from=' + str(self.job.pk)).status_code, 403)
        self.assertEqual(Job.objects.count(), 1)

    def test_bulk_action_opens_one_unsaved_copy_and_never_bulk_publishes(self):
        response = self.client.post(reverse('admin:board_job_changelist'), {'action':'duplicate_selected_jobs','_selected_action':[self.job.pk]}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Job.objects.count(), 1)
        self.assertIsNone(response.context['adminform'].form.instance.pk)

    def test_invalid_copy_save_does_not_create_record(self):
        response = self.client.post(reverse('admin:board_job_add') + '?duplicate_from=' + str(self.job.pk), {'title':'', '_save':'Save'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Job.objects.count(), 1)

    def test_dashboard_retains_recent_activity_under_the_new_workspaces(self):
        response = self.client.get('/admin/')
        for heading in ['Recent Job Postings','Recent Orders','Recent Applications','Needs Attention','Quick Management','Today']:
            self.assertContains(response, heading)
        content = response.content.decode().split('<main id="content-start"',1)[1]
        for text in ['Duplicate review','admin-global-search','Open operations','ops-toolbar','All admin controls']:
            self.assertNotIn(text, content)

    def test_dashboard_respects_limited_staff_permissions(self):
        user = get_user_model().objects.create_user('restricted-dashboard', is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_job', content_type__app_label='board'))
        self.client.force_login(user)
        response = self.client.get('/admin/')
        self.assertContains(response,'Recent Job Postings')
        for text in ['Recent Orders','Recent Applications','Revenue · CAD']:
            self.assertNotContains(response,text)


    def test_workspaces_open_and_only_show_authorized_tasks(self):
        for key in ('people','jobs','shop','billing','international','marketing'):
            with self.subTest(key=key):
                url = reverse('admin:task_workspace',args=[key])
                self.assertEqual(self.client.get(url).status_code,200)
        self.assertContains(self.client.get(reverse('admin:task_workspace',args=['people'])),self.employer.company_name)
        self.assertContains(self.client.get(reverse('admin:task_workspace',args=['shop'])), 'Private drafts')
        self.assertEqual(self.client.get(reverse('admin:task_advanced')).status_code,200)
        limited = get_user_model().objects.create_user('workspace-limited',is_staff=True)
        limited.user_permissions.add(Permission.objects.get(codename='view_job',content_type__app_label='board'))
        self.client.force_login(limited)
        self.assertEqual(self.client.get(reverse('admin:task_workspace',args=['shop'])).status_code,403)
        self.assertContains(self.client.get(reverse('admin:task_workspace',args=['jobs'])),'Job postings')

    def test_custom_editors_preserve_record_forms_and_related_permissions(self):
        employer_page = self.client.get(reverse('admin:board_employer_change',args=[self.employer.pk]))
        self.assertContains(employer_page,'pt-editor-grid')
        self.assertContains(employer_page,'id="employer-jobs"')
        self.assertContains(employer_page,'id="employer-purchases"')
        self.assertContains(employer_page,'Add job for this employer')
        job = self.client.get(reverse('admin:board_job_change',args=[self.job.pk]))
        self.assertContains(job,'International candidates')
        self.assertContains(job,'id="job_form"')
        rows = self.client.get(reverse('admin:operations_records',args=['jobs']),{'per_page':50})
        self.assertContains(rows,'Rows per page')
        self.assertEqual(rows.context['page_obj'].paginator.per_page,50)
        self.assertEqual(self.client.get(reverse('admin:operations_records',args=['jobs'])).context['page_obj'].paginator.per_page,50)

    def test_shared_admin_layout_covers_lists_settings_history_and_confirmations(self):
        from django.contrib.auth.models import Group
        group=Group.objects.create(name='Temporary QA group')
        for url, marker in (
            (reverse('admin:auth_group_changelist'),'pt-list-body'),
            (reverse('admin:auth_group_change',args=[group.pk]),'pt-editor-actions'),
            (reverse('admin:auth_group_history',args=[group.pk]),'Change history'),
            (reverse('admin:auth_group_delete',args=[group.pk]),'Review what will be deleted'),
            (reverse('admin:board_job_import'),'Preview import'),
            (reverse('admin:board_job_export'),'Download export'),
            (reverse('admin:password_change'),'Save new password'),
            (reverse('admin:auth_user_password_change',args=[self.user.pk]),'Password access'),
            (reverse('admin:task_advanced'),'pt-model-directory'),
        ):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url),marker)
        bulk=self.client.post(reverse('admin:auth_group_changelist'),{
            'action':'delete_selected','_selected_action':group.pk,'index':0,
        })
        self.assertContains(bulk,'Delete selected records')
        self.assertTrue(Group.objects.filter(pk=group.pk).exists())
        self.client.logout()
        self.assertContains(self.client.get(reverse('admin:login')),'Staff sign in')

    def test_review_queue_can_approve_and_return_to_the_queue(self):
        self.employer.is_approved=False
        self.employer.save(update_fields=['is_approved'])
        queue=reverse('admin:profile_review_queue')+'?kind=employers'
        approval=reverse('admin:board_employer_approve_profile',args=[self.employer.pk])
        self.assertContains(self.client.get(queue),approval)
        self.assertEqual(self.client.get(approval).status_code,405)
        self.assertRedirects(self.client.post(approval,{'return_to':'review'}),queue)
        self.employer.refresh_from_db()
        self.assertTrue(self.employer.is_approved)
        self.assertNotContains(self.client.get(queue),approval)

    def test_admin_publish_uses_saved_job_and_does_not_consume_credits(self):
        from .models import JobPublicationRequest
        self.employer.is_approved=True
        self.employer.credits=2
        self.employer.save(update_fields=['is_approved','credits'])
        self.job.is_active=False
        self.job.save(update_fields=['is_active'])
        url=reverse('admin:board_job_publish_saved',args=[self.job.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        waiting=JobPublicationRequest.objects.create(job=self.job,employer=self.employer,fingerprint='test',status='waiting')
        self.assertEqual(self.client.post(url).status_code,302)
        self.job.refresh_from_db()
        self.assertFalse(self.job.is_active)
        waiting.status='cancelled'
        waiting.save(update_fields=['status'])
        self.assertEqual(self.client.post(url).status_code,302)
        self.job.refresh_from_db()
        self.employer.refresh_from_db()
        self.assertTrue(self.job.is_active)
        self.assertEqual(self.employer.credits,2)

    def test_ptjc_navigation_order_and_data_tools(self):
        dashboard = self.client.get('/admin/').content.decode()
        nav = dashboard.split('<nav id="admin-navigation">', 1)[1].split('</nav>', 1)[0]
        expected = ['Dashboard', 'Review accounts', 'Job Board', 'Job Postings', 'Employer Profiles',
                    'Resumes', 'Job Seeker Profiles', 'Applications', 'Job Alerts', 'Appearance',
                    'Content', 'eCommerce', 'Digital products', 'Résumé builders', 'Job posting packages', 'Reports', 'Import &amp; Export',
                    'Listing Fields', 'Email Marketing', 'Affiliates', 'Email Logs', 'Email Templates', 'Settings', 'Career tools', 'International']
        offsets = [nav.index('>' + label + '<') for label in expected]
        self.assertEqual(offsets, sorted(offsets))
        for model in ('job', 'employer', 'jobseeker'):
            response = self.client.get(reverse('admin:data_tools'))
            for action in ('import', 'export'):
                self.assertContains(response, reverse(f'admin:board_{model}_{action}'))

    def test_job_list_status_tabs_filter_existing_records(self):
        from datetime import timedelta
        from django.utils import timezone
        self.job.expiry_date = timezone.localdate() - timedelta(days=1)
        self.job.save(update_fields=['expiry_date'])
        url = reverse('admin:board_job_changelist')
        response = self.client.get(url, {'posting_status': 'expired', 'q': self.job.title})
        self.assertContains(response, 'aria-current="page">Expired</a>')
        self.assertEqual(list(response.context['cl'].result_list), [self.job])
        self.assertEqual(list(self.client.get(url, {'posting_status': 'active'}).context['cl'].result_list), [])

    def test_sidebar_destinations_open_and_reports_keep_staff_boundaries(self):
        from html import unescape
        import re
        dashboard = self.client.get('/admin/').content.decode()
        nav = dashboard.split('<nav id="admin-navigation">', 1)[1].split('</nav>', 1)[0]
        for url in re.findall(r'href="([^"]+)"', nav):
            with self.subTest(url=url):
                self.assertContains(self.client.get(unescape(url)), 'class="pt-sidebar"')
        user = get_user_model().objects.create_user('report-staff', is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_job', content_type__app_label='board'))
        self.client.force_login(user)
        report = self.client.get(reverse('admin_dashboard'), {'period': 'custom', 'start': '2020-01-01', 'end': '2020-02-01'})
        self.assertContains(report, 'Jobs posted')
        self.assertNotContains(report, 'Recent Paid Orders')
        self.assertNotContains(report, 'New employers')
        data_tools = self.client.get(reverse('admin:data_tools'))
        self.assertContains(data_tools, reverse('admin:board_job_export'))
        self.assertNotContains(data_tools, reverse('admin:board_job_import'))
        self.assertNotContains(data_tools, reverse('admin:board_employer_export'))
