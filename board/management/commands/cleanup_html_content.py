import re
import html

from django.core.management.base import BaseCommand
from django.utils.html import strip_tags

from board.models import Employer, Job


_whitespace_re = re.compile(r"\s+")


def clean_text(value: str) -> str:
    if not value:
        return ""

    # 1) Convert &lt;div&gt; etc back into real tags so strip_tags can remove them
    v = html.unescape(value)

    # 2) Strip real HTML tags
    v = strip_tags(v)

    # 3) Normalize whitespace
    v = _whitespace_re.sub(" ", v).strip()

    return v


class Command(BaseCommand):
    help = "Strip HTML (including HTML-escaped tags) from Employer.company_description and Job.description."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Do not write changes.")
        parser.add_argument("--limit", type=int, default=0, help="Optional limit (0 = no limit).")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"] or 0

        employers_cleaned = 0
        jobs_cleaned = 0

        # Employers
        qs_e = Employer.objects.all().only("id", "company_description")
        if limit:
            qs_e = qs_e[:limit]

        for e in qs_e:
            original = e.company_description or ""
            cleaned = clean_text(original)
            if cleaned != original:
                employers_cleaned += 1
                if not dry_run:
                    e.company_description = cleaned
                    e.save(update_fields=["company_description"])

        # Jobs
        qs_j = Job.objects.all().only("id", "description")
        if limit:
            qs_j = qs_j[:limit]

        for j in qs_j:
            original = j.description or ""
            cleaned = clean_text(original)
            if cleaned != original:
                jobs_cleaned += 1
                if not dry_run:
                    j.description = cleaned
                    j.save(update_fields=["description"])

        self.stdout.write(
            self.style.SUCCESS(
                "HTML cleanup complete:\n"
                f"  Employers cleaned: {employers_cleaned}\n"
                f"  Jobs cleaned: {jobs_cleaned}\n"
                f"  Dry-run: {dry_run}"
            )
        )
