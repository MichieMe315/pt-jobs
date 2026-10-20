from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from board.models import JobSeeker, SiteSettings
from .models import ReferenceCost, ProvincialLicenceFee
from .research import research_context

class ResearchInterfaceTests(TestCase):
    def test_reviewed_snapshot_has_kitchener_and_correct_provinces(self):
        before=(ReferenceCost.objects.count(),ProvincialLicenceFee.objects.count())
        data=research_context()
        kw=next(r for r in data['locations'] if 'Kitchener' in r['aliases'])
        self.assertEqual(kw['rent'],2120)
        self.assertEqual(kw['province'],'Ontario')
        self.assertEqual(next(r for r in data['locations'] if r['city']=='Calgary')['rent'],1890)
        self.assertEqual(before,(ReferenceCost.objects.count(),ProvincialLicenceFee.objects.count()))
    def test_reference_panel_and_mapbox_render_on_both_layouts(self):
        SiteSettings.objects.create(mapbox_token='pk.public-test')
        for route in ['mobility_canadian','mobility_international']:
            r=self.client.get(reverse(route))
            self.assertContains(r,'career-mapbox-config')
            self.assertContains(r,'pk.public-test')
            self.assertContains(r,'pt-jobs-slate.css')
            self.assertNotContains(r,'Compare provincial licensing costs')
    def test_country_lookup_and_profile_fields(self):
        self.assertContains(self.client.get(reverse('mobility_international')),'data-career-place="country"',count=1)
        r=self.client.get(reverse('mobility_international_signup'),{'country_of_education':'India','citizenship_country':'Canada','destination_province':'Ontario'})
        self.assertEqual(r.context['form']['country_of_education'].value(),'India')
        self.assertContains(r,'data-career-place="country"',count=3)
    def test_dashboard_has_compact_heading_and_no_old_banner(self):
        user=get_user_model().objects.create_user(username='research-candidate')
        JobSeeker.objects.create(user=user,is_approved=True)
        self.client.force_login(user)
        r=self.client.get(reverse('jobseeker_dashboard'))
        self.assertContains(r,'My dashboard')
        self.assertNotContains(r,'Your next career move starts here')
        self.assertContains(r,'candidate-workspace')
    def test_existing_published_cost_retained(self):
        ReferenceCost.objects.create(kind='rent',city='Calgary',province='Alberta',amount_cad=1777,source_url='https://example.org/review',is_published=True)
        r=self.client.get(reverse('mobility_canadian'))
        self.assertEqual(r.context['costs']['Calgary, Alberta']['rent'],'1777.00')

    def test_international_references_follow_action_panel(self):
        html=self.client.get(reverse('mobility_international')).content.decode()
        self.assertLess(html.index('id="pathway-action-panel"'),html.index('Know which route to review'))
        self.assertNotIn('id="fee-origin"',html)
    def test_resume_and_application_tabs_precede_tools(self):
        user=get_user_model().objects.create_user(username='tab-order-candidate')
        JobSeeker.objects.create(user=user,is_approved=True)
        self.client.force_login(user)
        html=self.client.get(reverse('jobseeker_dashboard')).content.decode()
        self.assertLess(html.index('id="resumes-tab"'),html.index('id="applications-tab"'))
        self.assertLess(html.index('id="applications-tab"'),html.index('id="tools-tab"'))
        self.assertIn('candidate-profile',html)

    def test_first_release_does_not_link_unfinished_dashboard_tools(self):
        user=get_user_model().objects.create_user(username='release-navigation-user')
        JobSeeker.objects.create(user=user,is_approved=True)
        self.client.force_login(user)
        html=self.client.get(reverse('jobseeker_dashboard')).content.decode()
        self.assertIn('Job offer checklist · Coming soon',html)
        self.assertNotIn('href="'+reverse('mobility_relocation_comparisons')+'"',html)
        self.assertNotIn('href="'+reverse('mobility_clinic_offer_guide')+'"',html)
    def test_release_navigation_links_resources_and_salary(self):
        html=self.client.get(reverse('mobility_home')).content.decode()
        self.assertGreaterEqual(html.count('href="'+reverse('mobility_home')+'"'),2)
        self.assertIn('href="'+reverse('mobility_salary_comparison')+'"',html)
        self.assertIn('International physiotherapists',html)
        self.assertIn('Coming soon',html)
    def test_checklist_restores_six_section_guide(self):
        html=self.client.get(reverse('mobility_clinic_offer_guide')).content.decode()
        self.assertNotIn('offer-review',html)
        self.assertNotIn('job-offer-checklist.js',html)
        self.assertEqual(html.count('<section class="offer-card">'),6)

    def test_shared_navigation_removes_referral_and_province_footer(self):
        html=self.client.get(reverse('mobility_home')).content.decode()
        self.assertNotIn('Accepting New Patients?',html)
        self.assertNotIn('Jobs by Province',html)
        self.assertIn('id="careerResourcesMenu"',html)
        self.assertIn('aria-label="Career resources"',html)
        self.assertIn('All career resources',html)
