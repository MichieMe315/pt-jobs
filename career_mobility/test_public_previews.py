from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader
from io import BytesIO

@override_settings(SECURE_SSL_REDIRECT=False)
class PublicPreviewTests(TestCase):
    def test_hub_and_gallery_are_public_without_storefront(self):
        response = self.client.get(reverse('mobility_home'))
        self.assertContains(response, 'Canadian Educated Resume Builder')
        self.assertLess(response.content.index(b'Canadian Educated Resume Builder'), response.content.index(b"<h3>Salary vs. Split Calculator"))
        self.assertRedirects(self.client.get(reverse('mobility_public_previews')), reverse('mobility_shop'))
        from .models import DigitalProduct
        shop = reverse('mobility_shop')
        draft = self.client.get(shop)
        for label in ('Business Card Editor', 'Choose a specialty', '2027 Photo Wall Calendar'):
            self.assertNotContains(draft, label)
        DigitalProduct.objects.filter(slug__in=[
            'international-business-card-builder-access', 'ptjc-pelvic-physio-journal',
            'ptjc-physio-wall-calendar-2027',
        ]).update(is_published=True)
        response = self.client.get(shop)
        for label in ('Career tools and downloads','Business cards','Specialty Journals','Choose a specialty','Open builder'):
            self.assertContains(response, label)
        self.assertContains(response, 'target="_blank"')
        self.assertRedirects(
            self.client.get(reverse('mobility_choose_journal'), {'edition':'pelvic-physio-journal'}),
            reverse('mobility_editable_preview', args=['pelvic-physio-journal']),
        )
        guest = self.client.get(reverse('mobility_editable_preview', args=['canadian-resume']), follow=True)
        self.assertContains(guest, 'Build your Canadian résumé')
        self.assertContains(guest, 'id="design-controls"')
        studio = self.client.get(reverse('mobility_try_cards'))
        self.assertContains(studio, 'Business card editor')
        self.assertNotContains(studio, 'Sign in to your international plan')

    def test_iept_examples_include_builder_sections(self):
        response = self.client.get(reverse('mobility_public_resume_preview',args=['classic']))
        text=' '.join(' '.join(p.extract_text().split()) for p in PdfReader(BytesIO(response.content)).pages)
        for label in ('Assessment route','Credential assessment','PET','Examination','Canadian registration',
                      'Canadian experience','Supervised clinical education','Languages','Work authorization'):
            self.assertIn(label, text)

    def test_real_resume_and_both_sides_of_four_cards_are_public(self):
        response = self.client.get(reverse('mobility_public_resume_preview',args=['clinical']), {'audience':'canadian','focus':'pelvic'})
        self.assertEqual(response.status_code, 200)
        text=''.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
        self.assertIn('Physiotherapist, pelvic health', text)
        self.assertIn('PREVIEW', text)
        for design in ('clinical','community','editorial','networking'):
            for side in ('front','back'):
                response = self.client.get(reverse('mobility_public_card_preview',args=[design,side]))
                self.assertContains(response, 'PREVIEW')
                self.assertEqual(response.headers['Content-Type'], 'image/svg+xml')
                self.assertNotContains(response, 'Ari Shah')

    def test_public_card_studio_renders_custom_text_without_a_draft(self):
        response = self.client.get(reverse('mobility_try_cards'), {'design': 'editorial'})
        self.assertContains(response, 'Preview updates as you edit')
        url = reverse('mobility_try_card_svg')
        for side, value in [('front','Avery Demo'), ('back','Preview Test Studio')]:
            response = self.client.post(f'{url}?side={side}', {'data': {'design':'editorial','name':'Avery Demo','organization':'Preview Test Studio'}}, content_type='application/json')
            self.assertContains(response, value)
            self.assertContains(response, 'PREVIEW')
        from ptjc_resumes.models import BusinessCardDraft
        self.assertFalse(BusinessCardDraft.objects.exists())

    def test_international_library_and_registration_plan_have_next_steps(self):
        from django.contrib.auth import get_user_model
        from django.urls import NoReverseMatch
        try:
            url = reverse('mobility_resource_library')
        except NoReverseMatch:
            self.skipTest('International account routes are disabled in this URL configuration.')
        user = get_user_model().objects.create_user('audit-library-user')
        self.client.force_login(user)
        library = self.client.get(url)
        self.assertContains(library, reverse('mobility_international_shop'))
        self.assertContains(library, reverse('ptjc_resumes:start'))
        plan = self.client.get(reverse('mobility_country',args=['philippines']), {
            'province':'British Columbia','applied':'not-applied','registration':'yes',
        })
        for label in ('Your physiotherapy registration plan','Registration steps','Estimated costs','Save this plan'):
            self.assertContains(plan,label)
