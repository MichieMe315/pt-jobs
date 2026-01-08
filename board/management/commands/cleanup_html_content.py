from django.core.management.base import BaseCommand
from django.utils.html import strip_tags

from board.models import Employer, Job


class Command(BaseCommand):
    help = "Strip HTML from existing Employer and Job text fields (one-time cleanup)."

    def handle(self, *args, **options):
        employers_cleaned = 0
        jobs_cleaned = 0

        # ---- Employers ----
        for employer in Employer.objects.all():
            original = employer.company_description or ""
            cleaned = strip_tags(original).strip()

            if cleaned != original:
                employer.company_description = cleaned
                employer.save(update_fields=["company_description"])
                employers_cleaned += 1

        # ---- Jobs ----
        for job in Job.objects.all():
            original = job.description or ""
            cleaned = strip_tags(original).strip()

            if cleaned != original:
                job.description = cleaned
                job.save(update_fields=["description"])
                jobs_cleaned += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"HTML cleanup complete:\n"
                f"  Employers cleaned: {employers_cleaned}\n"
                f"  Jobs cleaned: {jobs_cleaned}"
            )
        )
