from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from .catalogue import entries
from .models import DigitalProduct, ProductOrder


@override_settings(SECURE_SSL_REDIRECT=False)
class PrintableCollectionTests(TestCase):
    def test_draft_files_are_reviewable_and_only_paid_user_can_download(self):
        user = get_user_model().objects.create_user('printable-buyer')
        self.client.force_login(user)
        for slug, expected_pages in (('exercise-tracker', 1), ('appointment-notes', 2), ('practice-planner-2027', 16)):
            product = DigitalProduct.objects.get(slug=f'ptjc-{slug}')
            with self.subTest(product=product):
                self.assertFalse(product.is_published)
                self.assertEqual(len(entries(product)), 1)
                with product.download.open('rb') as pdf:
                    reader = PdfReader(pdf)
                    self.assertEqual(len(reader.pages), expected_pages)
                    fields = reader.get_fields()
                    self.assertTrue(fields)
                    widgets = [a.get_object() for page in reader.pages for a in page.get('/Annots', []) if a.get_object().get('/Subtype') == '/Widget']
                    self.assertEqual(len(widgets), len(fields))
                    if expected_pages == 16:
                        self.assertEqual(sum(a.get_object().get('/Subtype') == '/Link' for a in reader.pages[0]['/Annots']), 15)
                    elif slug in ('exercise-tracker', 'appointment-notes'):
                        self.assertTrue(any(f['/FT'] == '/Btn' for f in fields.values()))
                url = reverse('mobility_product_download', args=[product.pk])
                self.assertEqual(self.client.get(url).status_code, 403)
                ProductOrder.objects.create(user=user, product=product, paid=True, stripe_session_id=f'cs_{slug}')
                response = self.client.get(url)
                try:
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(next(iter(response.streaming_content)).startswith(b'%PDF'))
                finally:
                    response.close()
                for palette in ('grayscale','plum'):
                    variant = self.client.get(url, {'palette':palette})
                    self.assertEqual(variant.status_code, 200)
                    self.assertIn(f'-{palette}.pdf',variant['Content-Disposition'])
                    from io import BytesIO
                    with BytesIO(b''.join(variant.streaming_content)) as data:
                        pdf = PdfReader(data)
                        self.assertEqual(len(pdf.pages), expected_pages)
                        self.assertEqual(set(pdf.get_fields()), set(fields))
                    variant.close()
                self.assertEqual(self.client.get(url,{'palette':'unavailable'}).status_code,404)

    def test_editable_editions_have_private_downloads_and_limited_public_samples(self):
        import json
        import re
        from .editable_products import TEMPLATES, CALENDAR, JOURNALS
        from ptjc_resumes.specialties import TRACKS
        from .journal_editions import EDITIONS
        self.assertTrue(TRACKS.keys() <= EDITIONS.keys())
        user = get_user_model().objects.create_user('template-buyer')
        self.client.force_login(user)
        for key in (*JOURNALS, CALENDAR):
            product = DigitalProduct.objects.get(slug='ptjc-' + key)
            self.assertFalse(product.is_published)
            demo = self.client.get(reverse('mobility_editable_preview', args=[key]), {'editor_frame': '1'})
            self.assertEqual(demo.status_code, 200)
            self.assertContains(demo, '"demo": true')
            url = reverse('mobility_product_download', args=[product.pk])
            self.assertEqual(self.client.get(url).status_code, 403)
            ProductOrder.objects.create(user=user, product=product, paid=True, stripe_session_id=f'cs_{key}')
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment;', response['Content-Disposition'])
            html = b''.join(response.streaming_content).decode()
            config = json.loads(re.search(r'<script id="config" type="application/json">(.*?)</script>', html).group(1))
            self.assertFalse(config['demo'])
            self.assertEqual(config['sections'], list(TEMPLATES[key][1]))
            self.assertEqual(config['type'], 'calendar' if key == CALENDAR else 'journal')
            self.assertNotIn('calendar_photos/', html)
            response.close()
