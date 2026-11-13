from django.utils import timezone
from types import SimpleNamespace
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from .planning import build,from_answers
from .forms import PROVINCES
from .models import InternationalProfile,InternationalChecklistItem

@override_settings(ALLOWED_HOSTS=['testserver'],EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ProgressivePlannerTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('planner',password='TestOnly123!')
        self.profile=InternationalProfile.objects.create(email_verified_at=timezone.now(),user=self.user,country_of_education='India',destination_province='Ontario',application_history='new',registered_in_education_country='yes')
    def test_public_questionnaire_and_preview_are_free(self):
        self.assertContains(self.client.get(reverse('mobility_international_plan')),'international-planner-form')
        response=self.client.get(reverse('mobility_international_preview'),{'country':'India','province':'Ontario','applied':'not-applied','registration':'yes'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['checklist_free'])
        self.assertGreater(len(response.json()['steps']),10)
        self.assertEqual(self.client.get(reverse('mobility_international_preview'),{'country':'India'}).status_code,400)
    def test_all_destinations_have_distinct_guidance(self):
        for province in PROVINCES:
            with self.subTest(province=province):
                self.profile.destination_province=province
                plan=build(self.profile)
                self.assertTrue(plan['guidance']['url'].startswith('https://'))
                self.assertGreater(len(plan['steps']),10)
                self.assertEqual(len({x['key'] for x in plan['steps']}),len(plan['steps']))
    def test_changing_destination_preserves_but_does_not_transfer_completion(self):
        self.client.force_login(self.user)
        old=next(s['key'] for s in build(self.profile)['steps'] if s['key'].startswith(('province_','local0_')))
        self.client.post(reverse('mobility_checklist_toggle'),{'key':old})
        self.profile.destination_province='Alberta';self.profile.save()
        response=self.client.get(reverse('mobility_international_dashboard'))
        self.assertFalse(next(s['completed'] for s in response.context['checklist'] if s['key'].startswith(('province_','local0_'))))
        self.profile.destination_province='Ontario';self.profile.save()
        self.assertTrue(next(s['completed'] for s in self.client.get(reverse('mobility_international_dashboard')).context['checklist'] if s['key'].startswith(('province_','local0_'))))
    def test_save_owns_profile_and_preserves_after_date_and_previous_registration(self):
        self.client.force_login(self.user)
        self.client.post(reverse('mobility_international_save'),{'country':'Philippines','province':'Quebec','applied':'after','registration':'previous'})
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.application_history,'after')
        self.assertEqual(self.profile.registered_in_education_country,'previous')
        self.assertEqual(self.profile.destination_province,'Quebec')
        self.assertIn('Quebec',build(self.profile)['route'])
        self.assertEqual(self.client.get(reverse('mobility_personalized_checklist')).status_code,200)
    def test_invalid_save_does_not_modify_profile(self):
        self.client.force_login(self.user)
        response=self.client.post(reverse('mobility_international_save'),{'country':'India','province':'Fake','applied':'before','registration':'yes'})
        self.assertEqual(response.status_code,400)
        self.profile.refresh_from_db();self.assertEqual(self.profile.destination_province,'Ontario')
    def test_canadian_jobseeker_cannot_save_international_plan(self):
        other=get_user_model().objects.create_user('other')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('mobility_international_save'),{}).status_code,403)
    def test_forged_task_and_other_profile_cannot_be_changed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('mobility_checklist_toggle'),{'key':'province_forged'}).status_code,400)
        self.assertEqual(InternationalChecklistItem.objects.count(),0)
    def test_territories_do_not_invent_registration_application(self):
        for province in ['Nunavut','Northwest Territories']:
            self.profile.destination_province=province
            plan=build(self.profile)
            self.assertIn('employer',next(s['label'] for s in plan['steps'] if s['key'].startswith(('province_','local0_'))))
            self.assertIn('employer',next(s['label'] for s in plan['steps'] if s['key'].startswith('apply_')))

    def test_country_history_registration_and_destination_combinations(self):
        from .country_content import countries
        for country in countries():
            for history in ('new','existing','after','unsure'):
                for status in ('yes','previous','no','unsure'):
                    self.profile.country_of_education=country['name']
                    self.profile.application_history=history
                    self.profile.registered_in_education_country=status
                    for province in PROVINCES:
                        self.profile.destination_province=province
                        plan=build(self.profile)
                        self.assertTrue(plan['route'])
                        self.assertTrue(all(len(step['key'])<=90 for step in plan['steps']))
                        if province=='Quebec': self.assertIn('Quebec',plan['route'])
    def test_saved_and_preview_steps_match(self):
        answers={'country':'India','province':'Ontario','applied':'not-applied','registration':'yes'}
        preview=self.client.get(reverse('mobility_international_preview'),answers).json()
        self.client.force_login(self.user)
        saved=self.client.get(reverse('mobility_international_dashboard')).context['checklist']
        self.assertEqual([x['key'] for x in saved],[x['key'] for x in preview['steps']])
    def test_questionnaire_save_requires_csrf(self):
        from django.test import Client
        browser=Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post(reverse('mobility_international_save'),{}).status_code,403)
    def test_ircc_source_is_separate_from_credentialling(self):
        step=next(x for x in build(self.profile)['steps'] if x['key'].startswith('immigration_'))
        self.assertIn('canada.ca',step['source_url'])

    def test_old_country_directory_handler_also_opens_questionnaire(self):
        from django.test import RequestFactory
        from django.contrib.auth.models import AnonymousUser
        from .country_views import country_index
        request=RequestFactory().get('/career-resources/international/')
        request.user=AnonymousUser()
        request.session={}
        response=country_index(request)
        self.assertIn(b'international-planner-form',response.content)
    def test_registration_has_compact_sections_and_preserves_questionnaire_answers(self):
        response=self.client.get(reverse('mobility_international_signup'),{'country_of_education':'India','destination_province':'Ontario','application_history':'after','registered_in_education_country':'previous'})
        self.assertContains(response,'international-register.css')
        self.assertNotContains(response,'iept-signup-v25.css')
        self.assertContains(response,'Create account and save my plan')
        self.assertEqual(response.context['form']['application_history'].value(),'after')
        self.assertEqual(response.context['form']['destination_province'].value(),'Ontario')
