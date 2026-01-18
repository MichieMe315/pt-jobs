from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from board.models import Employer


def _norm(s: str) -> str:
    return (s or "").strip()


def _trim_to_model(field_name: str, value: str) -> str:
    """
    If Employer.<field_name> is a CharField with max_length, trim to max_length.
    """
    try:
        f = Employer._meta.get_field(field_name)
        max_len = getattr(f, "max_length", None)
        if max_len and isinstance(value, str) and len(value) > max_len:
            return value[: max_len].strip()
    except Exception:
        pass
    return value


def _first(row: dict, keys: list[str]) -> str:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return _norm(row[k])
    return ""


class Command(BaseCommand):
    help = "Import employers from a CSV into Employer table (idempotent by email)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            self.stdout.write(self.style.ERROR(f"[employers] File not found: {csv_path}"))
            return

        # Determine status from filename (your existing convention)
        name = csv_path.name.lower()
        if "deactivated" in name or "inactive" in name:
            is_approved = False
            login_active = False
            status = "inactive"
        elif "pending" in name:
            is_approved = False
            login_active = False
            status = "pending"
        else:
            is_approved = True
            login_active = True
            status = "active"

        self.stdout.write(f"--- Importing: {csv_path.name} | status={status} (is_approved={is_approved}, login_active={login_active}) ---")

        created = updated = skipped = errors = 0

        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, start=1):
                try:
                    # Email is the stable unique key
                    email = _first(row, ["email", "Email", "company_email", "contact_email", "login_email"])
                    if not email:
                        skipped += 1
                        continue

                    company_name = _first(row, ["company_name", "Company Name", "clinic_name", "employer_name", "name"]) or email.split("@")[0]
                    phone = _first(row, ["phone", "Phone", "telephone"])
                    website = _first(row, ["website", "Website", "url"])
                    location = _first(row, ["location", "Location", "city", "province"])

                    company_description = _first(row, ["company_description", "Company Description", "description", "about"])

                    data = {
                        "email": _trim_to_model("email", email.lower()),
                        "company_name": _trim_to_model("company_name", company_name),
                        "phone": _trim_to_model("phone", phone),
                        "website": _trim_to_model("website", website),
                        "location": _trim_to_model("location", location),
                        "company_description": company_description,  # TextField typically, no max_length
                        "is_approved": is_approved,
                        "login_active": login_active,
                    }

                    # Remove keys that don't exist in your Employer model (contract-safe)
                    safe_data = {}
                    for k, v in data.items():
                        try:
                            Employer._meta.get_field(k)
                            safe_data[k] = v
                        except Exception:
                            continue

                    obj = Employer.objects.filter(email__iexact=safe_data["email"]).first()
                    if obj:
                        for k, v in safe_data.items():
                            setattr(obj, k, v)
                        obj.save()
                        updated += 1
                    else:
                        Employer.objects.create(**safe_data)
                        created += 1

                except Exception as e:
                    errors += 1
                    self.stdout.write(self.style.ERROR(f"[employers][Row {idx}] ERROR: {e}"))

        self.stdout.write(f"[employers] created={created} updated={updated} skipped={skipped} errors={errors}")
