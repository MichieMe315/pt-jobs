from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import InternationalProfile, ReferenceCost

class MobilityTests(TestCase):
    def test_public_pages(self):
        for name in ['mobility_home', 'mobility_international', 'mobility_canadian']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_separate_signup(self):
        response = self.client.post(reverse('mobility_international_signup'), {
            'email': 'overseas@example.com',
            'password': 'ExampleSafePassword2026!',
            'country_of_education': 'India',
            'citizenship_country': 'India',
            'residence_country': 'India',
            'destination_province': 'Ontario',
            'canadian_immigration_status': 'none',
            'graduation_year': 2023,
            'registered_in_education_country': 'yes',
        })
        self.assertEqual(response.status_code, 302, getattr(response.context.get('form'), 'errors', None) if response.context else '')
        user = get_user_model().objects.get(email='overseas@example.com')
        self.assertTrue(InternationalProfile.objects.filter(user=user).exists())
        self.assertFalse(hasattr(user, 'jobseeker'))
        self.assertEqual(user.international_pt_profile.citizenship_country, 'India')

    def test_international_cannot_use_canadian_gate(self):
        user = get_user_model().objects.create_user(username='international@example.com', password='ExampleSafePassword2026!')
        InternationalProfile.objects.create(user=user, country_of_education='India', citizenship_country='India', residence_country='India')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('mobility_canadian_full')).status_code, 403)

    def test_unpublished_costs_not_visible(self):
        ReferenceCost.objects.create(kind='rent', city='Toronto', province='Ontario', amount_cad=2000, is_published=False)
        response=self.client.get(reverse('mobility_canadian'))
        self.assertNotEqual(response.context['costs'].get('Toronto, Ontario', {}).get('rent'), '2000.00')


class IntegratedMobilityTests(TestCase):
    def test_salary_page(self):
        self.assertEqual(self.client.get(reverse("mobility_salary_comparison")).status_code, 200)
    def test_anonymous_cannot_save(self):
        import json
        response=self.client.post(reverse("mobility_save_plan"),data=json.dumps({"plan_type":"salary","inputs":{"split":50}}),content_type="application/json")
        self.assertEqual(response.status_code,302)
    def test_international_checklist_access(self):
        user=get_user_model().objects.create_user(username="inttest@example.com",password="ExampleSafePassword2026!")
        InternationalProfile.objects.create(user=user,country_of_education="India")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("mobility_international_dashboard")).status_code,200)
        self.assertEqual(self.client.post(reverse("mobility_checklist_toggle"),{"key":"education"}).status_code,302)
        self.assertEqual(self.client.get(reverse("mobility_personalized_checklist")).status_code,200)
        self.assertEqual(self.client.post(reverse("mobility_save_plan"),data='{"plan_type":"salary","inputs":{}}',content_type="application/json").status_code,403)
    def test_webhook_unsigned_rejected(self):
        from django.test import override_settings
        import os
        from unittest.mock import patch
        with patch.dict(os.environ,{"PT_MOBILITY_STRIPE_WEBHOOK_SECRET":"whsec_test"}):
            self.assertEqual(self.client.post(reverse("mobility_stripe_webhook"),data="{}",content_type="application/json").status_code,400)
