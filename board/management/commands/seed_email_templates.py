from django.core.management.base import BaseCommand
from board.models import EmailTemplate

# NOTE:
# - Keep tokens SIMPLE: {{ job_title }}, {{ package_name }}, {{ email }}, {{ site_name }}, etc.
# - This matches your views.py send_templated_email() which does simple string replacement.

# key, subject, html
TEMPLATES = [
    # ============================================================
    # Admin notifications (signup + approval)
    # ============================================================
    (
        "admin_new_employer",
        "Admin: New Employer Signup",
        "<p>A new employer signed up: <strong>{{ email }}</strong></p>",
    ),
    (
        "admin_new_jobseeker",
        "Admin: New Job Seeker Signup",
        "<p>A new job seeker signed up: <strong>{{ email }}</strong></p>",
    ),
    (
        "employer_approved",
        "Your Employer Account Has Been Approved",
        "<p>Hi {{ email }},</p>"
        "<p>Your employer account has been approved. You can now log in and post jobs.</p>"
        "<p>Log in: {{ login_url }}</p>",
    ),
    (
        "jobseeker_approved",
        "Your Job Seeker Account Has Been Approved",
        "<p>Hi {{ email }},</p>"
        "<p>Your job seeker account has been approved. You can now log in and apply to jobs.</p>"
        "<p>Log in: {{ login_url }}</p>",
    ),

    # ============================================================
    # Your required list (using SIMPLE tokens)
    # ============================================================
    (
        "application_email_to_employer",
        "New Application Received: {{ job_title }}",
        "<p>You received a new application for: <strong>{{ job_title }}</strong></p>"
        "<p>Employer: {{ employer_name }}</p>"
        "<p>View applications in your dashboard: {{ dashboard_url }}</p>",
    ),
    (
        "email_verification",
        "Verify Your Email",
        "<p>Please verify your email address by clicking this link:</p>"
        "<p>{{ verify_url }}</p>",
    ),
    (
        "employer_welcome",
        "Employer Signup Received",
        "<p>Hi {{ email }},</p>"
        "<p>Thanks for signing up. Your employer account is pending admin approval.</p>"
        "<p>You will receive an email once your account is approved.</p>",
    ),
    (
        "job_alert",
        "Job Alert: New opportunities available",
        "<p>New physiotherapy jobs matching your alert are available.</p>"
        "<p>Browse: {{ jobs_url }}</p>",
    ),
    (
        "job_expiration_notice",
        "Job Expiration Notice: {{ job_title }}",
        "<p>Your job posting <strong>{{ job_title }}</strong> is expiring soon.</p>"
        "<p>Manage your jobs here: {{ dashboard_url }}</p>",
    ),
    (
        "job_posting_confirmation",
        "Job Posting Confirmation: {{ job_title }}",
        "<p>Your job <strong>{{ job_title }}</strong> has been posted.</p>"
        "<p>View it here: {{ job_url }}</p>",
    ),
    (
        "jobseeker_application_confirmation",
        "Application Confirmation: {{ job_title }}",
        "<p>Thanks for applying to <strong>{{ job_title }}</strong>.</p>"
        "<p>You can review your applications here: {{ dashboard_url }}</p>",
    ),
    (
        "jobseeker_welcome",
        "Job Seeker Signup Received",
        "<p>Hi {{ email }},</p>"
        "<p>Thanks for signing up. Your account is pending admin approval.</p>"
        "<p>You will receive an email once your account is approved.</p>",
    ),
    (
        "order_confirmation",
        "Order Confirmation: {{ package_name }}",
        "<p>Thanks for your purchase of <strong>{{ package_name }}</strong>.</p>"
        "<p>Amount: {{ amount }}</p>"
        "<p>Your posting credits will be available in your dashboard.</p>",
    ),
    (
        "password_recovery",
        "Password Recovery",
        "<p>Reset your password using the link below:</p>"
        "<p>{{ reset_url }}</p>",
    ),
    (
        "product_expiration_notice",
        "Package Expiration Notice: {{ package_name }}",
        "<p>Your posting package <strong>{{ package_name }}</strong> is expiring soon.</p>"
        "<p>Manage packages: {{ dashboard_url }}</p>",
    ),
    (
        "recurring_payment_failed",
        "Recurring Payment Failed",
        "<p>Your recurring payment failed.</p>"
        "<p>Please update your payment method.</p>",
    ),
    (
        "recurring_subscription_canceled",
        "Recurring Subscription Canceled",
        "<p>Your recurring subscription has been canceled.</p>",
    ),
    (
        "resume_expiration_notice",
        "Resume Expiration Notice",
        "<p>One of your resumes is expiring soon.</p>"
        "<p>Manage resumes: {{ dashboard_url }}</p>",
    ),
    (
        "resume_posting_confirmation",
        "Resume Posting Confirmation",
        "<p>Your resume has been posted.</p>"
        "<p>Manage resumes: {{ dashboard_url }}</p>",
    ),
]


class Command(BaseCommand):
    help = "Seeds required email templates if missing (safe upsert by default). Use --force to overwrite."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite subject/html for existing templates as well (use carefully).",
        )

    def handle(self, *args, **kwargs):
        force = bool(kwargs.get("force"))
        created = 0
        updated = 0

        for key, subject, html in TEMPLATES:
            obj, was_created = EmailTemplate.objects.get_or_create(
                key=key,
                defaults={"subject": subject, "html": html, "is_enabled": True},
            )
            if was_created:
                created += 1
                continue

            # Existing template: default is SAFE upsert (do not overwrite admin edits)
            changed = False

            if force:
                if obj.subject != subject:
                    obj.subject = subject
                    changed = True
                if obj.html != html:
                    obj.html = html
                    changed = True
                if obj.is_enabled is False:
                    obj.is_enabled = True
                    changed = True
            else:
                # Only fill blanks safely
                if not obj.subject:
                    obj.subject = subject
                    changed = True
                if not obj.html:
                    obj.html = html
                    changed = True
                if obj.is_enabled is None:
                    obj.is_enabled = True
                    changed = True

            if changed:
                obj.save(update_fields=["subject", "html", "is_enabled"])
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete. created={created} updated={updated} force={force}"
            )
        )
