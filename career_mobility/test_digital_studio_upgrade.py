from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import JournalTemplate, ProductOrder
from .journal_content import worksheets
from .journal_admin import JournalTemplateForm


@override_settings(SECURE_SSL_REDIRECT=False, CAREER_TOOLS_PREVIEW=True)
class DigitalStudioTests(TestCase):
    def test_every_specialty_has_six_different_worksheets(self):
        from .journal_editions import EDITIONS
        self.assertEqual(JournalTemplate.objects.count(), len(EDITIONS))
        for track in EDITIONS:
            pages=worksheets(track)
            self.assertEqual(len(pages),6)
            self.assertEqual(len({x['title'] for x in pages}),6)
            self.assertTrue(all(len(x['fields'])==4 for x in pages))
        oncology=worksheets('oncology')
        self.assertEqual(oncology[1]['title'],'Activity and fatigue')
        self.assertEqual(oncology[1]['fields'][0]['label'],'Energy through the day')

    def test_admin_can_edit_journal_and_paid_file_matches_preview(self):
        item=JournalTemplate.objects.get(key='oncology-physio-journal')
        user=get_user_model().objects.create_superuser('journal-editor','editor@example.test','test-pass')
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('admin:career_mobility_journaltemplate_change',args=[item.pk])), 'Energy through the day')
        fields={'title':'Clinic oncology journal','subtitle':'Our editable professional journal','default_design':'minimal','default_colour':'#61412e'}
        for i,sheet in enumerate(worksheets('oncology')):
            fields[f'sheet_{i}_title']=sheet['title']
            fields[f'sheet_{i}_intro']=sheet['intro']
            for j,block in enumerate(sheet['fields']):
                fields[f'sheet_{i}_{j}_label']=block['label']
                fields[f'sheet_{i}_{j}_prompt']=block['prompt']
        fields['sheet_1_0_label']='Our energy review'
        form=JournalTemplateForm(fields,instance=item)
        self.assertTrue(form.is_valid(),form.errors)
        form.save()
        preview=reverse('mobility_editable_preview',args=[item.key])
        self.client.logout()
        self.assertContains(self.client.get(preview, {'editor_frame': '1'}),'Our energy review')
        self.assertContains(self.client.get(preview, {'editor_frame': '1'}),'"defaultDesign": "minimal"')
        from .models import DigitalProduct
        product=DigitalProduct.objects.get(slug='ptjc-'+item.key)
        download=reverse('mobility_product_download',args=[product.pk])
        self.assertEqual(self.client.get(download).status_code,302)
        customer=get_user_model().objects.create_user('journal-buyer')
        self.client.force_login(customer)
        self.assertEqual(self.client.get(download).status_code,403)
        ProductOrder.objects.create(user=customer,product=product,paid=True,stripe_session_id='cs_journal_paid')
        response=self.client.get(download)
        self.assertEqual(response.status_code,200)
        text=b''.join(response.streaming_content).decode()
        self.assertIn('Our energy review',text)
        self.assertIn('"demo": false',text)
        self.assertIn('"title": "Clinic oncology journal"',text)
