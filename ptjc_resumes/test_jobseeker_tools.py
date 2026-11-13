import base64
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from board.models import JobSeeker
from .cards import normalize, pdf
from .models import BusinessCardDraft


class JobSeekerToolsTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username='local-jobseeker', first_name='Morgan')
        JobSeeker.objects.create(user=user, is_approved=True, login_active=True)
        self.client.force_login(user)

    def test_resume_draft_is_listed_in_jobseeker_profile(self):
        response = self.client.post(reverse('ptjc_canadian_resumes:canadian_create'))
        self.assertTrue(response.url.startswith('/jobseeker/tools/resume/'))
        self.assertContains(self.client.get(response.url), 'navbar-brand')
        dashboard = self.client.get(reverse('jobseeker_dashboard'))
        self.assertContains(dashboard, response.url)
        self.assertContains(dashboard, reverse('jobseeker_cards:cards'))

    def test_card_artwork_round_trip_and_print_export(self):
        response = self.client.post(reverse('jobseeker_cards:card_create'))
        draft = BusinessCardDraft.objects.get()
        self.assertContains(self.client.get(response.url), 'id="art-back"')
        png = BytesIO()
        Image.new('RGB', (50, 35), 'purple').save(png, 'PNG')
        art = 'data:image/png;base64,' + base64.b64encode(png.getvalue()).decode()
        response = self.client.post(reverse('jobseeker_cards:card_save', args=[draft.pk]),
            {'revision': draft.revision, 'data': {**draft.data, 'back_art': art}}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        proof = reverse('jobseeker_cards:card_preview', args=[draft.pk])
        self.assertContains(self.client.get(proof + '?side=back'), art)
        self.assertNotContains(self.client.get(proof + '?side=front'), art)
        draft.refresh_from_db()
        self.assertIn(b'/Subtype /Image', pdf(normalize(draft.data)))

    def test_calendar_workspace_uses_job_board_header_and_its_own_editor(self):
        workspace = self.client.get(reverse('jobseeker_calendar'))
        self.assertContains(workspace, 'navbar-brand')
        self.assertContains(workspace, 'board/marketing/live-header-logo.jpg')
        self.assertContains(workspace, reverse('jobseeker_calendar_editor'))
        frame = self.client.get(reverse('jobseeker_calendar_editor') + '?layout=planner')
        self.assertContains(frame, '"defaultDesign": "minimal"')
        self.assertEqual(frame['X-Frame-Options'], 'SAMEORIGIN')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('jobseeker_calendar_editor')).status_code, 302)

    def test_full_art_replaces_text_only_on_the_selected_side(self):
        from .cards import svg
        png = BytesIO()
        Image.new('RGB', (100, 57), 'purple').save(png, 'PNG')
        art = 'data:image/png;base64,' + base64.b64encode(png.getvalue()).decode()
        data = normalize({'name':'Morgan Original', 'front_art':art,'front_placement':'full'})
        front = svg(data,'front',watermark=True)
        self.assertIn(b'width="252" height="144"', front)
        self.assertNotIn(b'Morgan Original', front)
        self.assertIn(b'PREVIEW', front)
        self.assertNotIn(art.encode(), svg(data,'back'))

    def test_guest_card_claim_uses_the_storefront_account(self):
        from career_mobility.models import InternationalProfile
        from django.test import Client
        from django.utils import timezone
        iept = get_user_model().objects.create_user(username='international-card', email='example@example.com')
        InternationalProfile.objects.create(user=iept, country_of_education='Philippines', email_verified_at=timezone.now())
        canadian = get_user_model().objects.get(username='local-jobseeker')
        for user, prefix in ((canadian,'/jobseeker/tools/business-cards/'),(iept,'/career-resources/international/resume/cards/')):
            with self.subTest(user=user):
                client = Client()
                saved = client.post(reverse('mobility_keep_card') + ('?audience=international' if user == iept else ''), {'data':{'name':'Morgan Edited','design':'clinical','ink':'#263248'}}, content_type='application/json')
                self.assertEqual(saved.status_code,200)
                self.assertEqual(saved.json()['url'], '')
                self.assertIn('pending_business_card', client.session)
                client.force_login(user)
                claimed = client.post(reverse('mobility_claim_card'))
                self.assertTrue(claimed.url.startswith(prefix), claimed.url)
                self.assertEqual(BusinessCardDraft.objects.get(owner=user).data['name'],'Morgan Edited')
                self.assertNotIn('pending_business_card', client.session)

    def test_resume_customization_and_optional_portrait_reach_the_pdf(self):
        from .schema import normalize as normalize_resume
        from .pdf import render_pdf
        png = BytesIO()
        Image.new('RGB', (50, 35), 'purple').save(png, 'PNG')
        data = normalize_resume({'name':'Morgan','portrait':'data:image/png;base64,' + base64.b64encode(png.getvalue()).decode(),
            'portrait_size':70,'typeface':'serif','accent_colour':'#263248','extra_heading':'Projects','extra_text':'A custom detail','hidden_sections':['summary']})
        for canadian in (False, True):
            self.assertIn(b'/Subtype /Image', render_pdf(data,canadian=canadian))
