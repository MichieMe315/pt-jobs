from tempfile import TemporaryDirectory
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import DigitalProduct, ProductGalleryImage
from ptjc_resumes.models import ResumeTemplate


@override_settings(SECURE_SSL_REDIRECT=False, CAREER_TOOLS_PREVIEW=True)
class ShopGalleryTests(TestCase):
    def test_admin_gallery_uses_private_storage_and_replaces_defaults(self):
        product = DigitalProduct.objects.get(slug='ptjc-exercise-tracker')
        admin = get_user_model().objects.create_superuser('shop-gallery-admin', 'shop@example.test', 'test-pass')
        self.client.force_login(admin)
        change_url = reverse('admin:career_mobility_digitalproduct_change', args=[product.pk])
        asset = Path(__file__).resolve().parent.parent / 'static/career_mobility/product-previews/pages/exercise-tracker-1.jpg'
        storage = ProductGalleryImage._meta.get_field('image').storage
        with TemporaryDirectory() as temp:
            from unittest.mock import patch
            with patch.object(storage, 'location', temp):
                page = ProductGalleryImage.objects.create(product=product, caption='Clinic tracking sheet', image=SimpleUploadedFile('sample.jpg', asset.read_bytes(), content_type='image/jpeg'))
                self.assertContains(self.client.get(change_url), 'Clinic tracking sheet')
                image = reverse('mobility_product_gallery_image', args=[product.pk, page.pk])
                self.assertEqual(self.client.get(image).status_code, 404)
                product.is_published = True
                product.save(update_fields=['is_published'])
                self.client.logout()
                self.assertEqual(self.client.get(image).status_code, 200)
                response = self.client.get(reverse('mobility_product_detail', args=[product.slug]))
                self.assertContains(response, 'Clinic tracking sheet')
                self.assertNotContains(response, 'Weekly exercise log')

    def test_resume_defaults_only_seed_new_drafts(self):
        template = ResumeTemplate.objects.get(key='canadian-professional')
        template.is_enabled = True
        template.default_layout = 'editorial'
        template.default_palette = 'navy'
        template.save()
        url = reverse('ptjc_canadian_resumes:canadian_start')
        self.assertContains(self.client.get(url), '"palette": "navy"')
        template.default_palette = 'plum'
        template.save(update_fields=['default_palette'])
        self.assertContains(self.client.get(url), '"palette": "navy"')
        from django.test import Client
        self.assertContains(Client().get(url), '"palette": "plum"')

    def test_studio_controls_change_shop_without_disabling_editor(self):
        from .models import StorefrontStudio
        card = StorefrontStudio.objects.get(key='cards')
        card.title = 'Make your clinic card'
        card.save(update_fields=['title'])
        product = DigitalProduct.objects.get(slug='international-business-card-builder-access')
        self.assertNotContains(self.client.get(reverse('mobility_shop')), 'Make your clinic card')
        product.is_published = True
        product.save(update_fields=['is_published'])
        self.assertContains(self.client.get(reverse('mobility_shop')), reverse('mobility_try_cards'))
        card.is_visible = False
        card.save(update_fields=['is_visible'])
        self.assertNotContains(self.client.get(reverse('mobility_shop')), reverse('mobility_try_cards'))
        self.assertEqual(self.client.get(reverse('mobility_try_cards')).status_code, 200)
