"""A fileless builder can be purchased and opened through a real entitlement."""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import DigitalProduct, ProductOrder, StoreDiscount, StoreEntitlement
from .shop_gallery import editor_link


@override_settings(SECURE_SSL_REDIRECT=False)
class OnlineBuilderPurchaseTests(TestCase):
    def setUp(self):
        self.buyer = get_user_model().objects.create_user(
            'builder-buyer', email='builder@example.test',
        )
        self.product = DigitalProduct.objects.create(
            slug='browser-planning-test', title='Browser planning workbook',
            kind='file', preview_editor='planning-spreadsheet', audience='canadian',
            price_cad='19.00', canadian_price_cad='11.25', is_published=True,
        )
        self.editor = editor_link(self.product, 'canadian')

    def test_fileless_checkout_price_and_entitlement(self):
        checkout = reverse('mobility_product_checkout', args=[self.product.pk])
        self.assertNotContains(self.client.get(self.editor + "&editor_frame=1"), '"canExport": true')
        self.assertEqual(self.client.post(checkout).status_code, 302)
        self.client.force_login(self.buyer)
        editor = self.client.get(self.editor + "&editor_frame=1")
        self.assertNotContains(editor, '"canExport": true')
        self.assertContains(editor, f'action="{checkout}"')
        self.assertContains(editor, '"productUrl": "#editor-checkout"')
        with patch.dict('os.environ', {
            'PT_MOBILITY_STRIPE_SECRET_KEY': 'sk_test_builder',
            'PT_MOBILITY_STRIPE_WEBHOOK_SECRET': 'whsec_builder',
        }), patch('stripe.checkout.Session.create', return_value=SimpleNamespace(
            id='cs_builder', url='https://checkout.stripe.com/test-builder',
        )) as create:
            self.assertRedirects(self.client.post(checkout), 'https://checkout.stripe.com/test-builder',
                                 fetch_redirect_response=False)
            self.assertEqual(create.call_args.kwargs['line_items'][0]['price_data']['unit_amount'], 1125)
            self.assertTrue(create.call_args.kwargs['cancel_url'].endswith(self.editor))
            order = ProductOrder.objects.get(stripe_session_id='cs_builder')
            session = {
                'id': order.stripe_session_id, 'status': 'complete', 'payment_status': 'paid',
                'currency': 'cad', 'amount_total': 1125, 'metadata': {
                    'mobility_product_id': str(self.product.pk),
                    'mobility_user_id': str(self.buyer.pk), 'mobility_amount_cents': '1125',
                },
            }
            self.assertNotContains(self.client.get(self.editor + "&editor_frame=1"), '"canExport": true')
            raw = json.dumps({'id': 'evt_builder', 'type': 'checkout.session.completed',
                              'data': {'object': session}})
            timestamp = int(time.time())
            digest = hmac.new(b'whsec_builder', f'{timestamp}.{raw}'.encode(), hashlib.sha256).hexdigest()
            hook = reverse('mobility_stripe_webhook')
            for _ in range(2):
                self.assertEqual(self.client.post(hook, raw, content_type='application/json',
                                                 HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={digest}').status_code, 200)
        order.refresh_from_db()
        self.assertTrue(order.paid)
        self.assertEqual(StoreEntitlement.objects.filter(user=self.buyer, product=self.product).count(), 1)
        self.assertContains(self.client.get(self.editor + "&editor_frame=1"), '"canExport": true')
        self.assertContains(self.client.get(reverse('mobility_resource_library')), 'Open builder')
        self.client.force_login(get_user_model().objects.create_user('other-builder-buyer'))
        self.assertNotContains(self.client.get(self.editor + "&editor_frame=1"), '"canExport": true')

    def test_zero_price_cannot_create_new_access(self):
        checkout = reverse('mobility_product_checkout', args=[self.product.pk])
        self.client.force_login(self.buyer)
        self.product.canadian_price_cad = 0
        self.product.save(update_fields=['canadian_price_cad'])
        self.assertNotContains(self.client.get(self.editor + "&editor_frame=1"), 'id="editor-checkout"')
        self.assertEqual(self.client.post(checkout).status_code, 409)
        self.assertFalse(ProductOrder.objects.filter(product=self.product).exists())
        self.assertFalse(StoreEntitlement.objects.filter(product=self.product).exists())

    def test_valid_full_discount_unlocks_editor_without_stripe(self):
        checkout = reverse('mobility_product_checkout', args=[self.product.pk])
        self.client.force_login(self.buyer)
        discount = StoreDiscount.objects.create(name='Full discount', code='FULL', kind='percent', value=100)
        discount.products.add(self.product)
        with patch('stripe.checkout.Session.create') as stripe, patch(
            'career_mobility.store_checkout.stripe_key', return_value='',
        ):
            self.assertEqual(self.client.post(checkout, {'discount_code': 'BAD'}).status_code, 400)
            self.assertFalse(ProductOrder.objects.filter(product=self.product).exists())
            self.assertContains(self.client.post(checkout, {'discount_code': 'FULL'}), 'Your resource is ready')
            stripe.assert_not_called()
        order = ProductOrder.objects.get(product=self.product, user=self.buyer)
        self.assertTrue(order.paid)
        self.assertEqual(order.amount_cents, 0)
        self.assertEqual(order.discount, discount)
        self.assertContains(self.client.get(self.editor + "&editor_frame=1"), '"canExport": true')

    def test_automatic_full_discount_does_not_grant_public_access(self):
        checkout = reverse('mobility_product_checkout', args=[self.product.pk])
        self.client.force_login(self.buyer)
        discount = StoreDiscount.objects.create(name='Automatic', code='', kind='percent', value=100)
        discount.products.add(self.product)
        self.assertContains(self.client.post(checkout), 'A valid discount code is required', status_code=400)
        self.assertFalse(StoreEntitlement.objects.filter(product=self.product).exists())
