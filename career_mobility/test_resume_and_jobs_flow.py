from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from board.models import JobSeeker
from career_mobility.models import InternationalProfile
from ptjc_resumes.models import ResumeDraft


@override_settings(SECURE_SSL_REDIRECT=False, CAREER_TOOLS_PREVIEW=True)
class CandidateEntryTests(TestCase):
    def test_canadian_guest_draft_claim_and_saved_editor(self):
        canadian = 'ptjc_canadian_resumes:canadian_'
        self.assertContains(self.client.get(reverse(canadian + 'start')), 'id="design-controls"')
        data = {'name': 'Avery Sample', 'layout': 'editorial', 'practice_track': 'pelvic',
                'canadian_experience': [{'role': 'Physiotherapist', 'location': 'Ottawa, ON'}]}
        payload = {'title': 'Pelvic health application', 'revision': 1, 'data': data}
        response = self.client.post(reverse(canadian + 'guest_save'), payload, content_type='application/json')
        self.assertEqual(response.json()['revision'], 2)
        self.assertNotContains(Client().get(reverse(canadian + 'start')), 'Avery Sample')
        self.assertEqual(self.client.post(reverse(canadian + 'guest_preview'))['Content-Type'], 'application/pdf')
        self.assertFalse(ResumeDraft.objects.exists())
        user = get_user_model().objects.create_user('canadian-test')
        JobSeeker.objects.create(user=user, is_approved=True)
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse(canadian + 'claim')), 'Save my resume draft')
        response = self.client.post(reverse(canadian + 'claim'), follow=True)
        self.assertContains(response, 'id="design-controls"')
        draft = ResumeDraft.objects.get(owner=user)
        self.assertEqual(draft.data['layout'], 'editorial')
        self.assertEqual(draft.data['practice_track'], 'pelvic')
        self.assertEqual(draft.data['canadian_experience'][0]['location'], 'Ottawa, ON')
        save_url = reverse(canadian + 'save', args=[draft.pk])
        self.assertEqual(self.client.post(save_url, {**payload, 'data': {**data, 'layout': 'sidebar'}}, content_type='application/json').status_code, 200)
        self.assertEqual(self.client.post(save_url, payload, content_type='application/json').status_code, 409)
        self.assertEqual(self.client.get(reverse(canadian + 'download', args=[draft.pk])).status_code, 403)

    def test_international_planner_has_no_job_board_enrollment(self):
        user = get_user_model().objects.create_user('iept-test', email='iept@example.test')
        InternationalProfile.objects.create(
            user=user, country_of_education='Philippines', destination_province='British Columbia',
            email_verified_at=timezone.now(), email_verified_address=user.email,
        )
        self.client.force_login(user)
        page = self.client.get(reverse('mobility_international_dashboard'))
        self.assertNotContains(page, 'aria-controls="jobs"')
        former_path = '/career-resources/international/jobs/1/apply/'
        self.assertEqual(self.client.post(former_path).status_code, 404)
        self.assertFalse(JobSeeker.objects.filter(user=user).exists())
