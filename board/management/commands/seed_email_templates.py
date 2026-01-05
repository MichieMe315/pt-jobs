from django.core.management.base import BaseCommand
from board.models import EmailTemplate

# key, subject, html
TEMPLATES = [
    ("application_email_to_employer", "New Application", "A new application was received."),
    ("employer_welcome", "Welcome", "Thanks for signing up. Your account is pending approval."),
    ("jobseeker_welcome", "Welcome", "Thanks for signing up. Your account is pending approval."),
    ("job_posting_confirmation", "Job Posting Confirmation", "Your job '{{ job.title }}' has been posted."),
    ("jobseeker_application_confirmation", "Application Confirmation", "Thanks for applying."),
    ("order_confirmation", "Order Confirmation", "Thanks for your purchase of {{ package.name }}."),
    ("password_recovery", "Password Recovery", "Reset your password."),
    ("job_expiration_notice", "Job Expiration Notice", "One of your jobs is expiring soon."),
    ("product_expiration_notice", "Package Expiration Notice", "Your package is expiring soon."),
    ("admin_new_employer", "Admin: New Employer", "A new employer has signed up."),
    ("admin_new_jobseeker", "Admin: New Jobseeker", "A new jobseeker has signed up."),
]

class Command(BaseCommand):
    help = "Seeds common email templates if missing (safe upsert)."

    def handle(self, *args, **kwargs):
        created = 0
        updated = 0

        for key, subject, html in TEMPLATES:
            obj, was_created = EmailTemplate.objects.get_or_create(
                key=key,
                defaults={"subject": subject, "html": html, "is_enabled": True},
            )
            if was_created:
                created += 1
            else:
                # Keep admin edits; only fill blanks safely
                changed = False
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

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} templates, updated {updated} existing."))
