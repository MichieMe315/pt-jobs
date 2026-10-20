import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from board.models import JobSeeker
from .models import InternationalProfile, SavedCareerPlan, DigitalProduct, ProductOrder

OFFER={'employee-type':'annual','employee-pay':'85000','billing':'100','split':'60','visits':'8','days':'5','weeks':'48','contractor-expenses':'4000'}

class ReleaseBoundaryTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='release-canadian', password='testing-long-password')
        JobSeeker.objects.create(user=self.user,is_approved=True)
        self.client.force_login(self.user)
    def post(self, route, payload):
        return self.client.post(reverse(route),json.dumps(payload),content_type='application/json')
    def test_both_salary_routes_validate_inputs_and_pdf(self):
        for route in ['mobility_save_plan','mobility_salary_save']:
            response=self.post(route,{'plan_type':'salary','inputs':OFFER,'title':'My hospital offer'})
            self.assertEqual(response.status_code,200)
            plan=SavedCareerPlan.objects.get(pk=response.json()['id'])
            self.assertEqual(plan.title,'My hospital offer')
            pdf=self.client.get(reverse('mobility_plan_pdf',args=[plan.pk]))
            self.assertEqual(pdf.status_code,200)
            self.assertTrue(pdf.content.startswith(b'%PDF'))
    def test_invalid_totals_cannot_create_unexportable_plan(self):
        for route in ['mobility_save_plan','mobility_salary_save']:
            self.assertEqual(self.post(route,{'plan_type':'salary','inputs':{'employee_gross':85000,'contractor_gross':100000}}).status_code,400)
        self.assertEqual(SavedCareerPlan.objects.count(),0)
    def test_salary_owner_isolation(self):
        other=get_user_model().objects.create_user(username='release-other')
        plan=SavedCareerPlan.objects.create(user=other,plan_type='salary',inputs=OFFER)
        self.assertEqual(self.client.get(reverse('mobility_salary_load',args=[plan.pk])).status_code,404)
    def test_basic_and_advanced_templates_are_distinct(self):
        self.assertTemplateUsed(self.client.get(reverse('mobility_canadian')),'career_mobility/canadian_basic.html')
        self.assertTemplateUsed(self.client.get(reverse('mobility_canadian_full')),'career_mobility/canadian.html')
    def test_relocation_reopens_only_owned_records(self):
        plan=SavedCareerPlan.objects.create(user=self.user,plan_type='relocation',inputs={'origin':'Rural Ontario','destination':'Calgary, AB'})
        response=self.client.get(reverse('mobility_canadian_full'),{'saved':plan.pk})
        self.assertEqual(response.context['saved_inputs'],plan.inputs)
        other=get_user_model().objects.create_user(username='relocation-other')
        plan.user=other;plan.save()
        self.assertEqual(self.client.get(reverse('mobility_canadian_full'),{'saved':plan.pk}).status_code,404)
    def test_international_isolation(self):
        intl=get_user_model().objects.create_user(username='release-intl')
        InternationalProfile.objects.create(user=intl,country_of_education='India')
        self.client.force_login(intl)
        self.assertFalse(JobSeeker.objects.filter(user=intl).exists())
        for route in ['mobility_canadian_full','jobseeker_dashboard','mobility_relocation_comparisons']:
            self.assertEqual(self.client.get(reverse(route)).status_code,403)
        for route in ['mobility_save_plan','mobility_salary_save']:
            self.assertEqual(self.post(route,{'plan_type':'salary','inputs':OFFER}).status_code,403)
    def test_unpaid_download_denied_and_signed_paid_webhook_idempotent(self):
        product=DigitalProduct.objects.create(title='Guide',slug='release-guide',price_cad='19.99',is_published=True)
        order=ProductOrder.objects.create(user=self.user,product=product,stripe_session_id='release-session')
        self.assertEqual(self.client.get(reverse('mobility_product_download',args=[product.pk])).status_code,403)
        event={'type':'checkout.session.completed','data':{'object':{'id':'release-session','payment_status':'paid'}}}
        with patch.dict('os.environ',{'PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'test-secret'}),patch('stripe.Webhook.construct_event',return_value=event):
            for _ in range(2):
                self.assertEqual(self.client.post(reverse('mobility_stripe_webhook'),data=b'{}',content_type='application/json').status_code,200)
        order.refresh_from_db();self.assertTrue(order.paid)
        self.assertEqual(ProductOrder.objects.filter(stripe_session_id='release-session').count(),1)

    def test_pending_candidate_cannot_enter_private_planning(self):
        profile=self.user.jobseeker;profile.is_approved=False;profile.save()
        self.assertEqual(self.client.get(reverse('mobility_canadian_full')).status_code,403)
        for route in ['mobility_salary_save','mobility_save_plan']:
            self.assertEqual(self.post(route,{'plan_type':'salary','inputs':OFFER}).status_code,403)
    def test_staff_can_review_private_draft_file(self):
        import tempfile
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            product=DigitalProduct.objects.create(title='Draft preview',slug='draft-preview',download=SimpleUploadedFile('draft.pdf',b'%PDF-1.4\npreview'))
            url=reverse('admin:career_mobility_digitalproduct_preview',args=[product.pk])
            self.assertNotEqual(self.client.get(url).status_code,200)
            staff=get_user_model().objects.create_superuser(username='review-staff',password='testing-long-password')
            self.client.force_login(staff)
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertIn('private',response['Cache-Control'])
            self.assertIn('no-store',response['Cache-Control'])
            self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF'))
