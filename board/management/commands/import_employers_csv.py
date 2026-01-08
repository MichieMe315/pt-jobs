import csv
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from board.models import Employer

User = get_user_model()


class Command(BaseCommand):
    help = "Import Employers from CSV (creates Users + Employers)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.is_absolute():
            csv_path = Path(settings.BASE_DIR) / csv_path

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV not found: {csv_path}")

        dry_run = options["dry_run"]

        created_users = 0
        created_employers = 0
        updated_employers = 0
        skipped = 0

        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            if "Employer Email" not in reader.fieldnames:
                raise ValueError(
                    f"CSV must include 'Employer Email'. Found: {reader.fieldnames}"
                )

            for row in reader:
                email = (row.get("Employer Email") or "").strip().lower()
                if not email:
                    skipped += 1
                    continue

                # ---- USER ----
                user = User.objects.filter(email=email).first()
                if not user:
                    if dry_run:
                        created_users += 1
                        user = None
                    else:
                        user = User.objects.create_user(
                            username=email,
                            email=email,
                            password=None,
                            is_active=True,
                        )
                        created_users += 1

                # ---- EMPLOYER ----
                employer = Employer.objects.filter(email=email).first()

                # CLEAN + SANITIZE DESCRIPTION (CRITICAL FIX)
                raw_desc = row.get("Company Description") or row.get("Description") or ""
                company_description = strip_tags(raw_desc).strip()

                data = {
                    "user": user,
                    "email": email,
                    "name": (row.get("Full Name") or "").strip(),
                    "company_name": (row.get("Company Name") or "").strip(),
                    "company_description": company_description,
                    "phone": (row.get("Employer Phone") or "").strip(),
                    "website": (row.get("Employer Website") or "").strip(),
                    "location": (row.get("Location") or "").strip(),
                    "is_approved": True,
                    "login_active": True,
                    "approved_at": timezone.now(),
                }

                if employer:
                    updated_employers += 1
                    if not dry_run:
                        for field, value in data.items():
                            setattr(employer, field, value)
                        employer.save()
                else:
                    created_employers += 1
                    if not dry_run:
                        Employer.objects.create(**data)

        self.stdout.write(
            self.style.SUCCESS(
                f"Users created: {created_users}\n"
                f"Employers created: {created_employers}\n"
                f"Employers updated: {updated_employers}\n"
                f"Rows skipped (missing email): {skipped}"
            )
        )
