from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage, get_connection
from django.test import TestCase, override_settings
from django.urls import reverse

from .admin_section_models import (
    AffiliateCommission, AffiliatePartner, AffiliateProgram, AffiliateReferral,
    EmailDeliveryLog, SignupAnswer, SignupQuestion, WebsitePage,
)
from .models import Invoice


@override_settings(EMAIL_BACKEND="board.email_audit_backend.EmailBackend",
                   PTJC_EMAIL_TRANSPORT="django.core.mail.backends.locmem.EmailBackend")
class OperationsSectionsTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_superuser("operations-staff")
        self.client.force_login(self.staff)

    def test_admin_publish_updates_navigation_and_draft_is_private(self):
        page = WebsitePage.objects.create(title="Accessibility policy", slug="accessibility",
                                          body="<script>untrusted</script>", header=True, footer=True)
        public = reverse("website_page", args=[page.slug])
        self.assertEqual(self.client.get(public).status_code, 404)
        response = self.client.post(reverse("admin:board_websitepage_change", args=[page.pk]), {
            "title": page.title, "slug": page.slug, "body": page.body, "seo_description": "Site accessibility",
            "published": "on", "header": "on", "footer": "on", "position": 10, "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        self.assertContains(self.client.get(reverse("employer_signup")), page.title, count=2)
        response = self.client.get(public)
        self.assertContains(response, "&lt;script&gt;untrusted&lt;/script&gt;")
        self.assertNotContains(response, "<script>untrusted</script>")

    def employer_payload(self):
        return {"email": "clinic@example.test", "company_name": "Example Clinic", "location": "Toronto",
                "password1": "Sample-Password-863", "password2": "Sample-Password-863"}

    def test_signup_question_required_for_its_audience_and_answer_saved(self):
        question = SignupQuestion.objects.create(audience="employer", label="Clinic focus", kind="choice",
                                                 options="Sports\nPaediatrics", required=True, enabled=True)
        key = f"extra_{question.pk}"
        self.client.logout()
        self.assertNotContains(self.client.get(reverse("jobseeker_signup")), "Clinic focus")
        url = reverse("employer_signup")
        for data in ({}, {key: "Other"}):
            self.assertEqual(self.client.post(url, {**self.employer_payload(), **data}).status_code, 200)
            self.assertFalse(SignupAnswer.objects.exists())
        self.assertEqual(self.client.post(url, {**self.employer_payload(), key: "Sports"}).status_code, 302)
        answer = SignupAnswer.objects.get()
        self.assertEqual((answer.answer, answer.label_at_signup), ("Sports", "Clinic focus"))

    def test_affiliate_application_referral_commission_and_manual_payout(self):
        program = AffiliateProgram.objects.get(pk=1)
        self.assertFalse(program.enabled)
        program.enabled = program.applications_open = True
        program.terms = "Test terms."
        program.default_rate = 15
        program.save()
        partner_user = get_user_model().objects.create_user("partner")
        self.client.force_login(partner_user)
        self.assertEqual(self.client.post(reverse("affiliate_apply"), {"accept": "on"}).status_code, 302)
        partner = AffiliatePartner.objects.get(user=partner_user)
        link = reverse("affiliate_link", args=[partner.code])
        self.assertEqual(self.client.get(link).status_code, 404)
        self.client.force_login(self.staff)
        approved = self.client.post(reverse("admin:board_affiliatepartner_changelist"), {
            "action": "approve", "index": 0, "_selected_action": partner.pk,
        })
        self.assertEqual(approved.status_code, 302)
        self.client.logout()
        self.assertRedirects(self.client.get(link), reverse("employer_signup"))
        self.assertEqual(self.client.post(reverse("employer_signup"), self.employer_payload()).status_code, 302)
        referral = AffiliateReferral.objects.get(partner=partner)
        invoice = Invoice.objects.create(employer=referral.user.employer, amount=1999, currency="CAD", status="paid")
        self.client.force_login(self.staff)
        url = reverse("admin:board_affiliatecommission_add")
        result = self.client.post(url, {"invoice": invoice.pk, "_save": "Save"})
        self.assertEqual(result.status_code, 302, result.context and result.context["adminform"].form.errors)
        commission = AffiliateCommission.objects.get(invoice=invoice)
        self.assertEqual(commission.cents, 300)
        self.assertEqual(self.client.post(url, {"invoice": invoice.pk, "_save": "Save"}).status_code, 200)
        result = self.client.post(reverse("admin:board_affiliatecommission_change", args=[commission.pk]), {
            "payment_reference": "External payment 42", "confirm_payment": "on", "_save": "Save",
        })
        self.assertEqual(result.status_code, 302)
        commission.refresh_from_db()
        self.assertIsNotNone(commission.paid_at)
        self.assertEqual(commission.payment_reference, "External payment 42")

    def test_email_log_uses_configured_transport_and_requires_permission(self):
        EmailMessage("Example subject", "Private message body", "info@example.test",
                     ["recipient@example.test"], connection=get_connection()).send()
        entry = EmailDeliveryLog.objects.get()
        self.assertEqual((entry.outcome, entry.recipients), ("submitted", "recipient@example.test"))
        url = reverse("admin:board_emaildeliverylog_changelist")
        self.assertContains(self.client.get(url, {"q": "recipient"}), "Example subject")
        self.assertNotContains(self.client.get(url), "Private message body")
        self.client.force_login(get_user_model().objects.create_user("limited-staff", is_staff=True))
        self.assertEqual(self.client.get(url).status_code, 403)
