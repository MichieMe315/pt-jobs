from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from board.models import Employer, Job


def _norm(s: str) -> str:
    return (s or "").strip()


def _parse_date(val: str) -> date | None:
    val = _norm(val)
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except Exception:
            pass
    return None


def _trim_to_model(field_name: str, value: str) -> str:
    try:
        f = Job._meta.get_field(field_name)
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
    help = "Import jobs from active + expired CSVs (idempotent best-effort)."

    def add_arguments(self, parser):
        parser.add_argument("active_csv", type=str)
        parser.add_argument("expired_csv", type=str)

    def _import_one(self, csv_path: Path, is_active: bool) -> tuple[int, int, int, int]:
        created = skipped = missing_employer = errors = 0

        label = "active" if is_active else "expired"
        self.stdout.write(f"--- Importing {csv_path.name} | mode={label} (is_active={is_active}) ---")

        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, start=1):
                try:
                    title = _first(row, ["title", "Title", "job_title", "Job Title"])
                    if not title:
                        skipped += 1
                        continue

                    employer_email = _first(row, ["employer_email", "Employer Email", "company_email", "email", "Email"])
                    employer_name = _first(row, ["company_name", "Company Name", "employer_name", "Employer", "clinic_name"])

                    employer = None
                    if employer_email:
                        employer = Employer.objects.filter(email__iexact=employer_email).first()
                    if not employer and employer_name:
                        employer = Employer.objects.filter(company_name__iexact=employer_name).first()

                    if not employer:
                        missing_employer += 1
                        continue

                    description = _first(row, ["description", "Description", "job_description", "Job Description"])

                    location = _first(row, ["location", "Location", "city", "City"])
                    job_type = _first(row, ["job_type", "Job Type", "type"])
                    compensation_type = _first(row, ["compensation_type", "Compensation Type"])
                    comp_min = _first(row, ["compensation_min", "Compensation Min", "min_compensation", "min"])
                    comp_max = _first(row, ["compensation_max", "Compensation Max", "max_compensation", "max"])

                    posting_date = _parse_date(_first(row, ["posting_date", "Posting Date", "date_posted"])) or timezone.now().date()
                    expiration_date = _parse_date(_first(row, ["expiration_date", "Expiry Date", "expires_at", "expiry"]))

                    data = {
                        "employer": employer,
                        "title": _trim_to_model("title", title),
                        "description": description,  # TextField usually
                        "location": _trim_to_model("location", location),
                        "job_type": _trim_to_model("job_type", job_type),
                        "compensation_type": _trim_to_model("compensation_type", compensation_type),
                        "posting_date": posting_date,
                        "expiration_date": expiration_date,
                        "is_active": is_active,
                    }

                    # Only set min/max if those fields exist in your Job model
                    if hasattr(Job, "compensation_min"):
                        try:
                            data["compensation_min"] = comp_min if comp_min != "" else None
                        except Exception:
                            pass
                    if hasattr(Job, "compensation_max"):
                        try:
                            data["compensation_max"] = comp_max if comp_max != "" else None
                        except Exception:
                            pass

                    # Create-only import (safe). If you want “update if same employer+title”, we can add it later.
                    Job.objects.create(**data)
                    created += 1

                except Exception as e:
                    errors += 1
                    self.stdout.write(self.style.ERROR(f"[jobs][Row {idx}] ERROR: {e}"))

        return created, skipped, missing_employer, errors

    def handle(self, *args, **options):
        active_csv = Path(options["active_csv"])
        expired_csv = Path(options["expired_csv"])

        if not active_csv.exists():
            self.stdout.write(self.style.ERROR(f"[jobs] File not found: {active_csv}"))
            return
        if not expired_csv.exists():
            self.stdout.write(self.style.ERROR(f"[jobs] File not found: {expired_csv}"))
            return

        c1, s1, m1, e1 = self._import_one(active_csv, is_active=True)
        c2, s2, m2, e2 = self._import_one(expired_csv, is_active=False)

        self.stdout.write("DONE")
        self.stdout.write(f"Jobs created: {c1 + c2}")
        self.stdout.write(f"Skipped rows: {s1 + s2}")
        self.stdout.write(f"Missing employer: {m1 + m2}")
        self.stdout.write(f"Errors: {e1 + e2}")
