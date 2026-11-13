from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from board.models import JobSeeker
from .models import DigitalProduct, ProductOrder, StoreGrant
from .store_access import activate_grant


@override_settings(SECURE_SSL_REDIRECT=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class StoreJourneyTests(TestCase):
    def test_shop_to_login_to_granted_download(self):
        product = DigitalProduct.objects.get(slug='ptjc-exercise-tracker')
        product.is_published = True
        product.price_cad = 0
        product.save(update_fields=['is_published','price_cad'])
        user = get_user_model().objects.create_user('flow-candidate', password='private-flow-test')
        JobSeeker.objects.create(user=user, is_approved=True)
        shop = self.client.get(reverse('mobility_shop'))
        detail = reverse('mobility_product_detail', args=[product.slug])
        from .shop_gallery import editor_link
        url = editor_link(product, 'canadian')
        self.assertContains(shop, url.replace('&', '&amp;'))
        self.assertNotContains(shop, 'shop-download-link')
        self.assertNotContains(self.client.get(url), 'id="editor-checkout"')
        entry = self.client.get(detail)
        self.assertContains(entry, 'Purchasing is not currently available.')
        login = reverse('login') + '?next=' + detail
        self.assertRedirects(self.client.post(login, {
            'username':user.username, 'password':'private-flow-test',
        }), detail)
        download = reverse('mobility_product_download', args=[product.pk])
        self.assertEqual(self.client.get(download, {'palette':'grayscale'}).status_code,403)
        start = reverse('mobility_product_checkout', args=[product.pk])
        self.assertEqual(self.client.post(start).status_code, 409)
        self.assertFalse(ProductOrder.objects.filter(user=user, product=product).exists())
        grant = StoreGrant.objects.create(user=user, product=product, reason='Staff issued')
        activate_grant(grant)
        library = self.client.get(reverse('mobility_resource_library'))
        self.assertContains(library, download + '?palette=grayscale')
        file = self.client.get(download, {'palette':'grayscale'})
        self.assertEqual(file.status_code, 200)
        self.assertTrue(b''.join(file.streaming_content).startswith(b'%PDF'))
        file.close()
        self.client.logout()
        self.assertEqual(self.client.get(download, {'palette':'grayscale'}).status_code,302)
