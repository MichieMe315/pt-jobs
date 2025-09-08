from django.core.management.base import BaseCommand
from board.models import Application
import csv
from django.utils.timezone import localtime

class Command(BaseCommand):
    help = "Export applications to CSV"

    def add_arguments(self, parser):
        parser.add_argument("--path", default="applications_export.csv", help="Output CSV path")

    def handle(self, *args, **opts):
        path = opts["path"]
        qs = Application.objects.select_related("job", "job__employer").order_by("-created_at")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["application_id", "job_id", "job_title", "employer", "name", "email", "resume_url", "created_at", "cover_letter"])
            for a in qs:
                resume_url = ""
                try:
                    if a.resume and hasattr(a.resume, "url"):
                        resume_url = a.resume.url
                except ValueError:
                    resume_url = ""
                w.writerow([
                    a.id, a.job_id, a.job.title, str(a.job.employer),
                    a.name, a.email, resume_url, localtime(a.created_at).isoformat(),
                    (a.cover_letter or "").replace("\r", " ").replace("\n", " ").strip()[:1000],
                ])
        self.stdout.write(self.style.SUCCESS(f"Exported {qs.count()} applications → {path}"))
