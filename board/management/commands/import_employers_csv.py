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


def _status_from_filename(filename: str) -> str:
    """
    Infer employer status from CSV filename.
    - pending => inactive/unapproved (new site has no pending state for login)
    - deactivated/inactive => inactive/unapproved
    - default => active/approved
    """
    name = (filename or "").lower()
    if "pending" in name:
        return "inactive"
    if "deactivated" in name or "inactive" in name:
        return "inactive"
    return "active"


class Command(BaseCommand):
    help = "Import Employers from one or more CSVs (creates Users + Employers)."

    def add_arguments(self, parser):
        # Accept 1+ CSVs in a single run
        parser.add_argument("csv_paths", nargs="+", type=str)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        csv_paths = options["csv_paths"]

        created_users = 0
        updated_users = 0
        created_employers = 0
        updated_employers = 0
        skipped = 0

        def _abs_path(p: str) -> Path:
            pp = Path(p)
            if not pp.is_absolute():
                pp = Path(settings.BASE_DIR) / pp
            return pp

        with transaction.atomic():
            for raw_path in csv_paths:
                csv_path = _abs_path(raw_path)

                if not csv_path.exists():
                    raise FileNotFoundError(f"CSV not found: {csv_path}")

                status = _status_from_filename(csv_path.name)
                is_active_login = status == "active"
                is_approved = status == "active"

                self.stdout.write(
                    self.style.WARNING(
                        f"\n--- Importing: {csv_path.name} | status={status} "
                        f"(is_approved={is_approved}, login_active={is_active_login}) ---"
                    )
                )

                with csv_path.open(newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)

                    if not reader.fieldnames or "Employer Email" not in reader.fieldnames:
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
                                    is_active=is_active_login,  # blocks login for inactive/pending
                                )
                                created_users += 1
                        else:
                            # keep user consistent with employer activation
                            if not dry_run and user.is_active != is_active_login:
                                user.is_active = is_active_login
                                user.save(update_fields=["is_active"])
                                updated_users += 1

                        # ---- EMPLOYER ----
                        employer = Employer.objects.filter(email=email).first()

                        # CLEAN + SANITIZE DESCRIPTION
                        raw_desc = row.get("Company Description") or row.get("Description") or ""
                        company_description = strip_tags(raw_desc).strip()

                        data = {
                            # never touch logo here
                            "user": user,
                            "email": email,
                            "name": (row.get("Full Name") or "").strip(),
                            "company_name": (row.get("Company Name") or "").strip(),
                            "company_description": company_description,
                            "phone": (row.get("Employer Phone") or "").strip(),
                            "website": (row.get("Employer Website") or "").strip(),
                            "location": (row.get("Location") or "").strip(),
                            "is_approved": is_approved,
                            "login_active": is_active_login,
                        }

                        # approved_at only when approved
                        if is_approved:
                            data["approved_at"] = timezone.now()
                        else:
                            data["approved_at"] = None

                        if employer:
                            updated_employers += 1
                            if not dry_run:
                                # Do not overwrite logo even if field exists in data (it doesn't)
                                for field, value in data.items():
                                    setattr(employer, field, value)
                                employer.save()
                        else:
                            created_employers += 1
                            if not dry_run:
                                Employer.objects.create(**data)

        self.stdout.write(
            self.style.SUCCESS(
                "\nDONE\n"
                f"Users created: {created_users}\n"
                f"Users updated: {updated_users}\n"
                f"Employers created: {created_employers}\n"
                f"Employers updated: {updated_employers}\n"
                f"Rows skipped (missing email): {skipped}\n"
            )
        )
