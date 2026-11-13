from django.utils import timezone
import json
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch
from types import SimpleNamespace
import os
from io import BytesIO
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from pypdf import PdfReader
from career_mobility.models import DigitalProduct, ProductOrder, InternationalProfile
from board.models import JobSeeker
from .models import ResumeTemplate, ResumeDraft
from .schema import normalize, status_lines, EXAMPLE, REGISTRATION
from .pdf import render_pdf

@override_settings(CAREER_TOOLS_PREVIEW=True,SECURE_SSL_REDIRECT=False)
class InternationalResumeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        U=get_user_model();cls.user=U.objects.create_user('resume-owner',email='owner@example.com',password='testpass123')
        cls.other=U.objects.create_user('resume-other',email='other@example.com',password='testpass123')
        for user in (cls.user,cls.other):InternationalProfile.objects.create(email_verified_at=timezone.now(),user=user,country_of_education='India',destination_province='Alberta')
        cls.product=DigitalProduct.objects.create(title='Resume access',slug='resume-access-test',price_cad=Decimal('29.99'),is_published=True,download='career_mobility/products/example.zip')
        cls.template,_=ResumeTemplate.objects.update_or_create(key='international-professional',defaults={'access_product':cls.product,'is_enabled':True})
    def setUp(self):
        self.client.force_login(self.user)
        self.draft=ResumeDraft.objects.create(owner=self.user,template=self.template,data=normalize(deepcopy(EXAMPLE)))
    def url(self,name,pk=None):return reverse('ptjc_resumes:'+name,args=[pk or self.draft.pk])
    def save(self,data=None,rev=1):return self.client.post(self.url('save'),json.dumps({'title':'My overseas application','data':normalize(deepcopy(EXAMPLE)) if data is None else data,'revision':rev}),content_type='application/json')
    def pay(self,product=None,paid=True):return ProductOrder.objects.create(user=self.user,product=product or self.product,stripe_session_id='cs_'+str(ProductOrder.objects.count()),paid=paid)
    def test_existing_checkout_uses_current_admin_price(self):
        self.product.price_cad=Decimal('39.50');self.product.save()
        with patch.object(self.product.download.storage,'exists',return_value=True),patch.dict(os.environ,{'PT_MOBILITY_STRIPE_SECRET_KEY':'sk_test_local','PT_MOBILITY_STRIPE_WEBHOOK_SECRET':'whsec_test_local'}),patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_test_admin_price',url='https://checkout.stripe.com/example')) as checkout:
            r=self.client.post(reverse('mobility_product_checkout',args=[self.product.pk]))
        self.assertEqual(r.status_code,302)
        self.assertEqual(checkout.call_args.kwargs['line_items'][0]['price_data']['unit_amount'],3950)

    def test_editor_and_admin_price(self):
        r=self.client.get(self.url('edit'));self.assertEqual(r.status_code,200);self.assertContains(r,'CAD $29.99');self.assertContains(r,'save automatically');self.assertContains(r,'resume-bootstrap')
    def test_index_and_new_draft(self):
        self.assertEqual(self.client.get(reverse('ptjc_resumes:index')).status_code,200)
        r=self.client.post(reverse('ptjc_resumes:create'));self.assertEqual(r.status_code,302);self.assertEqual(ResumeDraft.objects.filter(owner=self.user).count(),2)
    def test_save_and_reload(self):
        r=self.save();self.assertEqual(r.status_code,200);self.draft.refresh_from_db();self.assertEqual(self.draft.revision,2);self.assertEqual(self.draft.data['education_country'],EXAMPLE['education_country']);self.assertEqual(self.draft.title,'My overseas application')
    def test_stale_tab_cannot_overwrite(self):
        self.assertEqual(self.save().status_code,200);self.assertEqual(self.save(rev=1).status_code,409);self.draft.refresh_from_db();self.assertEqual(self.draft.revision,2)
    def test_another_user_cannot_access_any_draft_endpoint(self):
        self.client.force_login(self.other)
        for name in ['edit','preview','download']:
            with self.subTest(name=name):self.assertEqual(self.client.get(self.url(name)).status_code,404)
        self.assertEqual(self.save().status_code,404);self.assertEqual(self.client.post(self.url('delete')).status_code,404)
    def test_signed_out_cannot_access(self):
        self.client.logout();self.assertEqual(self.client.get(self.url('edit')).status_code,302);self.assertEqual(self.save().status_code,302)
    def test_save_requires_csrf(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.user);r=c.post(self.url('save'),'{}',content_type='application/json');self.assertEqual(r.status_code,403)
    def test_unpaid_export_blocked_even_with_pending_order(self):
        self.pay(paid=False);self.assertEqual(self.client.get(self.url('download')).status_code,403)
    def test_different_product_does_not_unlock(self):
        product=DigitalProduct.objects.create(title='Other',slug='other-product',price_cad=9);self.pay(product=product);self.assertEqual(self.client.get(self.url('download')).status_code,403)
    def test_single_design_order_and_all_design_order(self):
        self.pay(self.template.layout_offers.get(layout='classic').product)
        self.draft.data['layout'] = 'classic'
        self.draft.save(update_fields=['data'])
        self.assertEqual(self.client.get(self.url('download')).status_code, 200)
        self.draft.data['layout'] = 'sidebar'
        self.draft.save(update_fields=['data'])
        self.assertEqual(self.client.get(self.url('download')).status_code, 403)
        self.pay()
        self.assertEqual(self.client.get(self.url('download')).status_code, 200)

    def test_watermarked_preview_and_private_headers(self):
        r=self.client.get(self.url('preview'));self.assertEqual(r.status_code,200);self.assertIn('no-store',r['Cache-Control']);self.assertIn('PREVIEW',''.join(p.extract_text() for p in PdfReader(BytesIO(r.content)).pages))
    def test_paid_export_no_watermark(self):
        self.pay();r=self.client.get(self.url('download'));self.assertEqual(r.status_code,200);reader=PdfReader(BytesIO(r.content));text=''.join(p.extract_text() for p in reader.pages);self.assertIn(EXAMPLE['name'],text);self.assertNotIn('PREVIEW',text);self.assertIn('Not registered in Canada',text);self.assertIn('attachment;',r['Content-Disposition'])
    def test_incomplete_paid_export_is_actionable(self):
        self.pay();self.draft.data=normalize({});self.draft.save();r=self.client.get(self.url('download'));self.assertEqual(r.status_code,400);self.assertTrue(r.json()['fields'])
    def test_registered_status_needs_regulator_and_class(self):
        d=normalize(deepcopy(EXAMPLE));d['canadian_registration']=REGISTRATION[2];self.save(d);self.pay();self.assertEqual(self.client.get(self.url('download')).status_code,400)
    def test_canadian_related_work_is_separate_from_overseas_work(self):
        d=normalize(deepcopy(EXAMPLE));d['canadian_experience']=[{'role':'Rehabilitation assistant','employer':'Example Canadian Service','location':'Ottawa, Ontario','dates':'2026','setting':'Supervised rehabilitation support','bullets':'Supported the treating team within the assigned role.'}];text=''.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(d))).pages);self.assertIn('Canadian experience',text);self.assertIn('Rehabilitation assistant',text);self.assertIn('Not registered in Canada',text)

    def test_route_change_omits_stale_pet(self):
        d=normalize(deepcopy(EXAMPLE));d['pet']='Comparable';d['pathway']='Pre-Approved';text=''.join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(d))).pages);self.assertNotIn('PET:',text)
    def test_availability_is_opt_in(self):
        d=normalize(deepcopy(EXAMPLE));d['work_authorization']='PRIVATE OPTIONAL TEXT';d['show_availability']=False;pdf=PdfReader(BytesIO(render_pdf(d)));self.assertNotIn('PRIVATE OPTIONAL TEXT',''.join(p.extract_text() for p in pdf.pages))
    def test_long_resume_paginates_without_losing_text(self):
        d=normalize(deepcopy(EXAMPLE));d['name']='Alexandria François-Martínez';d['experience']=d['experience']*12;d['experience'][-1]=deepcopy(d['experience'][-1]);d['experience'][-1]['bullets']+='\nFINAL UNIQUE CONTRIBUTION';pdf=PdfReader(BytesIO(render_pdf(d)));self.assertGreater(len(pdf.pages),2);self.assertIn('FINAL UNIQUE CONTRIBUTION',''.join(p.extract_text() for p in pdf.pages))
    def test_invalid_order_and_oversized_content_rejected(self):
        d=normalize(deepcopy(EXAMPLE));d['section_order']=[1,'summary'];self.assertEqual(self.save(d).status_code,400)
        d=normalize(deepcopy(EXAMPLE));d['summary']='x'*1801;self.assertEqual(self.save(d).status_code,400)
    def test_schema_rejects_untrusted_types_and_control_characters(self):
        for d in [{'name':{}},{'summary':'bad\x00'},{'name':'\ud800'},{'placements':[{'hours':'nan'}]},{'profile_url':'javascript:alert(1)'}]:
            with self.subTest(data=repr(d)),self.assertRaises(ValidationError):normalize(d)
    def test_text_is_escaped_in_pdf(self):
        d=normalize(deepcopy(EXAMPLE));d['summary']='<script>alert(1)</script>';pdf=PdfReader(BytesIO(render_pdf(d)));self.assertIn('<script>',''.join(p.extract_text() for p in pdf.pages))
    def test_user_account_and_jobseeker_records_unchanged(self):
        before=JobSeeker.objects.count();profiles=InternationalProfile.objects.count();self.save();self.client.get(self.url('preview'));self.user.refresh_from_db();self.assertEqual(JobSeeker.objects.count(),before);self.assertEqual(InternationalProfile.objects.count(),profiles);self.assertFalse(self.user.is_staff)
    def test_disabled_template_stops_access(self):
        self.template.is_enabled=False;self.template.save();self.assertEqual(self.client.get(self.url('edit')).status_code,404);self.template.is_enabled=True;self.template.save()
    def test_delete_is_post_and_owner_only(self):
        self.assertEqual(self.client.get(self.url('delete')).status_code,405);self.assertEqual(self.client.post(self.url('delete')).status_code,302);self.assertFalse(ResumeDraft.objects.filter(pk=self.draft.pk).exists())
