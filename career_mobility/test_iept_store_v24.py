from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import DigitalProduct, InternationalProfile, ProductOrder

class IEPTStoreTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="iept-shop@example.test", email="iept-shop@example.test", password="StrongTestPassword123!")
        InternationalProfile.objects.create(user=self.user, country_of_education="India", citizenship_country="India", residence_country="India", graduation_year=2023, canadian_immigration_status="none", registered_in_education_country="yes")
        self.product = DigitalProduct.objects.create(title="Transition workbook", slug="transition-workbook", description="Editable workbook", price_cad=Decimal("19.00"), is_published=True)
        self.bundle = DigitalProduct.objects.create(title="Transition kit bundle", slug="transition-kit-bundle", description="Complete bundle", price_cad=Decimal("49.00"), is_published=True)
        self.client.force_login(self.user)
    def test_dashboard_shows_individual_and_bundle(self):
        response = self.client.get(reverse("mobility_international_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transition workbook")
        self.assertContains(response, "Transition kit bundle")
    def test_owned_item_moves_to_library(self):
        ProductOrder.objects.create(user=self.user, product=self.product, stripe_session_id="sess_test_v24", paid=True)
        response = self.client.get(reverse("mobility_international_dashboard"))
        self.assertContains(response, "Your downloads")
        self.assertContains(response, reverse("mobility_product_download", args=[self.product.pk]))
    def test_checkout_requires_post(self):
        response = self.client.get(reverse("mobility_product_checkout", args=[self.product.pk]))
        self.assertEqual(response.status_code, 405)
    def test_unpublished_products_not_shown(self):
        DigitalProduct.objects.create(title="Hidden guide", slug="hidden-guide", is_published=False)
        self.assertNotContains(self.client.get(reverse("mobility_international_dashboard")), "Hidden guide")
