from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from board.models import JobSeeker
from career_mobility.models import ProductOrder
from .models import ResumeDraft
from .schema import CANADIAN_EXAMPLE, normalize


@override_settings(SECURE_SSL_REDIRECT=False)
class CanadianResumeTests(TestCase):
    def test_draft_save_preview_and_paid_download(self):
        user = get_user_model().objects.create_user('canadian-candidate', email='candidate@example.test')
        self.client.force_login(user)
        root = 'ptjc_canadian_resumes:canadian_'
        self.assertEqual(self.client.get(reverse(root + 'index')).status_code, 302)
        JobSeeker.objects.create(user=user, is_approved=True)
        response = self.client.get(reverse(root + 'index'))
        self.assertEqual(response.status_code, 200, response.headers)
        self.assertContains(response, 'Canadian physiotherapy resume builder')
        self.assertEqual(self.client.post(reverse(root + 'create')).status_code, 302)
        draft = ResumeDraft.objects.get(owner=user)
        edit = reverse(root + 'edit', args=[draft.pk])
        data = normalize(CANADIAN_EXAMPLE)
        fields = {k: data[k] for k in ('name', 'email', 'location', 'summary', 'layout')}
        fields['revision'] = 1
        fields['practice_track'] = 'pelvic'
        fields['target_role'] = 'Physiotherapist, pelvic health'
        for key in ('canadian_experience', 'education', 'development'):
            rows = data[key]
            fields[f'{key}-TOTAL_FORMS'] = len(rows)
            fields[f'{key}-INITIAL_FORMS'] = 0
            for i, row in enumerate(rows):
                fields.update({f'{key}-{i}-{k}': v for k, v in row.items()})
        response = self.client.post(edit, fields)
        self.assertEqual(response.status_code, 302, response.context and [(group.errors, group.non_form_errors()) for _, group in response.context['sections']])
        draft.refresh_from_db()
        self.assertEqual(draft.data['name'], data['name'])
        self.assertEqual(draft.data['practice_track'], 'pelvic')
        self.assertEqual(draft.data['target_role'], fields['target_role'])
        self.assertEqual(self.client.get(reverse(root + 'preview', args=[draft.pk]))['Content-Type'], 'application/pdf')
        download = reverse(root + 'download', args=[draft.pk])
        self.assertEqual(self.client.get(download).status_code, 403)
        ProductOrder.objects.create(user=user, product=draft.template.access_product, paid=True, stripe_session_id='cs_canadian_pack')
        self.assertEqual(self.client.get(download)['Content-Type'], 'application/pdf')
