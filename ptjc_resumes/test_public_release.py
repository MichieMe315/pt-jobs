import json
from django.test import TestCase,override_settings,Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import ResumeDraft,ResumeTemplate,ResumeAdPlacement
from career_mobility.models import InternationalProfile

@override_settings(ALLOWED_HOSTS=['testserver'],CAREER_TOOLS_PREVIEW=True,SECURE_SSL_REDIRECT=False,EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PublicBuilderTests(TestCase):
    def setUp(self):
        self.template=ResumeTemplate.objects.get(key='international-professional');self.template.is_enabled=True;self.template.save()
    def test_public_entry_and_ten_pages_need_no_account(self):
        self.assertRedirects(self.client.get(reverse('ptjc_resumes:index')),reverse('ptjc_resumes:start'),fetch_redirect_response=False)
        for n in range(1,11):
            response=self.client.get(reverse('ptjc_resumes:public_step',args=[n]));self.assertEqual(response.status_code,200)
            self.assertContains(response,'Create account and keep my draft')
            self.assertNotContains(response,'pagead2.googlesyndication.com')
        self.assertFalse(ResumeDraft.objects.exists())
    def test_anonymous_save_and_restore_do_not_create_customer_records(self):
        self.client.get(reverse('ptjc_resumes:start'))
        response=self.client.post(reverse('ptjc_resumes:public_save'),json.dumps({'revision':1,'title':'My draft','data':{'name':'Alex Visitor'}}),content_type='application/json')
        self.assertEqual(response.status_code,200)
        r=self.client.get(reverse('ptjc_resumes:public_step',args=[2]));self.assertContains(r,'Alex Visitor');self.assertFalse(ResumeDraft.objects.exists())
        other=Client();r=other.get(reverse('ptjc_resumes:public_step',args=[1]));self.assertNotContains(r,'Alex Visitor')
    def test_stale_anonymous_tab_cannot_overwrite(self):
        self.client.get(reverse('ptjc_resumes:start'))
        payload=json.dumps({'revision':1,'title':'draft','data':{'name':'Alex'}})
        self.assertEqual(self.client.post(reverse('ptjc_resumes:public_save'),payload,content_type='application/json').status_code,200)
        self.assertEqual(self.client.post(reverse('ptjc_resumes:public_save'),payload,content_type='application/json').status_code,409)
    def test_public_save_and_claim_require_csrf(self):
        c=Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(reverse('ptjc_resumes:public_save'),'{}',content_type='application/json').status_code,403)
    def test_verified_account_claim_preserves_draft_and_is_idempotent(self):
        self.client.get(reverse('ptjc_resumes:start'))
        self.client.post(reverse('ptjc_resumes:public_save'),json.dumps({'revision':1,'title':'Keep this','data':{'name':'Alex Guest'}}),content_type='application/json')
        u=get_user_model().objects.create_user('claim',email='claim@example.test');InternationalProfile.objects.create(user=u,country_of_education='India',email_verified_at=timezone.now(),email_verified_address=u.email)
        self.client.force_login(u)
        r=self.client.post(reverse('ptjc_resumes:claim'));self.assertEqual(r.status_code,302)
        self.assertEqual(ResumeDraft.objects.get(owner=u).data['name'],'Alex Guest')
        self.client.post(reverse('ptjc_resumes:claim'));self.assertEqual(ResumeDraft.objects.filter(owner=u).count(),1)
    def test_unverified_account_cannot_claim(self):
        u=get_user_model().objects.create_user('unverified');InternationalProfile.objects.create(user=u,country_of_education='India');self.client.force_login(u)
        self.assertRedirects(self.client.post(reverse('ptjc_resumes:claim')),reverse('mobility_verify_pending'),fetch_redirect_response=False)
    def test_admin_controlled_ad_code_only_renders_when_enabled(self):
        ad=ResumeAdPlacement.objects.create(title='Small ad',html='<div>TEST AD SLOT</div>',enabled=False)
        path=reverse('ptjc_resumes:public_step',args=[1]);self.assertNotContains(self.client.get(path),'TEST AD SLOT')
        ad.enabled=True;ad.save();self.assertContains(self.client.get(path),'TEST AD SLOT')
