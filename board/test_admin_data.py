import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Employer, Job, JobSeeker


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminDataFlowTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.admin = users.create_superuser('record-admin', 'record-admin@example.test', 'audit-password')
        self.client.force_login(self.admin)
        self.person = users.create_user('candidate-data')
        self.employer = Employer.objects.create(user=users.create_user('employer-data'), company_name='Example Clinic')
        self.candidate = JobSeeker.objects.create(user=self.person, first_name='Taylor')

    def test_lists_have_import_export_and_selectable_registration_column(self):
        for model in ('employer', 'job', 'jobseeker'):
            with self.subTest(model=model):
                page = self.client.get(reverse(f'admin:board_{model}_changelist'))
                for action in ('import', 'export'):
                    self.assertContains(page, reverse(f'admin:board_{model}_{action}'))
                    self.assertEqual(self.client.get(reverse(f'admin:board_{model}_{action}')).status_code, 200)
                self.assertContains(page, 'Apply columns')
        url = reverse('admin:board_jobseeker_changelist')
        self.assertContains(self.client.get(url), self.candidate.created_at.strftime('%b'))
        self.client.post(reverse('admin:board_jobseeker_columns'), {'columns':['registered_at','current_location','nonexistent']})
        page = self.client.get(url)
        self.assertEqual(tuple(page.context['cl'].list_display)[-4:], ('id','approval_status','current_location','registered_at'))

    def test_record_toolbar_preserves_filters_when_columns_change(self):
        url = reverse('admin:board_employer_changelist')
        response = self.client.get(url, {'q': 'Example', 'approval_status': 'pending', 'per_page': 25})
        self.assertContains(response, 'class="pt-grid-toolbar"')
        self.assertContains(response, 'data-admin-filter')
        self.assertEqual(response.context['cl'].list_per_page, 25)
        response = self.client.post(reverse('admin:board_employer_columns'), {
            'columns': ['company_name', 'email'],
            'list_query': 'q=Example&approval_status=pending&per_page=25&o=2&p=2',
        })
        self.assertRedirects(response, url + '?q=Example&approval_status=pending&per_page=25',
                             fetch_redirect_response=False)

    def test_candidate_account_search_and_approval_sort(self):
        users = get_user_model().objects
        self.person.email = 'pending@sorting.example'
        self.person.save(update_fields=['email'])
        approved = JobSeeker.objects.create(
            user=users.create_user('approved-record', email='approved@sorting.example'),
            first_name='Alex', is_approved=True,
        )
        url = reverse('admin:board_jobseeker_changelist')
        response = self.client.get(url, {'q': 'sorting.example'})
        cl = response.context['cl']
        column = cl.list_display.index('approval_status')
        for order, expected in ((str(column), [self.candidate.pk, approved.pk]),
                                (f'-{column}', [approved.pk, self.candidate.pk])):
            response = self.client.get(url, {'q': 'sorting.example', 'o': order})
            self.assertEqual([row.pk for row in response.context['cl'].result_list], expected)
        response = self.client.get(url, {'q': 'sorting.example', 'approval_status': 'pending'})
        self.assertEqual([row.pk for row in response.context['cl'].result_list], [self.candidate.pk])

    def test_employer_lists_show_new_signups_before_recently_edited_old_accounts(self):
        from datetime import timedelta
        from django.utils import timezone

        newest = Employer.objects.create(
            user=get_user_model().objects.create_user('new-employer'),
            company_name='New Clinic', is_approved=True,
        )
        now = timezone.now()
        Employer.objects.filter(pk=self.employer.pk).update(
            created_at=now - timedelta(days=5), updated_at=now,
        )
        Employer.objects.filter(pk=newest.pk).update(
            created_at=now - timedelta(days=1), updated_at=now - timedelta(days=1),
        )
        page = self.client.get(reverse('admin:board_employer_changelist'))
        self.assertEqual([obj.pk for obj in page.context['cl'].result_list], [newest.pk, self.employer.pk])
        url = reverse('admin:operations_records', args=['employers'])
        page = self.client.get(url)
        self.assertEqual([row['id'] for row in page.context['rows']], [newest.pk, self.employer.pk])
        page = self.client.get(url, {'sort': 'created_at'})
        self.assertEqual([row['id'] for row in page.context['rows']], [self.employer.pk, newest.pk])

    def test_exports_contain_selected_records_and_escape_formulas(self):
        self.employer.company_name = '=1+1'
        self.employer.save(update_fields=['company_name'])
        for model, fields in (
            ('employer', ('company_name','user')), ('jobseeker', ('first_name','user')), ('job', ('title','employer')),
        ):
            export = reverse(f'admin:board_{model}_export')
            form = self.client.get(export).context['form']
            choices = {name:'on' for name in form.fields if any(name.endswith('_'+field) for field in fields)}
            result = self.client.post(export, {'format':'0', **choices})
            self.assertIn('attachment', result['Content-Disposition'])
            rows = list(csv.DictReader(StringIO(result.content.decode())))
            if model == 'employer':
                self.assertEqual(rows[0]['company_name'], "'=1+1")
            elif model == 'jobseeker':
                self.assertEqual(rows[0]['first_name'], 'Taylor')

    def test_import_preview_and_confirm_creates_an_inactive_job(self):
        data = f'id,employer,title,description,is_active\n,{self.employer.pk},Example role,Example description,1\n'
        preview = self.client.post(reverse('admin:board_job_import'), {
            'format':'0','import_file':SimpleUploadedFile('jobs.csv',data.encode(),content_type='text/csv'),
        })
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(Job.objects.filter(title='Example role').exists())
        self.assertIsNotNone(preview.context.get('confirm_form'), str(preview.context.get('result') and (preview.context['result'].row_errors(), preview.context['result'].invalid_rows)) + str(preview.context.get('form').errors))
        form = preview.context['confirm_form']
        confirmed = self.client.post(reverse('admin:board_job_process_import'), {
            name: field.value() for name, field in ((name, form[name]) for name in form.fields)
            if field.value() is not None
        })
        self.assertEqual(confirmed.status_code,302)
        self.assertFalse(Job.objects.get(title='Example role').is_active)
