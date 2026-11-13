from django.utils import timezone
import json
import os
import tempfile
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from board.models import JobSeeker
from .country_content import countries
from .models import InternationalProfile, InternationalActivity, CountryResourceCollection, DigitalProduct, ProductOrder
from .private_storage import PrivateMobilityStorage

@override_settings(ALLOWED_HOSTS=['testserver'],EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CountryPlannerTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('international',email='intl@example.test',password='TestOnly123!')
        self.profile=InternationalProfile.objects.create(email_verified_at=timezone.now(),user=self.user,country_of_education='India',residence_country='United Arab Emirates')
        self.temp=tempfile.TemporaryDirectory()
        self.field=DigitalProduct._meta.get_field('download');self.old_storage=self.field.storage
        self.field.storage=PrivateMobilityStorage(location=self.temp.name)
        self.addCleanup(self.temp.cleanup);self.addCleanup(setattr,self.field,'storage',self.old_storage)

    def test_all_supported_country_pages_and_resource_pages_render(self):
        self.assertEqual(len(countries()),17)
        for country in countries():
            with self.subTest(country=country['name']):
                r=self.client.get(reverse('mobility_country',args=[country['slug']]))
                self.assertContains(r,country['name'])
                self.assertContains(r,'planner.css')
                self.assertEqual(self.client.get(reverse('mobility_country_resources',args=[country['slug']])).status_code,200)
        self.assertEqual(self.client.get(reverse('mobility_country',args=['made-up'])).status_code,404)

    def test_legacy_country_lookup_redirects_to_canonical_page(self):
        r=self.client.get(reverse('mobility_international'),{'country':'India'})
        self.assertContains(r,'international-planner-form')
        self.assertContains(r,'India')

    def test_country_rules_and_existing_or_quebec_routes(self):
        for slug in ['india','pakistan','philippines','egypt']:
            self.assertContains(self.client.get(reverse('mobility_country',args=[slug])),'hospital-issued')
        for slug in ['hong-kong','south-africa']:
            self.assertContains(self.client.get(reverse('mobility_country',args=[slug])),'plan for an accepted language test')
        r=self.client.get(reverse('mobility_country',args=['france']))
        self.assertContains(r,'France is not on the pre-approved')
        self.assertContains(self.client.get(reverse('mobility_country',args=['india']),{'province':'Quebec'}),'Quebec equivalence and registration')
        self.assertContains(self.client.get(reverse('mobility_country',args=['india']),{'application_history':'unsure'}),'Continue your existing assessment file')
        self.assertEqual(self.client.get(reverse('mobility_country',args=['india']),{'province':'invalid'}).status_code,400)

    def test_profile_activity_has_separate_country_context_and_no_jobseeker(self):
        self.client.force_login(self.user)
        self.client.get(reverse('mobility_country',args=['philippines']))
        event=InternationalActivity.objects.get(action='country_viewed')
        self.assertEqual(event.profile,self.profile)
        self.assertEqual(event.education_country,'India')
        self.assertEqual(event.residence_country,'United Arab Emirates')
        self.assertEqual(event.page_country,'Philippines')
        self.assertFalse(JobSeeker.objects.filter(user=self.user).exists())

    def test_checklist_changes_and_successful_downloads_recorded(self):
        self.client.force_login(self.user)
        self.client.post(reverse('mobility_checklist_toggle'),{'key':next(s['key'] for s in self.client.get(reverse('mobility_international_dashboard')).context['checklist'] if s['key'].startswith(('record_','documents_')))})
        self.assertTrue(InternationalActivity.objects.filter(action='checklist_completed').exists())
        self.client.post(reverse('mobility_checklist_toggle'),{'key':next(s['key'] for s in self.client.get(reverse('mobility_international_dashboard')).context['checklist'] if s['key'].startswith(('record_','documents_')))})
        self.assertTrue(InternationalActivity.objects.filter(action='checklist_reopened').exists())
        from .store_access import activate_grant,workbook_product
        from .models import StoreGrant
        gift=StoreGrant.objects.create(user=self.user,product=workbook_product(),reason='Workbook test');activate_grant(gift)
        response=self.client.post(reverse('mobility_country_guide',args=['india']))
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('private',response['Cache-Control']);self.assertIn('no-store',response['Cache-Control'])
        self.assertTrue(InternationalActivity.objects.filter(action='country_guide_downloaded').exists())
        self.assertEqual(self.client.get(reverse('mobility_international_dashboard')).status_code,200)

    def test_country_guide_rejects_noninternational_accounts(self):
        other=get_user_model().objects.create_user('canadian');JobSeeker.objects.create(user=other,is_approved=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('mobility_country_guide',args=['india'])).status_code,403)
        self.assertFalse(InternationalActivity.objects.filter(action='country_guide_downloaded').exists())

    def test_signup_separate_account_records_countries_and_sends_mail(self):
        from django.core import mail
        data={'email':'newintl@example.test','password':'DistinctPrivate482!','country_of_education':'India','citizenship_country':'India','residence_country':'United Arab Emirates','canadian_immigration_status':'none','graduation_year':'2024','registered_in_education_country':'yes','application_history':'new'}
        r=self.client.post(reverse('mobility_international_signup'),data)
        self.assertEqual(r.status_code,302)
        profile=InternationalProfile.objects.get(user__email=data['email'])
        self.assertFalse(JobSeeker.objects.filter(user=profile.user).exists())
        self.assertEqual(profile.application_history,'new')
        self.assertTrue(InternationalActivity.objects.filter(profile=profile,action='account_created').exists())
        self.assertTrue(any('Your international planning account' in m.subject for m in mail.outbox))

    def test_unauthorized_download_not_recorded(self):
        self.client.force_login(self.user)
        p=DigitalProduct.objects.create(title='Resume',slug='resume-private',price_cad=20,is_published=True)
        p.download.save('resume.docx',ContentFile(b'private example'))
        self.assertEqual(self.client.get(reverse('mobility_product_download',args=[p.pk])).status_code,403)
        self.assertFalse(InternationalActivity.objects.filter(action='product_downloaded').exists())
        ProductOrder.objects.create(user=self.user,product=p,paid=True,stripe_session_id='test_order')
        r=self.client.get(reverse('mobility_product_download',args=[p.pk]));self.assertEqual(r.status_code,200);r.close()
        self.assertTrue(InternationalActivity.objects.filter(action='product_downloaded',subject=p.slug).exists())

    def test_bundle_contains_only_selected_private_files_and_stays_unpublished(self):
        from .bundles import build_bundle
        a=DigitalProduct.objects.create(title='Resume',slug='resume',price_cad=20);a.download.save('resume.docx',ContentFile(b'RESUME'))
        c=DigitalProduct.objects.create(title='Business card',slug='business-card',price_cad=10);c.download.save('card.pdf',ContentFile(b'CARD'))
        collection=CountryResourceCollection.objects.create(country_slug='india',title='India application resources')
        collection.products.add(a,c)
        bundle=build_bundle(collection)
        self.assertFalse(bundle.is_published);self.assertEqual(bundle.price_cad,Decimal('0'))
        with bundle.download.open('rb') as f,ZipFile(BytesIO(f.read())) as z:
            self.assertEqual(sorted(z.namelist()),['business-card/card.pdf','resume/resume.docx'])
            self.assertEqual(z.read('resume/resume.docx'),b'RESUME')
        collection.products.add(bundle)
        with self.assertRaises(ValueError):build_bundle(collection)

    def test_signed_payment_confirmation_is_idempotent_and_return_page_does_not_fulfill(self):
        product=DigitalProduct.objects.create(title='Kit',slug='kit',price_cad=20)
        order=ProductOrder.objects.create(user=self.user,product=product,stripe_session_id='cs_test_country')
        self.client.force_login(self.user)
        self.client.get(reverse('mobility_international_dashboard')+'?payment=return')
        order.refresh_from_db();self.assertFalse(order.paid)
        event={'type':'checkout.session.completed','data':{'object':{'id':order.stripe_session_id,'payment_status':'paid','amount_total':2000,'currency':'cad'}}}
        with patch.dict(os.environ,{'PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'test_secret'}),patch('stripe.Webhook.construct_event',return_value=event):
            for _ in range(2):
                with self.captureOnCommitCallbacks(execute=True):
                    self.assertEqual(self.client.post(reverse('mobility_stripe_webhook'),b'{}',content_type='application/json').status_code,200)
        order.refresh_from_db();self.assertTrue(order.paid)
        self.assertEqual(InternationalActivity.objects.filter(action='purchase_confirmed',event_key=f'paid:{order.pk}').count(),1)

    def test_activity_is_permission_protected_and_countries_are_filterable(self):
        self.client.force_login(self.user);self.client.get(reverse('mobility_country',args=['india']))
        url=reverse('admin:career_mobility_internationalactivity_changelist')
        self.assertEqual(self.client.get(url).status_code,302)
        staff=get_user_model().objects.create_user('staff',is_staff=True);self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code,403)
        staff.user_permissions.add(Permission.objects.get(content_type__app_label='career_mobility',codename='view_internationalactivity'))
        r=self.client.get(url);self.assertContains(r,'intl@example.test');self.assertContains(r,'United Arab Emirates')
        self.assertNotContains(self.client.get(url,{'residence_country__exact':'India'}),'intl@example.test')
