import json,re
from unittest.mock import patch
from types import SimpleNamespace
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from .models import InternationalProfile,DigitalProduct,ProductOrder
from .email_verification import tokens,send_verification
from ptjc_resumes.models import ResumeTemplate,ResumeDraft
from ptjc_resumes.schema import normalize,status_lines

@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',ALLOWED_HOSTS=['testserver'])
class VerificationAndResumeJourneyTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('new-intl',email='candidate@example.com',password='Strong-password-584!')
        self.profile=InternationalProfile.objects.create(user=self.user,country_of_education='India',destination_province='Ontario',application_history='new',registered_in_education_country='yes')
        self.client.force_login(self.user)
    def test_unverified_cannot_enter_dashboard_or_resume_or_download(self):
        for name in ['mobility_international_dashboard','ptjc_resumes:index','mobility_personalized_checklist']:
            self.assertRedirects(self.client.get(reverse(name)),reverse('mobility_verify_pending'),fetch_redirect_response=False)
        self.assertEqual(ResumeDraft.objects.filter(owner=self.user).count(),0)
    def test_verification_mail_one_use_and_cooldown(self):
        from django.test import RequestFactory
        request=RequestFactory().get('/');request.user=self.user
        self.assertTrue(send_verification(request,self.profile));self.assertFalse(send_verification(request,self.profile))
        self.assertEqual(len(mail.outbox),1);self.assertIn('Verify my email',mail.outbox[0].alternatives[0].content)
        url=re.search(r'http://testserver/[^\s]+',mail.outbox[0].body).group()
        self.assertEqual(self.client.get(url).status_code,302)
        self.profile.refresh_from_db();self.assertIsNotNone(self.profile.email_verified_at)
        self.assertEqual(self.client.get(reverse('mobility_international_dashboard')).status_code,200)
        self.assertEqual(self.client.get(url).status_code,400)
    def test_changed_email_invalidates_token(self):
        token=tokens.make_token(self.user);self.user.email='changed@example.com';self.user.save()
        self.assertFalse(tokens.check_token(self.user,token))
    def test_email_failure_is_visible_and_retryable(self):
        from django.test import RequestFactory
        with patch('django.core.mail.EmailMultiAlternatives.send',side_effect=RuntimeError('offline')):
            self.assertFalse(send_verification(RequestFactory().get('/'),self.profile))
        self.profile.refresh_from_db();self.assertIsNone(self.profile.verification_sent_at)
    def test_confirm_does_not_log_in_another_account(self):
        self.client.logout();url=reverse('mobility_verify_email',args=[urlsafe_base64_encode(force_bytes(self.user.pk)),tokens.make_token(self.user)])
        self.assertRedirects(self.client.get(url),reverse('mobility_international_login'),fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id',self.client.session)
    def activate(self):
        self.profile.email_verified_at=timezone.now();self.profile.save()
    def test_resume_new_draft_prefills_known_account_facts(self):
        self.activate();r=self.client.post(reverse('ptjc_resumes:create'));d=ResumeDraft.objects.get(owner=self.user)
        self.assertEqual(d.data['education_country'],'India');self.assertEqual(d.data['email'],self.user.email);self.assertEqual(d.data['destination'],'Ontario');self.assertEqual(d.data['canadian_registration'],'')
    def test_exam_date_roundtrip_and_detail_visibility(self):
        d=normalize({'exam':'Exam booked','exam_date':'2027-02-16','canadian_registration':'Not registered in Canada'})
        self.assertFalse(any(k=='Examination' for k,v in status_lines(d)))
        d['show_assessment_details']=True;self.assertIn(('Examination','Exam booked · 2027-02-16'),status_lines(d))
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):normalize({'exam_date':'2027-02-31'})
    def test_admin_priced_resume_access_checkout_without_download_file(self):
        self.activate();product=DigitalProduct.objects.create(title='Resume PDF',slug='priced-resume-access',price_cad='24.99',is_published=True)
        template=ResumeTemplate.objects.get(key='international-professional');template.access_product=product;template.is_enabled=True;template.save()
        with patch.dict('os.environ',{'PT_MOBILITY_STRIPE_SECRET_KEY':'sk_test_fake','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_fake'}),patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_test_resume_access',url='https://checkout.stripe.com/fake')) as checkout:
            r=self.client.post(reverse('mobility_product_checkout',args=[product.pk]));self.assertEqual(r.status_code,302)
            self.assertEqual(checkout.call_args.kwargs['line_items'][0]['price_data']['unit_amount'],2499)
        self.assertFalse(ProductOrder.objects.get(stripe_session_id='cs_test_resume_access').paid)
    def test_ontario_subtotals_are_explicit_and_admin_controls_price(self):
        self.activate();r=self.client.get(reverse('mobility_international_dashboard'))
        self.assertContains(r,'Total: assessment, exam and selected registration');self.assertContains(r,'4,712.00');self.assertContains(r,'762.00');self.assertContains(r,'Additional expenses:');self.assertContains(r,'target="_blank" rel="noopener">Open resume builder')
    def test_landing_disclaimer_at_bottom_and_no_middle_account_panel(self):
        r=self.client.get(reverse('mobility_international_plan'));body=r.content.decode()
        self.assertNotIn('Your international account</h2>',body)
        self.assertGreater(body.index('Planning information only.'),body.index('international-planner-form'))

    def test_each_checklist_action_saves_without_reload_and_is_idempotent(self):
        self.activate()
        from .planning import build
        from .models import InternationalChecklistItem
        plan=build(self.profile);key=next(step['key'] for step in plan['steps'] if step['key'].startswith('record_'))
        url=reverse('mobility_checklist_toggle')
        for _ in range(2):
            result=self.client.post(url,{'key':key,'completed':'true'},HTTP_ACCEPT='application/json')
            self.assertEqual(result.status_code,200);self.assertTrue(result.json()['completed']);self.assertEqual(result.json()['done'],1)
        self.assertEqual(InternationalChecklistItem.objects.filter(profile=self.profile,key=key).count(),1)
        self.assertFalse(self.client.post(url,{'key':key,'completed':'false'},HTTP_ACCEPT='application/json').json()['completed'])
    def test_admin_can_publish_fileless_resume_product_with_own_price(self):
        from .admin import DigitalProductAdminForm
        from django.forms import modelform_factory
        product=DigitalProduct.objects.create(title='Resume access',slug='fileless-access',price_cad=0)
        template=ResumeTemplate.objects.get(key='international-professional');template.access_product=product;template.is_enabled=True;template.save()
        Form=modelform_factory(DigitalProduct,form=DigitalProductAdminForm,fields=['price_cad','is_published'])
        form=Form({'price_cad':'39.99','is_published':True},instance=product)
        self.assertTrue(form.is_valid(),form.errors);form.save();product.refresh_from_db();self.assertTrue(product.is_published);self.assertEqual(str(product.price_cad),'39.99')
    def test_signup_requires_email_verification(self):
        self.client.logout()
        data={'email':'brand-new@example.test','password':'New-Private-Audit-482!','country_of_education':'India','citizenship_country':'India','residence_country':'India','destination_province':'Ontario','canadian_immigration_status':'none','graduation_year':2024,'registered_in_education_country':'yes','application_history':'new'}
        response=self.client.post(reverse('mobility_international_signup'),data)
        self.assertRedirects(response,reverse('mobility_verify_pending'))
        self.assertRedirects(self.client.get(reverse('mobility_international_dashboard')),reverse('mobility_verify_pending'))
        profile=InternationalProfile.objects.get(user__email=data['email']);self.assertIsNone(profile.email_verified_at)

    def test_new_email_requires_verification_again(self):
        self.profile.email_verified_at=timezone.now();self.profile.email_verified_address=self.user.email;self.profile.save()
        self.user.email='new-address@example.test';self.user.save()
        self.assertRedirects(self.client.get(reverse('mobility_international_dashboard')),reverse('mobility_verify_pending'))

    def test_alternate_country_workbook_url_requires_verified_email(self):
        self.assertRedirects(self.client.get(reverse('mobility_country_guide',args=['india'])),reverse('mobility_verify_pending'))
    def test_checklist_response_keeps_overview_next_action_current(self):
        self.activate()
        from .planning import build
        tasks=build(self.profile)['steps'];first=tasks[0]
        response=self.client.post(reverse('mobility_checklist_toggle'),{'key':first['key'],'completed':'true'},HTTP_ACCEPT='application/json')
        self.assertEqual(response.json()['next_step']['label'],tasks[1]['label'])
        response=self.client.post(reverse('mobility_checklist_toggle'),{'key':first['key'],'completed':'false'},HTTP_ACCEPT='application/json')
        self.assertEqual(response.json()['next_step']['label'],first['label'])
    def test_international_hub_has_direct_account_route(self):
        self.activate();response=self.client.get(reverse('mobility_home'))
        self.assertContains(response,'My international dashboard');self.assertNotContains(response,'Your Canadian job seeker account')
