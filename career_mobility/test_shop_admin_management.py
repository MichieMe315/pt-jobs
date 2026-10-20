from decimal import Decimal
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from .admin import DigitalProductAdminForm
from .models import DigitalProduct


class DigitalShopManagementTests(TestCase):
    def test_price_is_editable_without_migration(self):
        product = DigitalProduct.objects.create(title="Resume template", slug="resume-template-2", price_cad="2.49")
        product.price_cad = Decimal("3.49")
        product.save(update_fields=["price_cad"])
        product.refresh_from_db()
        self.assertEqual(product.price_cad, Decimal("3.49"))

    def test_cannot_publish_without_download(self):
        form = DigitalProductAdminForm(data={"title":"Guide", "slug":"guide-test", "description":"Offer tips", "price_cad":"3.49", "is_published":"on"})
        self.assertFalse(form.is_valid())
        self.assertIn("download", form.errors)

    def test_cannot_publish_without_positive_price(self):
        form = DigitalProductAdminForm(data={"title":"Guide", "slug":"guide-test", "description":"Offer tips", "price_cad":"0", "is_published":"on"}, files={"download":SimpleUploadedFile("guide.pdf", b"%PDF-1.4\n", content_type="application/pdf")})
        self.assertFalse(form.is_valid())
        self.assertIn("price_cad", form.errors)

    def test_unpublished_can_be_saved_without_file(self):
        form = DigitalProductAdminForm(data={"title":"Coming soon", "slug":"coming-soon", "description":"", "price_cad":"2.49"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_shop_admin_denies_anonymous(self):
        response = self.client.get(reverse("ptjc_shop_admin"))
        self.assertNotEqual(response.status_code, 200)
