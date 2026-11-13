import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from board.models import Employer, JobSeeker
from .models import DigitalProduct, ProductActivity, ProductDraft, ProductOrder
from .shop_gallery import editor_link


@override_settings(SECURE_SSL_REDIRECT=False)
class AppointmentDesignTests(TestCase):
    def setUp(self):
        self.product = DigitalProduct.objects.create(title='Appointment cards', slug='appointment-test',
            price_cad=15, preview_editor='appointment-card-designs', is_published=True,
            audience='both', eligible_accounts=['employer', 'jobseeker'])
        self.user = get_user_model().objects.create_user('clinic')
        Employer.objects.create(user=self.user, company_name='Clinic')
        side = dict(heading='Clinic', name='', note='', date='Date', time='Time',
                    **{'with': 'Clinician'}, paper='#ffffff', ink='#111111',
                    image='', scale=30, placement='right')
        self.data = dict(design='clinical', front=side, back={**side, 'placement': 'left'})
        self.url = reverse('mobility_save_design', args=[self.product.pk])

    def save(self, draft=None):
        return self.client.post(self.url, json.dumps({'draft': draft, 'data': self.data}), content_type='application/json')

    def test_employer_can_save_but_needs_access_to_print(self):
        editor = editor_link(self.product, 'canadian')
        shell = self.client.get(editor)
        self.assertContains(shell, '<iframe')
        self.assertNotContains(shell, 'Saving and printing')
        page = self.client.get(editor + '&editor_frame=1')
        self.assertEqual(page['X-Frame-Options'], 'SAMEORIGIN')
        self.assertNotContains(page, 'Saving and printing')
        self.assertNotContains(page, 'Preview print sheet')
        self.assertContains(page, 'Print or save as PDF')
        self.assertNotContains(page, 'My digital products')
        self.assertContains(page, 'Front · Practice branding')
        self.assertContains(shell, 'Physiotherapy Jobs Canada')
        self.assertContains(page, 'Create an account')
        self.assertContains(page, 'CAD $15.00')
        self.assertNotContains(page, 'No starter cards are included.')
        self.assertEqual(self.save().status_code, 302)
        self.client.force_login(self.user)
        result = self.save()
        self.assertEqual(result.status_code, 200)
        draft = ProductDraft.objects.get()
        self.assertFalse(result.json()['canPrint'])
        activity = reverse('mobility_design_activity', args=[self.product.pk])
        self.assertEqual(self.client.post(activity, {'event':'print_requested','draft':draft.pk}).status_code, 403)
        ProductOrder.objects.create(user=self.user, product=self.product, paid=True, stripe_session_id='test-access')
        self.assertTrue(self.save(draft.pk).json()['canPrint'])
        self.assertContains(self.client.get(result.json()['url'] + '&editor_frame=1'), '"placement": "right"')
        self.assertContains(self.client.get(reverse('mobility_resource_library')), 'Saved designs')
        self.assertEqual(self.client.post(activity, {'event':'print_requested','draft':draft.pk}).status_code, 200)
        self.assertTrue(ProductActivity.objects.filter(product=self.product, event='print_requested', account='employer').exists())
        other = get_user_model().objects.create_user('candidate')
        JobSeeker.objects.create(user=other, is_approved=True, login_active=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(result.json()['url']).status_code, 404)
        self.assertEqual(self.save(draft.pk).status_code, 404)

    def test_product_account_selection_is_enforced(self):
        self.product.eligible_accounts = ['jobseeker']
        self.product.save()
        self.client.force_login(self.user)
        self.assertEqual(self.save().status_code, 403)
        checkout = reverse('mobility_product_checkout', args=[self.product.pk])
        self.assertEqual(self.client.post(checkout).status_code, 403)

    def test_international_account_can_reopen_its_draft(self):
        from django.utils import timezone
        from .models import InternationalProfile
        user = get_user_model().objects.create_user('international')
        InternationalProfile.objects.create(user=user, country_of_education='Philippines', email_verified_at=timezone.now())
        self.product.eligible_accounts.append('international')
        self.product.save(update_fields=['eligible_accounts'])
        self.client.force_login(user)
        saved = self.save()
        self.assertEqual(saved.status_code, 200)
        self.assertIn('audience=international', saved.json()['url'])
        self.assertContains(self.client.get(saved.json()['url'] + '&editor_frame=1'), '"placement": "left"')

    def test_staff_can_reorder_live_products_and_open_activity_report(self):
        from .shop_gallery import resource_link
        staff = get_user_model().objects.create_superuser('staff')
        self.client.force_login(staff)
        other = DigitalProduct.objects.create(title='Second appointment card', slug='second-appointment-test',
            preview_editor='appointment-card-designs', is_published=True)
        url = reverse('admin:career_mobility_digitalproduct_order')
        self.assertContains(self.client.get(url), 'Save shop order')
        order = [other.pk, self.product.pk] + [
            p.pk for p in DigitalProduct.objects.filter(is_published=True).exclude(pk__in=[self.product.pk, other.pk])
            if any(resource_link(p, role) for role in ('canadian', 'international'))
        ]
        self.assertEqual(self.client.post(url, {'product': order}).status_code, 302)
        other.refresh_from_db()
        self.product.refresh_from_db()
        self.assertLess(other.storefront_order, self.product.storefront_order)
        report = reverse('admin:career_mobility_digitalproduct_activity')
        self.assertContains(self.client.get(report), 'Print requested counts clicks')

    def test_new_account_starter_cards_debit_sheet_quantity(self):
        from django.utils import timezone
        self.product.starter_quantity = 10
        self.product.save()
        self.client.force_login(self.user)
        saved = self.save().json()
        activity = reverse('mobility_design_activity', args=[self.product.pk])
        event = {'event': 'print_requested', 'draft': saved['id'], 'copies': '8'}
        self.assertEqual(self.client.post(activity, event).status_code, 403)
        self.user.date_joined = timezone.now()
        self.user.save(update_fields=['date_joined'])
        self.assertEqual(self.client.post(activity, event).json()['remaining'], 2)
        self.assertEqual(self.client.post(activity, event).status_code, 403)
        self.assertEqual(self.client.post(activity, {**event, 'copies':'2'}).json()['remaining'], 0)
        self.assertEqual(self.client.post(activity, {**event, 'copies':'1'}).status_code, 403)
