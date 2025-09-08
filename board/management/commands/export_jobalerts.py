from django.core.management.base import BaseCommand
from board.models import JobAlert
import csv
from django.utils.timezone import localtime

class Command(BaseCommand):
    help = "Export job alerts to CSV"

    def add_arguments(self, parser):
        parser.add_argument("--path", default="jobalerts_export.csv", help="Output CSV path")

    def handle(self, *args, **opts):
        path = opts["path"]
        qs = JobAlert.objects.order_by("-created_at")
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["email", "query", "location", "is_active", "created_at"])
            for a in qs:
                w.writerow([
                    a.email, a.q, a.location, a.is_active, localtime(a.created_at).isoformat()
                ])
        self.stdout.write(self.style.SUCCESS(f"Exported {qs.count()} job alerts → {path}"))
