from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import DigitalProduct, ProductOrder

class ShopTests(TestCase):
    def setUp(self):
        self.product = DigitalProduct.objects.create(title='Resume template',slug='resume-template',price_cad='9.00',is_published=True)
        DigitalProduct.objects.create(title='Draft',slug='draft',price_cad='5.00',is_published=False)

    def test_shop_public_and_only_published(self):
        response=self.client.get(reverse('ptjc_shop'))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Resume template')
        self.assertNotContains(response,'<h2 class="h4 mt-2">Draft</h2>')

    def test_shop_admin_requires_staff(self):
        response=self.client.get(reverse('ptjc_shop_admin'))
        self.assertNotEqual(response.status_code,200)

    def test_shop_checkout_requires_login(self):
        response=self.client.post(reverse('mobility_product_checkout',args=[self.product.pk]))
        self.assertEqual(response.status_code,302)
