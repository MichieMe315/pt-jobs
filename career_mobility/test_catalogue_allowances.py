from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from board.models import Employer
from .models import DigitalProduct, ProductActivity, StoreBundleItem
from .store_access import has_access


@override_settings(SECURE_SSL_REDIRECT=False)
class CatalogueAllowanceTests(TestCase):
    def setUp(self):
        self.product = DigitalProduct.objects.create(
            title='Starter planner', slug='starter-planner', audience='both',
            preview_editor='practice-planner-2027', is_published=True, starter_quantity=1)
        self.bundle = DigitalProduct.objects.create(
            title='Starter bundle', slug='starter-bundle', audience='both',
            kind='bundle', is_published=True, starter_quantity=1)
        StoreBundleItem.objects.create(bundle=self.bundle, product=self.product)
        self.user = get_user_model().objects.create_user('starter-clinic')
        Employer.objects.create(user=self.user, company_name='Starter Clinic')
        self.client.force_login(self.user)

    def test_editor_export_spends_one_and_records_activity(self):
        url = reverse('mobility_design_activity', args=[self.product.pk])
        self.assertEqual(self.client.post(url, {'event': 'editor_print'}).json()['remaining'], 0)
        self.assertEqual(self.client.post(url, {'event': 'editor_print'}).status_code, 403)
        self.assertEqual(ProductActivity.objects.filter(product=self.product, event='print_requested').count(), 1)

    def test_bundle_claim_is_post_only_and_cannot_repeat(self):
        url = reverse('mobility_claim_starter_bundle', args=[self.bundle.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertTrue(has_access(self.user, self.product))
        self.assertEqual(self.client.post(url).status_code, 403)

    def test_admin_can_change_allowance_for_any_product(self):
        url = reverse('admin:career_mobility_digitalproduct_allowances')
        self.assertEqual(self.client.post(url, {f'quantity_{self.bundle.pk}': 2}).status_code, 302)
        admin = get_user_model().objects.create_superuser('starter-admin')
        self.client.force_login(admin)
        self.assertContains(self.client.get(url), 'Bundle claims')
        self.assertEqual(self.client.post(url, {f'quantity_{self.bundle.pk}': 2}).status_code, 302)
        self.bundle.refresh_from_db()
        self.assertEqual(self.bundle.starter_quantity, 2)
