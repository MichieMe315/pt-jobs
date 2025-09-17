# board/management/commands/seed_email_templates.py
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from board.models import EmailTemplate


TEMPLATES = [
    {
        "slug": "application_email_to_employer",
        "title": "Application Email to Employer",
        "is_active": True,
        "subject": "New Application for {{ job.title }}",
        "body": (
            "Hello {{ employer.company_name|default:employer.name }},\n\n"
            "You received a new application to your job posting {{ job.title }} from the following applicant:\n\n"
            "Name: {{ application.name }}\n"
            "Email: {{ application.email }}\n\n"
            "Cover Letter:\n{{ application.cover_letter|default:\"(none)\" }}\n\n"
            "View all applications: {{ employer_dashboard_url }}\n\n"
            "Thanks,\n"
            "The PhysiotherapyJobsCanada team"
        ),
    },
    {
        "slug": "email_verification",
        "title": "Email Verification",
        "is_active": True,
        "subject": "Verify your email",
        "body": (
            "Hi {{ user.username }},\n\n"
            "Please verify your email address by clicking the link below:\n"
            "{{ verification_url }}\n\n"
            "If you didn’t create an account, you can ignore this message."
        ),
    },
    {
        "slug": "employer_welcome",
        "title": "Employer Welcome Email",
        "is_active": True,
        "subject": "Welcome to PhysiotherapyJobsCanada",
        "body": (
            "Hi {{ employer.name }},\n\n"
            "Welcome to PhysiotherapyJobsCanada! Your employer account is now set up.\n"
            "You can post jobs, manage applications, and view invoices from your dashboard:\n"
            "{{ employer_dashboard_url }}\n\n"
            "Thanks for joining us!"
        ),
    },
    {
        "slug": "job_alert",
        "title": "Job Alert",
        "is_active": True,
        "subject": "New jobs that match: {{ alert.q|default:\"Your criteria\" }}",
        "body": (
            "Hi,\n\n"
            "Here are new jobs that match your alert {{ alert.q }} "
            "{% if alert.location %}in {{ alert.location }}{% endif %}:\n\n"
            "{% for job in jobs %}- {{ job.title }} at {{ job.employer.company_name|default:job.employer.name }} ({{ job.location }})\n"
            "  {{ site_url }}{% url 'job_detail' job.pk %}\n{% empty %}"
            "No new jobs this time.\n{% endfor %}\n\n"
            "Manage alerts or unsubscribe at: {{ manage_alerts_url }}"
        ),
    },
    {
        "slug": "job_expiration_notice",
        "title": "Job Expiration Notice",
        "is_active": True,
        "subject": "Your job is expiring soon: {{ job.title }}",
        "body": (
            "Hi {{ employer.name }},\n\n"
            "Your job posting {{ job.title }} will expire on {{ job.expiry_date }}.\n"
            "To extend or repost, visit your dashboard: {{ employer_dashboard_url }}"
        ),
    },
    {
        "slug": "job_posting_confirmation",
        "title": "Job Posting Confirmation",
        "is_active": True,
        "subject": "Job posted: {{ job.title }}",
        "body": (
            "Hi {{ employer.name }},\n\n"
            "Your job {{ job.title }} is now live.\n"
            "View it here: {{ site_url }}{% url 'job_detail' job.pk %}\n\n"
            "Manage your postings: {{ employer_dashboard_url }}"
        ),
    },
    {
        "slug": "jobseeker_application_confirmation",
        "title": "Job Seeker Application Confirmation",
        "is_active": False,
        "subject": "We sent your application for {{ job.title }}",
        "body": (
            "Hi {{ jobseeker.first_name }},\n\n"
            "Thanks for applying to {{ job.title }} at {{ job.employer.company_name|default:job.employer.name }}.\n"
            "We’ve sent your application to the employer.\n\n"
            "You can track your applications here: {{ jobseeker_dashboard_url }}"
        ),
    },
    {
        "slug": "jobseeker_welcome",
        "title": "Job Seeker Welcome Email",
        "is_active": True,
        "subject": "Welcome to PhysiotherapyJobsCanada",
        "body": (
            "Hi {{ jobseeker.first_name }},\n\n"
            "Welcome! Your job seeker account is set up. You can upload resumes and start applying here:\n"
            "{{ jobseeker_dashboard_url }}"
        ),
    },
    {
        "slug": "order_confirmation",
        "title": "Order Confirmation",
        "is_active": True,
        "subject": "Order confirmation: {{ order.number }}",
        "body": (
            "Hi {{ employer.name }},\n\n"
            "Thanks for your purchase.\n"
            "Product: {{ package.name }}\n"
            "Price: {{ package.price_cents|floatformat:-2 }}\n"
            "Credits: {{ purchased.credits_total }}\n\n"
            "Your invoice is available here: {{ invoice_url }}"
        ),
    },
    {
        "slug": "password_recovery",
        "title": "Password Recovery",
        "is_active": True,
        "subject": "Reset your password",
        "body": (
            "Hi {{ user.username }},\n\n"
            "You can reset your password using the link below:\n"
            "{{ reset_url }}\n\n"
            "If you didn’t request this, you can ignore this email."
        ),
    },
    {
        "slug": "product_expiration_notice",
        "title": "Product Expiration Notice",
        "is_active": True,
        "subject": "Your posting package is expiring soon",
        "body": (
            "Hi {{ employer.name }},\n\n"
            "Your package {{ package.name }} will expire on {{ purchased.expires_at }}.\n"
            "Renew here: {{ packages_url }}"
        ),
    },
    {
        "slug": "recurring_payment_failed",
        "title": "Recurring Payment Failed",
        "is_active": True,
        "subject": "Payment failed for your subscription",
        "body": (
            "Hi {{ employer.name }},\n\n"
            "We couldn’t process your latest subscription payment. Please update your billing details:\n"
            "{{ billing_portal_url }}"
        ),
    },
    {
        "slug": "recurring_subscription_canceled",
        "title": "Recurring Subscription Canceled",
        "is_active": False,
        "subject": "Your subscription has been canceled",
        "body": (
            "Hi {{ employer.name }},\n\n"
            "Your subscription has been canceled. If this was a mistake, you can re-subscribe here:\n"
            "{{ subscribe_url }}"
        ),
    },
    {
        "slug": "resume_expiration_notice",
        "title": "Resume Expiration Notice",
        "is_active": True,
        "subject": "Your resume will be archived soon",
        "body": (
            "Hi {{ jobseeker.first_name }},\n\n"
            "Your resume {{ resume.title }} will be archived on {{ resume.expiry_date }}.\n"
            "You can upload a new version here: {{ jobseeker_dashboard_url }}"
        ),
    },
    {
        "slug": "resume_posting_confirmation",
        "title": "Resume Posting Confirmation",
        "is_active": True,
        "subject": "Resume uploaded successfully",
        "body": (
            "Hi {{ jobseeker.first_name }},\n\n"
            "We’ve received your resume {{ resume.title }}.\n"
            "Manage your resumes here: {{ jobseeker_dashboard_url }}"
        ),
    },
]


class Command(BaseCommand):
    help = "Seed default email templates (idempotent)."

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        updated = 0
        for t in TEMPLATES:
            obj, was_created = EmailTemplate.objects.update_or_create(
                slug=t["slug"],
                defaults={
                    "title": t["title"],
                    "is_active": t["is_active"],
                    "subject": t["subject"],
                    "body": t["body"],
                },
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Email templates seeded. Created: {created}, Updated: {updated}"
            )
        )
