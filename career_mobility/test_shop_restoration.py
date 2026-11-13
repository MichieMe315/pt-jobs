from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from tempfile import TemporaryDirectory
from unittest.mock import patch
from board.models import Employer, Job
from .models import DigitalProduct


@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ShopRestorationTests(TestCase):
    def test_international_products_only_appear_in_the_international_shop(self):
        product = DigitalProduct.objects.create(title='International workbook test', slug='restored-workbook', kind='workbook', audience='international', is_published=True)
        response = self.client.get(reverse('mobility_shop'))
        self.assertNotContains(response, product.title)
        shop = self.client.get(reverse('mobility_international_shop'))
        self.assertContains(shop, product.title)
        self.assertContains(shop, f'<a class="btn btn-primary" href="{reverse('mobility_international')}">Start your registration plan</a>', html=True)
        self.assertNotContains(shop, reverse('mobility_personalized_checklist'))
        self.assertNotContains(response, 'Working in Canada')
        self.assertNotContains(response, 'No resources match this search.')

    def test_digital_admin_search_finds_a_draft_and_links_to_pricing(self):
        admin = get_user_model().objects.create_superuser('shop-operator')
        self.client.force_login(admin)
        draft = DigitalProduct.objects.create(title='Private shoulder worksheet', slug='shoulder-draft', category='Shoulder care')
        workspace = reverse('admin:task_workspace', args=['shop'])
        edit = reverse('admin:career_mobility_digitalproduct_change', args=[draft.pk])
        self.assertNotContains(self.client.get(workspace), draft.title)
        results = self.client.get(workspace, {'q': 'Shoulder care', 'status': 'draft'})
        self.assertContains(results, draft.title)
        self.assertContains(results, f'href="{edit}#pricing"')
        self.assertContains(self.client.get(edit), 'id="pricing"')

    def test_resume_product_shows_all_four_existing_design_previews(self):
        from ptjc_resumes.models import ResumeTemplate
        product = DigitalProduct.objects.create(title='Resume previews', slug='restored-resume', is_published=True)
        template = ResumeTemplate.objects.get(key='international-professional')
        template.access_product = product
        template.is_enabled = True
        template.save()
        url = reverse('mobility_product_detail', args=[product.slug])
        self.assertNotContains(self.client.get(reverse('mobility_shop')), url)
        response = self.client.get(url)
        for name in ('classic', 'clinical', 'editorial', 'sidebar'):
            self.assertContains(response, f'ptjc_resumes/designs/{name}.png')

    def test_admin_groups_preserve_original_record_listing(self):
        user = get_user_model().objects.create_superuser('restoration-admin', 'admin@example.test', 'Local-Test-482!')
        self.client.force_login(user)
        employer = Employer.objects.create(user=get_user_model().objects.create_user('restoration-clinic'), company_name='Current clinic')
        today = timezone.localdate()
        for title, start, end in [('Live posting', today, today+timedelta(days=30)), ('Expired posting', today-timedelta(days=60), today-timedelta(days=30)), ('Future posting', today+timedelta(days=2), today+timedelta(days=32))]:
            Job.objects.create(employer=employer, title=title, description='Patient care', is_active=True, posting_date=start, expiry_date=end)
        response = self.client.get('/admin/')
        self.assertContains(response, 'Live posting')
        self.assertContains(response, 'Expired posting')
        self.assertContains(response, 'Future posting')
        self.assertNotContains(response, 'pt-shop-shortcuts')
        self.assertContains(response, reverse('admin:task_workspace',args=['shop']))
        self.assertContains(self.client.get(reverse('admin:task_workspace',args=['shop'])), 'Discounts and promotions')

    def test_four_public_pdf_previews_are_watermarked_examples(self):
        from io import BytesIO
        from pypdf import PdfReader
        from ptjc_resumes.models import ResumeDraft
        from .models import ProductOrder
        before = (ResumeDraft.objects.count(), ProductOrder.objects.count())
        for layout in ('classic', 'clinical', 'editorial', 'sidebar'):
            response = self.client.get(reverse('ptjc_resumes:design_preview', args=[layout]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
            self.assertIn('physiotherapyjobscanada.ca', text)
        self.assertEqual(before, (ResumeDraft.objects.count(), ProductOrder.objects.count()))
        self.assertEqual(self.client.get(reverse('ptjc_resumes:design_preview', args=['unknown'])).status_code, 404)

    def test_native_pdf_fallback_when_windows_renderer_cannot_import(self):
        import builtins
        from io import BytesIO
        from reportlab.pdfgen.canvas import Canvas
        user = get_user_model().objects.create_superuser('pdf-preview-admin', 'pdf@example.test', 'Local-Test-482!')
        self.client.force_login(user)
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        with patch.object(DigitalProduct._meta.get_field('download'), 'storage', FileSystemStorage(directory.name)):
            product = DigitalProduct.objects.create(title='PDF resource', slug='pdf-fallback')
            data = BytesIO()
            canvas = Canvas(data)
            canvas.drawString(40, 700, 'Test product preview')
            canvas.save()
            product.download.save('sample.pdf', ContentFile(data.getvalue()))
            file_name = product.download.name.rsplit('/', 1)[-1]
            original_import = builtins.__import__
            def windows_import(name, *args, **kwargs):
                if name == 'fitz':
                    raise ImportError('DLL load failed')
                return original_import(name, *args, **kwargs)
            with patch('builtins.__import__', side_effect=windows_import):
                page = self.client.get(reverse('admin:career_mobility_digitalproduct_view_file', args=[product.pk]), {'file': file_name})
                self.assertContains(page, 'Open PDF in a new window')
                asset = self.client.get(reverse('admin:career_mobility_digitalproduct_asset', args=[product.pk]), {'file': file_name})
                self.assertEqual(asset.status_code, 200)
                self.assertEqual(asset['Content-Type'], 'application/pdf')
                result = self.client.post(reverse('admin:career_mobility_digitalproduct_review', args=[product.pk]), {'preview': file_name}, follow=True)
                self.assertContains(result, 'PDF thumbnail rendering is unavailable')

    def test_production_admin_keeps_discounts_grants_and_access(self):
        import os
        import subprocess
        import sys
        from django.conf import settings
        script = '''import os
os.environ['DJANGO_SETTINGS_MODULE']='pt_jobs.settings'
import django
django.setup()
from django.contrib import admin
from career_mobility.models import DigitalProduct, ProductOrder, StoreDiscount, StoreGrant, StoreEntitlement
assert all(model in admin.site._registry for model in (DigitalProduct,ProductOrder,StoreDiscount,StoreGrant,StoreEntitlement))
from django.urls import reverse
for model in ('digitalproduct','productorder','storediscount','storegrant','storeentitlement'):
    reverse('admin:career_mobility_'+model+'_changelist')
print('Production shop admin registered')
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=settings.BASE_DIR, env=dict(os.environ, DJANGO_DEBUG='1', CAREER_TOOLS_PREVIEW='0', INTERNATIONAL_PLANNER_ENABLED='1'), capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_admin_listing_changes_reach_shop_search_detail_and_checkout(self):
        from decimal import Decimal
        from types import SimpleNamespace
        from .models import InternationalProfile, ProductOrder
        from ptjc_resumes.models import ResumeTemplate

        staff = get_user_model().objects.create_superuser('shop-sync-admin')
        self.client.force_login(staff)
        template = ResumeTemplate.objects.get(key='international-professional')
        product = template.access_product
        if not product:
            product = DigitalProduct.objects.create(title='Original product', slug='shop-sync')
            template.access_product = product
            template.is_enabled = True
            template.save()
        change = reverse('admin:career_mobility_digitalproduct_change', args=[product.pk])
        payload = {
            'title': 'Audited International Resume', 'slug': product.slug, 'kind': 'file',
            'audience': 'international', 'category': 'Resume builder', 'short_description': 'Updated by staff.',
            'description': '', 'storefront_order': '1', 'price_cad': '19.99', 'is_published': 'on',
            'gallery_images-TOTAL_FORMS': '0', 'gallery_images-INITIAL_FORMS': '0',
            'gallery_images-MIN_NUM_FORMS': '0', 'gallery_images-MAX_NUM_FORMS': '1000', '_save': 'Save',
        }
        saved = self.client.post(change, payload)
        self.assertEqual(saved.status_code, 302, getattr(saved, 'context', None))
        product.refresh_from_db()
        self.assertEqual(product.price_cad, Decimal('19.99'))
        self.client.logout()
        detail = reverse('mobility_product_detail', args=[product.slug])
        for filters in ({}, {'q': 'Audited'}, {'q': 'Updated by staff'}, {'category': 'Resume builder'}):
            shop = self.client.get(reverse('mobility_international_shop'), filters)
            self.assertContains(shop, 'Audited International Resume', count=1)
            self.assertContains(shop, 'Updated by staff.')
            self.assertContains(shop, reverse('ptjc_resumes:start'))
            self.assertNotContains(shop, detail)
            self.assertNotContains(shop, '19.99')
        self.assertNotContains(self.client.get(reverse('mobility_canadian_shop')), 'Audited International Resume')
        self.assertContains(self.client.get(detail), '19.99')
        buyer = get_user_model().objects.create_user('shop-sync-buyer', email='buyer@example.test')
        InternationalProfile.objects.create(user=buyer, email_verified_at=timezone.now(),
            email_verified_address=buyer.email, country_of_education='Philippines', destination_province='British Columbia')
        self.client.force_login(buyer)
        with patch.dict('os.environ', {'PT_MOBILITY_STRIPE_SECRET_KEY': 'sk_test_sync', 'PT_MOBILITY_STRIPE_WEBHOOK_SECRET': 'whsec_sync'}), patch(
            'stripe.checkout.Session.create', return_value=SimpleNamespace(id='cs_sync', url='https://checkout.stripe.com/test')
        ) as stripe:
            response = self.client.post(reverse('mobility_product_checkout', args=[product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(stripe.call_args.kwargs['line_items'][0]['price_data']['unit_amount'], 1999)
        order = ProductOrder.objects.get(stripe_session_id='cs_sync')
        self.assertEqual(order.amount_cents, 1999)
        from .store_access import has_access
        self.assertFalse(has_access(buyer, product))
        import hashlib, hmac, json, time
        payload_bytes = json.dumps({'type': 'checkout.session.completed', 'data': {'object': {
            'id': 'cs_sync', 'payment_status': 'paid', 'currency': 'cad', 'amount_total': 1999,
            'metadata': stripe.call_args.kwargs['metadata'],
        }}}).encode()
        stamp = str(int(time.time()))
        signature = hmac.new(b'whsec_sync', stamp.encode()+b'.'+payload_bytes, hashlib.sha256).hexdigest()
        webhook = reverse('mobility_stripe_webhook')
        with patch.dict('os.environ', {'PT_MOBILITY_STRIPE_WEBHOOK_SECRET': 'whsec_sync'}):
            self.assertEqual(self.client.post(webhook, payload_bytes, content_type='application/json', HTTP_STRIPE_SIGNATURE=f't={stamp},v1=bad').status_code, 400)
            for _ in range(2):
                self.assertEqual(self.client.post(webhook, payload_bytes, content_type='application/json', HTTP_STRIPE_SIGNATURE=f't={stamp},v1={signature}').status_code, 200)
        order.refresh_from_db()
        self.assertTrue(order.paid)
        self.assertTrue(has_access(buyer, product))
        self.assertContains(self.client.get(reverse('mobility_resource_library')), 'Audited International Resume')
        self.client.force_login(staff)
        payload.pop('is_published')
        self.assertEqual(self.client.post(change, payload).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.assertNotContains(self.client.get(reverse('mobility_international_shop')), 'Audited International Resume')
