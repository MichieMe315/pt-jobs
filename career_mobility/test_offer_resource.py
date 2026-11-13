from django.test import TestCase,override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from board.models import JobSeeker

class OfferResourceTests(TestCase):
    def test_guide_has_six_sections_24_statuses_and_six_note_fields(self):
        user=get_user_model().objects.create_user('workbook-reader')
        JobSeeker.objects.create(user=user,is_approved=True)
        self.client.force_login(user)
        response=self.client.get(reverse('mobility_offer_review'))
        self.assertContains(response,'class="job-offer-section"',count=6)
        self.assertContains(response,'data-offer-field="status-',count=24)
        self.assertContains(response,'data-offer-field="notes-',count=6)
        self.assertContains(response,'offer-checklist.js')
        self.assertContains(response,'offer-print')
        self.assertContains(response,'offer-export')
        self.assertNotContains(response,'FREE PTJC CAREER RESOURCE')
        self.assertNotContains(response,'For hospitals, rehabilitation')
    def test_header_footer_home_and_calculator_link_to_guide(self):
        link='href="'+reverse('mobility_clinic_offer_guide')+'"'
        for route in ('mobility_home','mobility_salary_comparison'):
            response=self.client.get(reverse(route))
            self.assertGreaterEqual(response.content.decode().count(link),3)
    def test_jobseeker_dashboard_opens_guide_and_keeps_relocation_coming_soon(self):
        user=get_user_model().objects.create_user('offer-user')
        JobSeeker.objects.create(user=user,is_approved=True)
        self.client.force_login(user)
        response=self.client.get(reverse('jobseeker_dashboard'))
        self.assertContains(response,'href="'+reverse('mobility_offer_review')+'"')
        self.assertContains(response,'Compare Canadian communities · Coming soon')
        self.assertNotContains(response,'href="'+reverse('mobility_canadian')+'"')
