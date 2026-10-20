import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import InternationalProfile, SavedCareerPlan

class SavedComparisonTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="intl-salary@example.com", password="TestPass2026!X")
        InternationalProfile.objects.create(user=self.user, country_of_education="India")
        self.client.force_login(self.user)

    def test_international_salary_save_is_blocked(self):
        result = self.client.post(reverse("mobility_save_plan"), data=json.dumps({"plan_type":"salary", "inputs":{"employee":85000,"contractor":100000}}), content_type="application/json")
        self.assertEqual(result.status_code, 403)
        self.assertFalse(SavedCareerPlan.objects.filter(user=self.user).exists())

    def test_international_relocation_still_blocked(self):
        response = self.client.post(reverse("mobility_save_plan"), data=json.dumps({"plan_type":"relocation", "inputs":{"city":"Toronto"}}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

    def test_other_users_cannot_view_or_delete_plan(self):
        other = get_user_model().objects.create_user(username="another@example.com", password="TestPass2026!X")
        plan = SavedCareerPlan.objects.create(user=other, plan_type="salary", title="Private", inputs={"rate":100})
        self.assertEqual(self.client.get(reverse("mobility_plan_pdf", args=[plan.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("mobility_delete_plan", args=[plan.pk])).status_code, 404)

    def test_offer_guide_public(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("mobility_clinic_offer_guide")).status_code, 200)
