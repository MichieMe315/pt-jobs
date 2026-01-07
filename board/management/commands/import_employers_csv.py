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
    return s in {"1", "true", "yes", "y", "t", "approved", "active"}


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
    dt = parse_datetime(s)
    if dt:
        return dt
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    return None


def _truncate_for_field(model_cls, field_name: str, value: str) -> str:
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

        # Explicit, allowed header mappings for YOUR export format.
        # Left = internal key we use in code. Right = accepted CSV header names.
        HEADER_MAP = {
            "email": ["email", "Employer Email"],
            "name": ["name", "Full Name"],
            "company_name": ["company_name", "Company Name"],
            "company_description": ["company_description", "Company Description"],
            "phone": ["phone", "Employer Phone"],
            "website": ["website", "Employer Website"],
            "location": ["location", "Location"],
            "logo": ["logo", "Employer Logo"],
            "created_at": ["created_at", "Registration Date"],
            "is_approved": ["is_approved", "Status"],
        }

        def get_by_headers(row: dict, keys: list[str]) -> str:
            # Match exactly (case-insensitive) against allowed headers.
            for k in row.keys():
                if not k:
                    continue
                for wanted in keys:
                    if k.strip().lower() == wanted.strip().lower():
                        return _clean_str(row.get(k))
            return ""

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError("CSV has no headers/fieldnames.")

            headers = [h.strip() for h in reader.fieldnames if h]

            # Require an email via the explicit allowed headers
            test_email = None
            for h in headers:
                if h.strip().lower() in {x.lower() for x in HEADER_MAP["email"]}:
                    test_email = h
                    break
            if not test_email:
                raise ValueError(
                    f"CSV must include an email column. Accepted: {HEADER_MAP['email']}. Found headers: {headers}"
                )

            for idx, row in enumerate(reader, start=2):
                email = get_by_headers(row, HEADER_MAP["email"]).lower()
                if not email:
                    rows_skipped += 1
                    continue

                name = get_by_headers(row, HEADER_MAP["name"])
                company_name = get_by_headers(row, HEADER_MAP["company_name"])
                company_description = get_by_headers(row, HEADER_MAP["company_description"])
                phone = get_by_headers(row, HEADER_MAP["phone"])
                website = get_by_headers(row, HEADER_MAP["website"])
                location = get_by_headers(row, HEADER_MAP["location"])
                logo = get_by_headers(row, HEADER_MAP["logo"])
                created_at = _clean_dt(get_by_headers(row, HEADER_MAP["created_at"]))

                # Status from export may be text; treat common values as approved
                status_raw = get_by_headers(row, HEADER_MAP["is_approved"])
                is_approved = _clean_bool(status_raw)

                # Clamp to model field max lengths to avoid Postgres varchar errors
                email = _truncate_for_field(Employer, "email", email)
                name = _truncate_for_field(Employer, "name", name)
                company_name = _truncate_for_field(Employer, "company_name", company_name)
                phone = _truncate_for_field(Employer, "phone", phone)
                website = _truncate_for_field(Employer, "website", website)
                location = _truncate_for_field(Employer, "location", location)

                if dry_run:
                    continue

                try:
                    with transaction.atomic():
                        # Create/get user by email
                        user = User.objects.filter(email__iexact=email).first()
                        if not user:
                            create_kwargs = {"email": email}

                            # If default User has username, set username=email
                            if hasattr(User(), "username"):
                                create_kwargs["username"] = email

                            user = User.objects.create(**create_kwargs)
                            user.set_unusable_password()
                            user.save(update_fields=["password"])
                            users_created += 1

                        employer = Employer.objects.filter(email__iexact=email).first()
                        created = False
                        if not employer:
                            employer = Employer(email=email)
                            created = True

                        if hasattr(employer, "user_id"):
                            employer.user = user

                        if hasattr(employer, "name"):
                            employer.name = name
                        if hasattr(employer, "company_name"):
                            employer.company_name = company_name
                        if hasattr(employer, "company_description"):
                            employer.company_description = company_description
                        if hasattr(employer, "phone"):
                            employer.phone = phone
                        if hasattr(employer, "website"):
                            employer.website = website
                        if hasattr(employer, "location"):
                            employer.location = location

                        # Do NOT assign logo string into ImageField here.
                        # CSV contains a URL; ImageField needs an uploaded file.
                        # We'll handle logos in a separate step later.

                        if hasattr(employer, "is_approved"):
                            employer.is_approved = is_approved

                        # created_at may be auto_add; only set if allowed
                        if created_at and hasattr(employer, "created_at"):
                            try:
                                employer.created_at = created_at
                            except Exception:
                                pass

                        employer.save()

                        if created:
                            employers_created += 1
                        else:
                            employers_updated += 1

                except Exception as e:
                    rows_error += 1
                    self.stderr.write(f"Row {idx} ERROR for email={email}: {e}")

        self.stdout.write(f"Users created: {users_created}")
        self.stdout.write(f"Employers created: {employers_created}")
        self.stdout.write(f"Employers updated: {employers_updated}")
        self.stdout.write(f"Rows skipped (missing email): {rows_skipped}")
        self.stdout.write(f"Rows errors: {rows_error}")
