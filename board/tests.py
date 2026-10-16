from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import resolve, reverse
from django.utils import timezone

from .models import Employer, Invoice, Job, JobAlert, JobSeeker, PaymentGatewayConfig, PostingPackage, PurchasedPackage
from .sitemaps import JobSitemap
from .views import _gateway_context, admin_dashboard


@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ProductionRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('clinic', password='Testing123!')
        self.employer = Employer.objects.create(user=self.user, company_name='Test clinic', email='clinic@example.test', is_approved=True)
        self.package = PostingPackage.objects.create(code='test', name='Test package', price_cents=9900, credits=3)
        PaymentGatewayConfig.objects.create(use_stripe=True, stripe_public_key='pk_test_dummy', stripe_secret_key='sk_test_dummy')

    def test_external_login_redirect_is_rejected(self):
        response = self.client.post('/login/?next=https://untrusted.example/', {'username': 'clinic', 'password': 'Testing123!'})
        self.assertRedirects(response, reverse('employer_dashboard'), fetch_redirect_response=False)

    def test_local_login_redirect_is_preserved(self):
        response = self.client.post('/login/?next=/jobs/', {'username': 'clinic', 'password': 'Testing123!'})
        self.assertRedirects(response, '/jobs/', fetch_redirect_response=False)

    def test_unapproved_login_stays_blocked(self):
        self.employer.is_approved = False
        self.employer.save()
        response = self.client.post('/login/', {'username': 'clinic', 'password': 'Testing123!'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_custom_admin_dashboard_resolves(self):
        self.assertEqual(resolve('/admin/dashboard/').func, admin_dashboard)

    def test_admin_dashboard_rejects_nonstaff(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/admin/dashboard/').status_code, 403)

    def test_sitemap_excludes_expired_active_rows(self):
        today = timezone.localdate()
        expired = Job.objects.create(employer=self.employer, title='Expired', is_active=True, expiry_date=today-timedelta(days=1))
        current = Job.objects.create(employer=self.employer, title='Current', is_active=True, expiry_date=today)
        inactive = Job.objects.create(employer=self.employer, title='Draft', is_active=False)
        ids = set(JobSitemap().items().values_list('pk', flat=True))
        self.assertIn(current.pk, ids)
        self.assertNotIn(expired.pk, ids)
        self.assertNotIn(inactive.pk, ids)

    def test_public_key_aliases_work_with_current_field(self):
        self.assertEqual(_gateway_context()['stripe_publishable_key'], 'pk_test_dummy')

    def test_public_key_aliases_work_with_legacy_field(self):
        PaymentGatewayConfig.objects.update(stripe_public_key='', stripe_publishable_key='pk_legacy_dummy')
        self.assertEqual(_gateway_context()['stripe_public_key'], 'pk_legacy_dummy')
        self.assertTrue(_gateway_context()['use_stripe'])

    def paid_session(self, employer_id=None):
        return SimpleNamespace(payment_status='paid', amount_total=9900, metadata={'employer_id': str(employer_id or self.employer.pk), 'package_id': str(self.package.pk)})

    def test_paid_callback_is_idempotent_including_emails(self):
        self.client.force_login(self.user)
        with patch('stripe.checkout.Session.retrieve', return_value=self.paid_session()), patch('board.views.send_templated_email') as email:
            with self.captureOnCommitCallbacks(execute=True):
                first = self.client.get('/checkout/success/?session_id=cs_test_dummy')
            with self.captureOnCommitCallbacks(execute=True):
                second = self.client.get('/checkout/success/?session_id=cs_test_dummy')
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(PurchasedPackage.objects.count(), 1)
        self.assertEqual(email.call_count, 2)  # one admin + one customer message
        self.employer.refresh_from_db()
        self.assertEqual(self.employer.credits, 3)

    def test_credit_allocation_failure_rolls_back_invoice(self):
        self.client.force_login(self.user)
        with patch('stripe.checkout.Session.retrieve', return_value=self.paid_session()), patch('board.views.PurchasedPackage.objects.create', side_effect=RuntimeError('allocation failed')):
            with self.assertRaises(RuntimeError):
                self.client.get('/checkout/success/?session_id=cs_test_dummy')
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(PurchasedPackage.objects.exists())

    def test_other_employer_cannot_claim_payment(self):
        self.client.force_login(self.user)
        with patch('stripe.checkout.Session.retrieve', return_value=self.paid_session(self.employer.pk+100)):
            response = self.client.get('/checkout/success/?session_id=cs_test_dummy')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Invoice.objects.exists())

    def test_candidate_dashboard_on_fresh_migrations(self):
        user = get_user_model().objects.create_user('candidate', password='Testing123!')
        JobSeeker.objects.create(user=user, email='candidate@example.test', is_approved=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/jobseeker/dashboard/').status_code, 200)

    def test_alert_signup_persists_and_preserves_filters(self):
        data = {'email': 'alerts@example.test', 'q': 'Physiotherapist', 'location': 'Ottawa'}
        for _ in range(2):
            response = self.client.post('/job-alerts/signup/', data)
            self.assertEqual(response.status_code, 302)
        self.assertEqual(JobAlert.objects.count(), 1)
        alert = JobAlert.objects.get()
        self.assertEqual((alert.email, alert.q, alert.location, alert.active), ('alerts@example.test', 'Physiotherapist', 'Ottawa', True))

    def test_invalid_alert_is_not_recorded(self):
        self.assertEqual(self.client.post('/job-alerts/signup/', {'email': 'invalid'}).status_code, 200)
        self.assertFalse(JobAlert.objects.exists())

    def test_existing_alert_can_be_reactivated(self):
        alert = JobAlert.objects.create(email='alerts@example.test', active=False)
        self.client.post('/job-alerts/signup/', {'email': alert.email})
        alert.refresh_from_db()
        self.assertTrue(alert.active)

    def test_candidate_dashboard_never_queries_abandoned_career_fit(self):
        user = get_user_model().objects.create_user('candidate2', password='Testing123!')
        JobSeeker.objects.create(user=user, email='candidate2@example.test', is_approved=True)
        self.client.force_login(user)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/jobseeker/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any('careerfitlead' in query['sql'].lower() for query in queries))
