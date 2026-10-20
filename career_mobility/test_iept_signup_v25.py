from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .forms import InternationalSignupForm
from .models import InternationalProfile


class InternationalSignupV25Tests(TestCase):
    def details(self, **changes):
        payload = {
            'email': 'international@example.com',
            'password': 'Example-Secure-Pass-2026!x',
            'country_of_education': 'Sri Lanka',
            'citizenship_country': 'Sri Lanka',
            'residence_country': 'Qatar',
            'destination_province': 'Alberta',
            'canadian_immigration_status': 'none',
            'graduation_year': 2020,
            'registered_in_education_country': 'yes',
        }
        payload.update(changes)
        return payload

    def test_signup_creates_private_profile_and_logs_in(self):
        response = self.client.post(reverse('mobility_international_signup'), self.details())
        self.assertRedirects(response, reverse('mobility_international_dashboard'))
        profile = InternationalProfile.objects.get(user__email='international@example.com')
        self.assertEqual(profile.citizenship_country, 'Sri Lanka')
        self.assertEqual(profile.residence_country, 'Qatar')
        self.assertEqual(profile.destination_province, 'Alberta')

    def test_citizenship_cannot_be_blank(self):
        form = InternationalSignupForm(self.details(citizenship_country=''))
        self.assertFalse(form.is_valid())
        self.assertIn('citizenship_country', form.errors)

    def test_unlisted_country_allowed(self):
        form = InternationalSignupForm(self.details(country_of_education='Iceland'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_existing_account_cannot_be_overwritten(self):
        user = get_user_model().objects.create_user(username='existing@example.com', email='existing@example.com', password='Some-Password-2026!')
        response = self.client.post(reverse('mobility_international_signup'), self.details(email=user.email))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(InternationalProfile.objects.count(), 0)

    def test_signed_in_non_iept_account_shows_switch_account_page(self):
        user = get_user_model().objects.create_user(username='local@example.com', email='local@example.com', password='Some-Password-2026!')
        self.client.force_login(user)
        response = self.client.get(reverse('mobility_international_signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'different PTJC account')
