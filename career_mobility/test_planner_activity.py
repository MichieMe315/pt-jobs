from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import InternationalActivity, InternationalProfile


@override_settings(ALLOWED_HOSTS=['testserver'])
class PlannerActivityTests(TestCase):
    answers = dict(country='Philippines', province='British Columbia',
                   applied='not-applied', registration='yes')

    @patch('career_mobility.geolocation.visitor_country', return_value='United Arab Emirates')
    def test_guest_plan_is_counted_without_saving_or_creating_account(self, country):
        url = reverse('mobility_international_plan')
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get(url, dict(self.answers, build='1')).status_code, 302)
        event = InternationalActivity.objects.get(action='planner_generated')
        self.assertIsNone(event.profile_id)
        self.assertEqual(event.education_country, 'Philippines')
        self.assertEqual(event.visitor_country, 'United Arab Emirates')
        self.assertEqual(event.destination_province, 'British Columbia')
        self.assertFalse(InternationalProfile.objects.exists())
        self.assertFalse(InternationalActivity.objects.filter(action='planner_saved').exists())
        self.assertTrue(InternationalActivity.objects.filter(action='planner_viewed').exists())

        self.client.force_login(get_user_model().objects.create_superuser('activity-admin'))
        report = self.client.get(reverse('admin:career_mobility_internationalactivity_changelist'))
        self.assertContains(report, 'International planner usage')
        self.assertEqual(report.context['activity_totals']['guest_results'], 1)
        self.assertEqual(self.client.get(
            reverse('admin:career_mobility_internationalactivity_changelist'),
            {'destination_province__exact': 'Ontario'},
        ).context['activity_totals']['planner_results'], 0)

    def test_preview_counts_valid_results_and_honors_guest_privacy_signal(self):
        url = reverse('mobility_international_preview')
        self.assertEqual(self.client.get(url).status_code, 400)
        self.assertEqual(self.client.get(url, self.answers, HTTP_SEC_GPC='1').status_code, 200)
        self.assertFalse(InternationalActivity.objects.exists())
        self.assertEqual(self.client.get(url, self.answers).status_code, 200)
        self.assertEqual(InternationalActivity.objects.filter(action='planner_generated').count(), 1)

    def test_dashboard_all_time_includes_older_unsaved_plans(self):
        from datetime import timedelta
        from django.utils import timezone
        admin = get_user_model().objects.create_superuser('dashboard-admin')
        self.client.force_login(admin)
        event = InternationalActivity.objects.create(
            action='planner_generated', education_country='Philippines',
            visitor_country='United Arab Emirates', destination_province='British Columbia')
        InternationalActivity.objects.filter(pk=event.pk).update(
            created_at=timezone.now() - timedelta(days=400))
        url = reverse('admin:task_workspace', args=['international'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['planner']['days'], 'all')
        self.assertEqual(response.context['planner']['totals']['guest_plans'], 1)
        self.assertContains(response, 'Philippines')
        self.assertNotContains(response, '?action__exact=account_created')
        self.assertEqual(self.client.get(url, {'days': '7'}).context[
            'planner']['totals']['plans'], 0)
        self.assertEqual(self.client.get(url, {'days': 'invalid'}).context[
            'planner']['totals']['plans'], 1)

    def test_dashboard_hides_activity_without_view_permission(self):
        from django.contrib.auth.models import Permission
        staff = get_user_model().objects.create_user('profiles-only', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(
            content_type__app_label='career_mobility', codename='view_internationalprofile'))
        self.client.force_login(staff)
        response = self.client.get(reverse('admin:task_workspace', args=['international']))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context['planner'])
        self.assertNotContains(response, 'Search all activity')
