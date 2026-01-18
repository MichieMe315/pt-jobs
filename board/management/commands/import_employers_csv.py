# board/management/commands/import_employers_csv.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from board.models import Employer


User = get_user_model()


def _norm(s: Any) -> str:
    return ("" if s is None else str(s)).strip()


def _lower_keys(row: dict[str, Any]) -> dict[str, Any]:
    return {str(k).strip().lower(): v for k, v in row.items()}


def _truncate_to_field(model, field_name: str, value: Any) -> Any:
    """
    If the model field is a CharField with max_length, truncate safely.
    """
    if value is None:
        return None
    val = str(value)
    try:
        field = model._meta.get_field(field_name)
        max_len = getattr(field, "max_length", None)
        if max_len and isinstance(max_len, int) and len(val) > max_len:
            return val[:max_len]
    except Exception:
        pass
    return value


def _pick(row: dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = row.get(k)
        if v not in (None, ""):
            return _norm(v)
    return ""


class Command(BaseCommand):
    help = "Import employers from CSV (active/inactive/pending). Creates/updates Users + Employer rows."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument(
            "--status",
            choices=["active", "inactive", "pending"],
            default="active",
            help="Controls is_approved/login_active.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Validate only; no DB writes.")

    def handle(self, *args, **opts):
        csv_path = Path(opts["csv_path"])
        status = opts["status"]
        dry_run = bool(opts["dry_run"])

        is_approved = status == "active"
        login_active = status == "active"

        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"File not found: {csv_path}"))
            return

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        self.stdout.write(
            f"--- Importing: {csv_path.name} | status={status} (is_approved={is_approved}, login_active={login_active}) ---"
        )

        # Wrap whole run so --dry-run can rollback cleanly.
        atomic_ctx = transaction.atomic()
        atomic_ctx.__enter__()
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for i, raw in enumerate(reader, start=2):
                    row = _lower_keys(raw or {})

                    # REQUIRED: email
                    email = _pick(row, "email", "email address", "email_address", "employer_email", "contact email")
                    if not email:
                        skipped += 1
                        continue

                    # Normalized user identity
                    email_lc = email.lower()

                    # Core employer fields (best-effort mapping)
                    company_name = _pick(row, "company_name", "company name", "company", "clinic", "name")
                    phone = _pick(row, "phone", "phone number", "phone_number", "tel", "telephone")
                    website = _pick(row, "website", "url", "site", "web")
                    location = _pick(row, "location", "city", "province", "address")
                    company_description = _pick(
                        row,
                        "company_description",
                        "company description",
                        "description",
                        "about",
                        "about_company",
                    )

                    # Create/get the auth user (NEVER skip employer creation just because user exists)
                    user, user_created = User.objects.get_or_create(
                        email=email_lc,
                        defaults={
                            "username": email_lc,
                            "is_active": True,
                        },
                    )
                    # Keep username aligned (Django may require it)
                    if getattr(user, "username", None) != email_lc:
                        try:
                            user.username = email_lc
                        except Exception:
                            pass

                    # IMPORTANT: do NOT accidentally lock staff/superuser accounts
                    if not (user.is_staff or user.is_superuser):
                        user.is_active = True  # keep auth account active; you gate login via Employer.login_active
                    user.email = email_lc
                    user.save()

                    # Create or update Employer linked to this user
                    emp, emp_created = Employer.objects.get_or_create(
                        user=user,
                        defaults={
                            "email": email_lc,
                        },
                    )

                    # Apply status flags
                    emp.is_approved = bool(is_approved)
                    emp.login_active = bool(login_active)

                    # Fill fields if present
                    if company_name:
                        # some projects have both company_name and name; set both if they exist
                        if hasattr(emp, "company_name"):
                            emp.company_name = _truncate_to_field(Employer, "company_name", company_name)
                        if hasattr(emp, "name"):
                            emp.name = _truncate_to_field(Employer, "name", company_name)

                    if phone and hasattr(emp, "phone"):
                        emp.phone = _truncate_to_field(Employer, "phone", phone)

                    if website and hasattr(emp, "website"):
                        emp.website = _truncate_to_field(Employer, "website", website)

                    if location and hasattr(emp, "location"):
                        emp.location = _truncate_to_field(Employer, "location", location)

                    # Prefer company_description field if it exists, else fallback to description
                    if company_description:
                        if hasattr(emp, "company_description"):
                            # company_description often TextField; still safe to assign
                            emp.company_description = company_description
                        elif hasattr(emp, "description"):
                            emp.description = _truncate_to_field(Employer, "description", company_description)

                    # Ensure email stored on Employer if model has it
                    if hasattr(emp, "email"):
                        emp.email = _truncate_to_field(Employer, "email", email_lc)

                    emp.save()

                    if emp_created:
                        created += 1
                    else:
                        updated += 1

            if dry_run:
                raise transaction.TransactionManagementError("Dry-run complete (rolled back).")

        except transaction.TransactionManagementError:
            # expected for dry-run
            pass
        except Exception as e:
            errors += 1
            self.stderr.write(self.style.ERROR(f"FATAL import error: {e}"))
        finally:
            # rollback if dry-run, otherwise commit
            if dry_run:
                transaction.set_rollback(True)
            atomic_ctx.__exit__(None, None, None)

        if dry_run:
            self.stdout.write(self.style.WARNING("[employers] DRY-RUN: no DB writes performed."))

        self.stdout.write(f"[employers] created={created} updated={updated} skipped={skipped} errors={errors}")
