from datetime import timedelta
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from board.models import Employer, Job
from .models import DigitalProduct
from .recovered_products import FILES


class OutstandingReleaseTests(TestCase):
    def test_job_feed_only_shows_live_opted_in_jobs(self):
        User = get_user_model()
        employer = Employer.objects.create(user=User.objects.create_user('publisher'),company_name='Approved clinic',is_approved=True)
        blocked = Employer.objects.create(user=User.objects.create_user('pending'),company_name='Pending clinic')
        today = timezone.localdate()
        defaults = dict(employer=employer,posting_date=today,expiry_date=today+timedelta(days=5),is_active=True,
                        international_stage='exam_passed',international_support='discuss')
        for title, changes in [
            ('Visible after CPTE',{}),('Visible all stages',{'international_stage':'any'}),
            ('Hidden expired',{'expiry_date':today-timedelta(days=1)}),('Hidden future',{'posting_date':today+timedelta(days=1)}),
            ('Hidden draft',{'is_active':False}),('Hidden unapproved',{'employer':blocked}),('Hidden no consent',{'international_stage':''}),
            ('Visible registered',{'international_stage':'registered','international_support':'unavailable'}),
        ]:
            Job.objects.create(title=title,description='Job description',**{**defaults,**changes})
        response = self.client.get(reverse('mobility_international_jobs'),{'stage':'exam_passed','support':'discuss'})
        self.assertContains(response,'Visible after CPTE')
        self.assertContains(response,'Visible all stages')
        self.assertContains(response,'Visible registered')
        self.assertNotContains(response,'Hidden ')
        self.assertContains(self.client.get(reverse('mobility_international')),reverse('mobility_international_jobs'))

    def test_new_downloads_have_private_files_and_start_unpublished(self):
        for key, filename in FILES.items():
            with self.subTest(product=key):
                product = DigitalProduct.objects.get(slug='ptjc-'+key)
                self.assertFalse(product.is_published)
                self.assertEqual(product.download.name,'bundled/'+filename)
                with product.download.open('rb') as handle, ZipFile(handle) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertTrue(archive.namelist())
                self.assertEqual(self.client.get(reverse('mobility_product_detail',args=[product.slug])).status_code,404)

    def test_duplicate_review_groups_matches_without_deleting_or_publishing(self):
        user = get_user_model().objects.create_superuser('catalogue-staff','staff@example.test','Local-Password-123')
        product = DigitalProduct.objects.create(title='Card Set',slug='card-a',download='same.zip')
        DigitalProduct.objects.create(title='Card-set',slug='card-b',download='same.zip')
        self.client.force_login(user)
        response = self.client.get(reverse('admin:career_mobility_digitalproduct_duplicates'))
        self.assertContains(response,'Same title and audience')
        self.assertContains(response,'Same download file')
        self.assertContains(response,reverse('admin:career_mobility_digitalproduct_change',args=[product.pk]))
        self.assertEqual(DigitalProduct.objects.filter(slug__in=['card-a','card-b'],is_published=False).count(),2)

    def test_landing_and_selected_country_use_expected_sponsor(self):
        from .models import InternationalSponsor
        InternationalSponsor.objects.create(sponsor='Global sponsor',description='General listing',website='https://example.test/',enabled=True)
        InternationalSponsor.objects.create(sponsor='Philippines sponsor',country='Philippines',description='Targeted listing',website='https://example.test/',enabled=True)
        InternationalSponsor.objects.create(sponsor='Disabled sponsor',country='Philippines',description='Not live',website='https://example.test/',enabled=False,position=0)
        landing = self.client.get(reverse('mobility_international'))
        self.assertContains(landing,'Global sponsor')
        self.assertContains(landing,'Plan your move to Canada')
        self.assertContains(landing,'id="international-planner-form"')
        self.assertNotContains(landing,'<h2>Jobs</h2>')
        self.assertContains(landing,reverse('mobility_international_plan'))
        self.assertNotContains(landing,'Philippines sponsor')
        targeted = self.client.get(reverse('mobility_country',args=['philippines']))
        self.assertContains(targeted,'Philippines sponsor')
        self.assertNotContains(targeted,'Disabled sponsor')
        self.assertNotContains(targeted,'Global sponsor')

    def test_shop_uses_plain_titles_and_no_price_or_details_link(self):
        p = DigitalProduct.objects.get(slug='ptjc-practice-prints')
        p.is_published=True
        p.price_cad='37.14'
        p.save()
        response = self.client.get(reverse('mobility_shop'))
        self.assertContains(response,f'<h2>{p.title}</h2>',html=True)
        self.assertNotContains(response,'37.14')
        self.assertNotContains(response,'Product details')
        self.assertContains(self.client.get(reverse('mobility_product_detail',args=[p.slug])),'37.14')

    def test_product_admin_uses_focused_sections_and_hides_bundle_rows(self):
        staff = get_user_model().objects.create_superuser('focused-product-admin','focused@example.test','Local-Password-123')
        self.client.force_login(staff)
        p = DigitalProduct.objects.get(slug='ptjc-practice-prints')
        page = self.client.get(reverse('admin:career_mobility_digitalproduct_change',args=[p.pk]))
        self.assertContains(page,'Price and publication')
        self.assertContains(page,'Preview and files')
        self.assertNotContains(page,'Add another Store bundle item')
        self.assertNotContains(page,'Not a specialty journal')
        self.assertContains(page,'name="preview_editor"')

    def test_rebuilt_product_form_saves_price_and_description(self):
        staff = get_user_model().objects.create_superuser('product-editor-save','product-save@example.test','Local-Password-123')
        self.client.force_login(staff)
        product = DigitalProduct.objects.get(slug='ptjc-practice-prints')
        url = reverse('admin:career_mobility_digitalproduct_change',args=[product.pk])
        response = self.client.get(url)
        self.assertContains(response,'pt-editor-actions')
        self.assertContains(response,'id="digitalproduct_form"')
        saved = self.client.post(url,{
            'title':product.title,'slug':product.slug,'kind':product.kind,'audience':product.audience,
            'category':product.category,'short_description':'Edited in the new form','description':product.description,
            'storefront_order':product.storefront_order,'price_cad':'12.34','_save':'Save',
            'gallery_images-TOTAL_FORMS':'0','gallery_images-INITIAL_FORMS':'0',
            'gallery_images-MIN_NUM_FORMS':'0','gallery_images-MAX_NUM_FORMS':'1000',
        })
        self.assertEqual(saved.status_code,302)
        product.refresh_from_db()
        self.assertEqual(str(product.price_cad),'12.34')
        self.assertEqual(product.short_description,'Edited in the new form')
        self.assertTrue(product.download.name.endswith('practice-prints.zip'))
        self.assertFalse(product.is_published)
