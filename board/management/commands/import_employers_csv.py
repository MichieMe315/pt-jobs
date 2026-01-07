import csv
from datetime import datetime
from typing import Any, Optional

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.dateparse import parse_datetime

from board.models import Employer


def _clean_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _clean_bool(v: Any) -> bool:
    s = _clean_str(v).lower()
    return s in {"1", "true", "yes", "y", "t"}


def _clean_int(v: Any, default: int = 0) -> int:
    s = _clean_str(v)
    if not s:
        return default
    try:
        return int(float(s))
    except Exception:
        return default


def _clean_dt(v: Any) -> Optional[datetime]:
    s = _clean_str(v)
    if not s:
        return None
    # Try Django parser first
    dt = parse_datetime(s)
    if dt:
        return dt
    # Fallback common formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def _truncate_for_field(model_cls, field_name: str, value: str) -> str:
    """
    If the model field has max_length (CharField/URLField/etc), clamp to that.
    Prevents Postgres: value too long for type character varying(N)
    """
    try:
        field = model_cls._meta.get_field(field_name)
    except Exception:
        return value

    max_len = getattr(field, "max_length", None)
    if max_len and isinstance(value, str) and len(value) > max_len:
        return value[:max_len]
    return value


class Command(BaseCommand):
    help = "Import Employers from a CSV and create/link Django Users by email."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to employers.csv")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate, but do not write to DB.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        dry_run = options["dry_run"]

        User = get_user_model()

        users_created = 0
        employers_created = 0
        employers_updated = 0
        rows_skipped = 0
        rows_error = 0

        # We require at minimum an email column.
        required_col = "email"

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV has no headers/fieldnames.")

            headers = [h.strip() for h in reader.fieldnames if h]
            if required_col not in [h.lower() for h in headers]:
                # try exact match first; if not, fail loudly (no silent mapping)
                raise ValueError(f"CSV must include an 'email' column. Found headers: {headers}")

            # Normalize keys to lower for safe access without aliasing names
            def row_get(row, key: str) -> str:
                # exact lower-key match only
                for k, v in row.items():
                    if k and k.strip().lower() == key:
                        return _clean_str(v)
                return ""

            for idx, row in enumerate(reader, start=2):  # line numbers roughly (header=1)
                email = row_get(row, "email").lower()
                if not email:
                    rows_skipped += 1
                    continue

                # Pull values (no guessing/renaming)
                name = row_get(row, "name")
                company_name = row_get(row, "company_name")
                company_description = row_get(row, "company_description")
                description = row_get(row, "description")
                phone = row_get(row, "phone")
                website = row_get(row, "website")
                location = row_get(row, "location")
                logo = row_get(row, "logo")  # NOTE: CSV string cannot populate ImageField file automatically
                is_approved = _clean_bool(row_get(row, "is_approved"))
                login_active = _clean_bool(row_get(row, "login_active"))
                credits = _clean_int(row_get(row, "credits"), default=0)
                approved_at = _clean_dt(row_get(row, "approved_at"))
                created_at = _clean_dt(row_get(row, "created_at"))
                updated_at = _clean_dt(row_get(row, "updated_at"))

                # Clamp lengths to prevent varchar(N) crashes
                name = _truncate_for_field(Employer, "name", name)
                company_name = _truncate_for_field(Employer, "company_name", company_name)
                phone = _truncate_for_field(Employer, "phone", phone)
                website = _truncate_for_field(Employer, "website", website)
                location = _truncate_for_field(Employer, "location", location)
                email_clamped = _truncate_for_field(Employer, "email", email)

                # Also clamp user email/username if your User model uses a max length (safe)
                user_email = email_clamped

                if dry_run:
                    continue

                try:
                    with transaction.atomic():
                        # Get/create user by email
                        user = User.objects.filter(email__iexact=user_email).first()
                        if not user:
                            # username strategy: use email (common)
                            kwargs = {}
                            # If custom user model has username field, set it.
                            if hasattr(User, "USERNAME_FIELD") and User.USERNAME_FIELD != "email":
                                # most default users use "username"
                                if hasattr(user := User(), "username"):
                                    kwargs["username"] = user_email
                            kwargs["email"] = user_email

                            user = User.objects.create(**kwargs)
                            user.set_unusable_password()  # force password reset to set first password
                            user.save(update_fields=["password"])
                            users_created += 1

                        # Get/create employer linked to this user
                        employer = Employer.objects.filter(email__iexact=user_email).first()
                        created = False
                        if not employer:
                            employer = Employer(email=user_email)
                            created = True

                        # Link the user FK if present on model
                        if hasattr(employer, "user_id"):
                            employer.user = user

                        # Set fields (only those present in your admin importer list)
                        if hasattr(employer, "name"):
                            employer.name = name
                        if hasattr(employer, "company_name"):
                            employer.company_name = company_name
                        if hasattr(employer, "company_description"):
                            employer.company_description = company_description
                        if hasattr(employer, "description"):
                            employer.description = description
                        if hasattr(employer, "phone"):
                            employer.phone = phone
                        if hasattr(employer, "website"):
                            employer.website = website
                        if hasattr(employer, "location"):
                            employer.location = location

                        # Logo handling:
                        # If Employer.logo is an ImageField, a CSV string (often a URL) cannot be saved as a file here.
                        # We intentionally do NOT assign it to avoid invalid file path crashes.
                        # We'll do a separate "download+attach logos" step later if needed.

                        if hasattr(employer, "is_approved"):
                            employer.is_approved = is_approved
                        if hasattr(employer, "login_active"):
                            employer.login_active = login_active
                        if hasattr(employer, "credits"):
                            employer.credits = credits
                        if hasattr(employer, "approved_at"):
                            employer.approved_at = approved_at

                        # Preserve timestamps if your model allows it (some use auto_now/add)
                        # Only set if fields exist and are editable; otherwise Django will ignore or error.
                        if created_at and hasattr(employer, "created_at"):
                            try:
                                employer.created_at = created_at
                            except Exception:
                                pass
                        if updated_at and hasattr(employer, "updated_at"):
                            try:
                                employer.updated_at = updated_at
                            except Exception:
                                pass

                        employer.save()

                        if created:
                            employers_created += 1
                        else:
                            employers_updated += 1

                except Exception as e:
                    rows_error += 1
                    # Log which row failed without dumping entire sensitive row
                    self.stderr.write(
                        f"Row {idx} ERROR for email={email}: {e}"
                    )

        self.stdout.write(f"Users created: {users_created}")
        self.stdout.write(f"Employers created: {employers_created}")
        self.stdout.write(f"Employers updated: {employers_updated}")
        self.stdout.write(f"Rows skipped (missing email): {rows_skipped}")
        self.stdout.write(f"Rows errors: {rows_error}")
