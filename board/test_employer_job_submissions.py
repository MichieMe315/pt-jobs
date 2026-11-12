from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Employer, Job, PostingPackage, PurchasedPackage


@override_settings(ALLOWED_HOSTS=["testserver"])
class EmployerJobSubmissionTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("employer")
        self.employer = Employer.objects.create(user=user, is_approved=True)
        package = PostingPackage.objects.create(
            code="five-sixty-days", name="5 × 60 days", credits=5,
            price_cents=25000, duration_days=60,
        )
        self.purchase = PurchasedPackage.objects.create(
            employer=self.employer, package=package, credits_granted=5,
            credits_remaining=5, duration_days=60,
        )
        self.client.force_login(user)
        self.data = {
            "title": "Physiotherapist",
            "description": "Provide assessments and treatment at our clinic.",
            "job_type": "full_time",
            "location": "Ottawa, ON",
            "relocation_assistance": "no",
            "action": "publish",
        }

    def test_live_edit_keeps_one_published_job_one_debit_and_one_notice(self):
        with patch("board.publication.notify_publication") as notify:
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(reverse("job_create"), self.data)
                job = Job.objects.get()
                edit_url = reverse("job_edit", args=[job.pk])
                for title in ("Updated job", "Final job"):
                    # An edit form opened before deployment can send Save Draft.
                    self.client.post(edit_url, {**self.data, "action": "draft", "title": title})
                    self.client.post(edit_url, {**self.data, "title": title})

        job.refresh_from_db()
        self.purchase.refresh_from_db()
        self.employer.refresh_from_db()
        self.assertEqual(
            (Job.objects.count(), self.purchase.credits_remaining, notify.call_count),
            (1, 4, 1),
        )
        self.assertEqual(self.employer.credits, 4)
        self.assertTrue(job.is_active)
        self.assertEqual(job.title, "Final job")
        self.assertEqual(job.expiry_date, timezone.localdate() + timedelta(days=59))
        edit = self.client.get(edit_url)
        self.assertContains(edit, "Save Changes")
        self.assertNotContains(edit, "Save Draft")
        self.assertNotContains(edit, "continue to payment")

    def test_create_form_retry_spends_one_credit(self):
        url = reverse("job_create")
        form = self.client.get(url)
        token = form.context["submission_token"]
        self.assertContains(form, token)
        with patch("board.publication.notify_publication") as notify:
            with self.captureOnCommitCallbacks(execute=True):
                for _ in range(3):
                    self.client.post(url, {**self.data, "submission_token": token})

            notify.assert_called_once_with(Job.objects.get().pk)

        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.credits_remaining, 4)

    def test_duplicate_form_retry_spends_one_credit(self):
        original = Job.objects.create(employer=self.employer, title="Original")
        url = reverse("job_duplicate", args=[original.pk])
        token = self.client.get(url).context["submission_token"]
        with patch("board.publication.notify_publication") as notify:
            with self.captureOnCommitCallbacks(execute=True):
                for _ in range(2):
                    self.client.post(url, {**self.data, "submission_token": token})

            copy = Job.objects.exclude(pk=original.pk).get()
            notify.assert_called_once_with(copy.pk)

        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.credits_remaining, 4)
