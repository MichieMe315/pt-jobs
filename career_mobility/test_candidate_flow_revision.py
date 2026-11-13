from django.utils import timezone
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import InternationalProfile
from .views import _canadian_context

@override_settings(CAREER_TOOLS_PREVIEW=True,SECURE_SSL_REDIRECT=False)
class CandidateFlowRevisionTests(TestCase):
 def test_public_route_is_preview_not_unsaved_checklist(self):
  response=self.client.get(reverse('mobility_country',args=['india'])+'?province=Alberta')
  self.assertContains(response,'Create account and save this route')
  self.assertNotContains(response,'name="completed"')
  self.assertContains(response,'Planning information only.')
 def test_login_action_preserves_questionnaire(self):
  r=self.client.post(reverse('mobility_international_capture'),{'country':'India','province':'Alberta','applied':'not-applied','registration':'yes','account_action':'login'})
  self.assertRedirects(r,reverse('mobility_international_login'))
  self.assertEqual(self.client.session['international_pending']['answers']['destination_province'],'Alberta')
 def test_dashboard_exposes_builder_and_individual_save(self):
  u=get_user_model().objects.create_user('revision-user');InternationalProfile.objects.create(email_verified_at=timezone.now(),user=u,country_of_education='India',destination_province='Alberta')
  self.client.force_login(u);r=self.client.get(reverse('mobility_international_dashboard'))
  self.assertContains(r,reverse('ptjc_resumes:index'));self.assertContains(r,'Each task saves immediately')
 def test_noninternational_account_can_preview_public_builder(self):
  u=get_user_model().objects.create_user('revision-canadian');self.client.force_login(u)
  self.assertRedirects(self.client.get(reverse('ptjc_resumes:index')),reverse('ptjc_resumes:start'),fetch_redirect_response=False)
 def test_grande_prairie_reference_has_provenance_and_date(self):
  c=_canadian_context();key='Grande Prairie, Alberta'
  self.assertEqual(c['costs'][key]['rent'],'1444.5')
  self.assertEqual(c['citations'][key]['rent']['period'],'2025')
  self.assertIn({'city':'Grande Prairie','province':'Alberta'},c['community_directory'])
 def test_hub_keeps_international_in_separate_section(self):
  r=self.client.get(reverse('mobility_home'));self.assertNotContains(r,'Working in Canada');self.assertContains(r,'Trained outside Canada?');self.assertNotContains(r,'More career resources')

 def test_reopening_same_route_keeps_completed_tasks(self):
  from .planning import build
  from .models import InternationalChecklistItem
  u=get_user_model().objects.create_user('resume-route-user')
  profile=InternationalProfile.objects.create(email_verified_at=timezone.now(),user=u,country_of_education='India',destination_province='Alberta',application_history='new',registered_in_education_country='yes')
  key=build(profile)['steps'][0]['key'];InternationalChecklistItem.objects.create(profile=profile,key=key,completed=True)
  self.client.force_login(u)
  self.client.post(reverse('mobility_international_capture'),{'country':'India','province':'Alberta','applied':'not-applied','registration':'yes'})
  self.assertTrue(profile.checklist_items.get(key=key).completed)
