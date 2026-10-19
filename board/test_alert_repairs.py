from io import StringIO
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .alerts import unsubscribe_token
from .models import Employer, Job, JobAlert, JobAlertDelivery

@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AlertRepairTests(TestCase):
    def setUp(self):
        self.alert=JobAlert.objects.create(email='candidate@example.test',q='Physiotherapist',location='Toronto')
        u=get_user_model().objects.create_user('clinic')
        self.employer=Employer.objects.create(user=u,company_name='Clinic')
        self.job=Job.objects.create(employer=self.employer,title='Physiotherapist',location='Toronto, ON')
    def test_signup_page_has_real_form(self):
        self.assertContains(self.client.get('/job-alerts/signup/'),'name="email"')
    def test_preview_does_not_send_or_mark_jobs(self):
        call_command('send_job_alerts',stdout=StringIO())
        self.assertEqual(len(mail.outbox),0);self.assertFalse(JobAlertDelivery.objects.exists())
    def test_matching_delivery_includes_unsubscribe_and_does_not_repeat(self):
        Job.objects.create(employer=self.employer,title='Physiotherapist',location='Vancouver, BC')
        Job.objects.create(employer=self.employer,title='Physiotherapist',location='Toronto',is_active=False)
        Job.objects.create(employer=self.employer,title='Physiotherapist',location='Toronto',expiry_date=timezone.localdate()-timedelta(days=1))
        for _ in range(2):call_command('send_job_alerts',send=True,stdout=StringIO())
        self.assertEqual(len(mail.outbox),1);self.assertIn('Unsubscribe:',mail.outbox[0].body)
        self.assertEqual(list(JobAlertDelivery.objects.values_list('job_id',flat=True)),[self.job.pk])
    def test_email_failure_does_not_mark_sent(self):
        with patch('board.management.commands.send_job_alerts.EmailMessage.send',side_effect=RuntimeError('offline')):
            with self.assertRaises(CommandError):call_command('send_job_alerts',send=True,stdout=StringIO(),stderr=StringIO())
        self.assertFalse(JobAlertDelivery.objects.exists())
    def test_unsubscribe_get_is_confirmation_post_disables(self):
        path=reverse('job_alert_unsubscribe',args=[unsubscribe_token(self.alert)])
        self.assertEqual(self.client.get(path).status_code,200)
        self.alert.refresh_from_db();self.assertTrue(self.alert.active)
        self.assertContains(self.client.post(path),'You’re unsubscribed')
        self.alert.refresh_from_db();self.assertFalse(self.alert.active)
        call_command('send_job_alerts',send=True,stdout=StringIO());self.assertEqual(len(mail.outbox),0)
    def test_tampered_unsubscribe_is_rejected(self):
        path=reverse('job_alert_unsubscribe',args=[unsubscribe_token(self.alert)+'bad'])
        self.assertEqual(self.client.post(path).status_code,404)
        self.alert.refresh_from_db();self.assertTrue(self.alert.active)
