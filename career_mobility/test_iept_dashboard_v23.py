from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import InternationalProfile

class InternationalDashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="iept-test", email="iept@example.org", password="test-password-123")
        self.profile = InternationalProfile.objects.create(user=self.user, country_of_education="India", citizenship_country="India", residence_country="India", destination_province="Ontario")
        self.client.force_login(self.user)
    def test_dashboard_private_and_available(self):
        response = self.client.get(reverse("mobility_international_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your pathway workspace")
    def test_update_profile(self):
        response = self.client.post(reverse("mobility_international_profile_update"), {"country_of_education":"India", "citizenship_country":"India", "residence_country":"United Kingdom", "destination_province":"Alberta", "canadian_immigration_status":"none", "graduation_year":"2024", "registered_in_education_country":"yes"})
        self.assertEqual(response.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.destination_province, "Alberta")
    def test_cannot_access_without_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("mobility_international_dashboard")).status_code,302)
