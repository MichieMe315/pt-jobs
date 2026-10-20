import json
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import include, path, reverse, resolve, Resolver404
from board.models import JobSeeker
from .models import SavedCareerPlan

urlpatterns = [path('', include('board.urls')), path('career-resources/', include('career_mobility.release_urls'))]

@override_settings(ROOT_URLCONF=__name__)
class FirstReleaseRoutesTests(TestCase):
    def test_public_pages_render_without_draft_routes(self):
        for route in ('mobility_home','mobility_salary_comparison'):
            self.assertEqual(self.client.get(reverse(route)).status_code,200)
    def test_unfinished_endpoints_are_not_published(self):
        for url in ('/career-resources/canadian/','/career-resources/canadian/full/','/career-resources/international/','/career-resources/international/register/','/career-resources/shop/','/shop/','/career-resources/salary-comparison/clinic-offer-guide/'):
            with self.assertRaises(Resolver404):resolve(url)
    def test_dashboard_does_not_reverse_unpublished_links(self):
        user=get_user_model().objects.create_user(username='release-route-candidate')
        JobSeeker.objects.create(user=user,is_approved=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('jobseeker_dashboard')).status_code,200)
    def test_save_load_and_pdf_for_approved_candidate(self):
        user=get_user_model().objects.create_user(username='release-salary-candidate')
        JobSeeker.objects.create(user=user,is_approved=True)
        self.client.force_login(user)
        inputs={'employee-type':'annual','employee-pay':'85000','billing':'100','split':'60','visits':'8','days':'5','weeks':'48'}
        r=self.client.post(reverse('mobility_salary_save'),json.dumps({'plan_type':'salary','inputs':inputs}),content_type='application/json')
        self.assertEqual(r.status_code,200)
        pk=r.json()['id']
        self.assertEqual(self.client.get(reverse('mobility_salary_load',args=[pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('mobility_plan_pdf',args=[pk])).status_code,200)
        self.assertContains(self.client.get(reverse('jobseeker_dashboard')),'Reopen comparison')
    def test_legacy_save_cannot_save_relocation(self):
        user=get_user_model().objects.create_user(username='release-no-relocation')
        JobSeeker.objects.create(user=user,is_approved=True)
        self.client.force_login(user)
        r=self.client.post(reverse('mobility_save_plan'),json.dumps({'plan_type':'relocation','inputs':{'origin':'Toronto'}}),content_type='application/json')
        self.assertEqual(r.status_code,400)
        self.assertFalse(SavedCareerPlan.objects.filter(user=user).exists())
