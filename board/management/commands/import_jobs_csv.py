# board/management/commands/import_jobs_csv.py
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from board.models import Employer, Job


def _clean(s: Any) -> str:
    if s is None:
        return ""
    val = str(s).strip()
    return "" if val.lower() in {"nan", "none", "null"} else val


def _lower(s: Any) -> str:
    return _clean(s).lower()


def _parse_int(s: Any) -> Optional[int]:
    s = _clean(s)
    if not s:
        return None
    try:
        return int(float(s))
    except Exception:
        return None


def _parse_decimal(s: Any) -> Optional[Decimal]:
    s = _clean(s)
    if not s:
        return None
    # remove currency symbols/commas
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _parse_bool_yes_no(s: Any) -> bool:
    s = _lower(s)
    return s in {"1", "true", "yes", "y", "on"}


def _parse_date(s: Any):
    """
    Accepts:
      - YYYY-MM-DD
      - YYYY-MM-DD HH:MM:SS
      - common human date strings
    Returns date or None.
    """
    s = _clean(s)
    if not s:
        return None

    # Fast path for ISO date
    m = re.match(r"^\d{4}-\d{2}-\d{2}$", s)
    if m:
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    # ISO datetime
    m = re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$", s)
    if m:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").date()
        except Exception:
            return None

    # Try a couple common formats (best effort)
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue

    return None


JOB_TYPE_MAP = {
    "full time": "full_time",
    "full-time": "full_time",
    "full_time": "full_time",
    "part time": "part_time",
    "part-time": "part_time",
    "part_time": "part_time",
    "contract": "contractor",
    "contractor": "contractor",
    "casual": "casual",
    "locum": "locum",
    "temporary": "temporary",
}

COMP_TYPE_MAP = {
    "hour": "hourly",
    "hourly": "hourly",
    "hr": "hourly",
    "year": "yearly",
    "yearly": "yearly",
    "annual": "yearly",
    "percent": "split",
    "percentage": "split",
    "split": "split",
}


@dataclass
class ImportStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


class Command(BaseCommand):
    help = "Import Jobs from legacy export CSVs (jobs_active/jobs_expired)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument(
            "--mode",
            choices=["active", "expired", "infer"],
            default="infer",
            help="Force is_active based on file type. Use active for jobs_active.csv and expired for jobs_expired.csv.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Parse + validate, but do not write to DB.")
        parser.add_argument(
            "--allow-update",
            action="store_true",
            default=True,
            help="Update existing Job rows if IDs match.",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        mode = options["mode"]
        dry_run = options["dry_run"]
        allow_update = options["allow_update"]

        p = Path(csv_path)
        if not p.is_absolute():
            p = Path(settings.BASE_DIR) / p

        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")

        with p.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            required = {"Job Id", "Employer Email", "Job Title", "Job Description"}
            missing = [h for h in required if h not in set(headers)]
            if missing:
                raise ValueError(f"CSV missing required columns: {missing}. Found headers: {headers}")

            stats = ImportStats()

            # Wrap whole import in one transaction unless dry-run
            ctx = transaction.atomic() if not dry_run else _NoopCtx()

            with ctx:
                for idx, row in enumerate(reader, start=2):
                    try:
                        self._import_row(row=row, mode=mode, allow_update=allow_update, dry_run=dry_run, stats=stats)
                    except Exception as e:
                        stats.errors += 1
                        stats.skipped += 1
                        self.stdout.write(self.style.ERROR(f"[jobs] Row {idx} ERROR: {e}"))

                if dry_run:
                    self.stdout.write(self.style.WARNING("[jobs] DRY-RUN: no DB writes performed."))

            self.stdout.write(
                self.style.SUCCESS(
                    f"[jobs] created={stats.created} updated={stats.updated} skipped={stats.skipped} errors={stats.errors}"
                )
            )

    def _import_row(self, row: dict, mode: str, allow_update: bool, dry_run: bool, stats: ImportStats) -> None:
        job_id = _parse_int(row.get("Job Id"))
        if not job_id:
            stats.skipped += 1
            return

        employer_email = _clean(row.get("Employer Email"))
        if not employer_email:
            stats.skipped += 1
            return

        employer = Employer.objects.filter(email__iexact=employer_email).first()
        if not employer:
            # If employer isn't found, skip. (We don't create Employers here.)
            stats.skipped += 1
            return

        title = _clean(row.get("Job Title"))
        desc = _clean(row.get("Job Description"))

        # Enforce model max_length constraints safely by SKIPPING (no truncation).
        if len(title) > 200:
            raise ValueError(f"Job Title too long (len={len(title)} > 200) for Job Id={job_id}")

        # Location: prefer Location, else build from City/State/Country
        loc = _clean(row.get("Location"))
        if not loc:
            parts = [p for p in [_clean(row.get("City")), _clean(row.get("State")), _clean(row.get("Country"))] if p]
            loc = ", ".join(parts)
        if len(loc) > 200:
            raise ValueError(f"Location too long (len={len(loc)} > 200) for Job Id={job_id}")

        job_type_raw = _lower(row.get("Job Type"))
        job_type = JOB_TYPE_MAP.get(job_type_raw, "")

        comp_period_raw = _lower(row.get("Salary Period"))
        comp_type = ""
        # Try matching by substring keys
        for key, val in COMP_TYPE_MAP.items():
            if key and key in comp_period_raw:
                comp_type = val
                break

        comp_min = _parse_decimal(row.get("Salary From"))
        comp_max = _parse_decimal(row.get("Salary To"))

        apply_email = _clean(row.get("Apply Email"))
        apply_url = _clean(row.get("Apply URL"))

        apply_via = ""
        if apply_email:
            apply_via = "email"
        elif apply_url:
            apply_via = "url"

        posting_date = _parse_date(row.get("Posting Date")) or timezone.now().date()
        expiry_date = _parse_date(row.get("Expiration Date"))

        status_raw = _lower(row.get("Status"))
        if mode == "active":
            is_active = True
        elif mode == "expired":
            is_active = False
        else:
            # infer from status text
            if "not active" in status_raw or "inactive" in status_raw or "expired" in status_raw:
                is_active = False
            elif "active" in status_raw:
                is_active = True
            else:
                is_active = True

        relocation = _parse_bool_yes_no(row.get("Relocation assistance provided?"))
        views_count = _parse_int(row.get("Views")) or 0

        existing = Job.objects.filter(id=job_id).first()

        if existing and not allow_update:
            stats.skipped += 1
            return

        if dry_run:
            # Just simulate success
            if existing:
                stats.updated += 1
            else:
                stats.created += 1
            return

        if existing:
            job = existing
        else:
            job = Job(id=job_id)

        job.employer = employer
        job.title = title
        job.description = desc

        job.job_type = job_type
        job.compensation_type = comp_type
        job.compensation_min = comp_min
        job.compensation_max = comp_max

        job.location = loc

        job.apply_via = apply_via
        job.apply_email = apply_email if apply_via == "email" else ""
        job.apply_url = apply_url if apply_via == "url" else ""

        # Keep legacy apply fields aligned too
        job.application_email = job.apply_email
        job.external_apply_url = job.apply_url

        job.relocation_assistance = relocation
        job.relocation_assistance_provided = relocation

        job.posting_date = posting_date
        job.expiry_date = expiry_date

        job.is_active = is_active
        job.views_count = int(views_count or 0)

        job.source = "import"

        job.save()

        if existing:
            stats.updated += 1
        else:
            stats.created += 1


class _NoopCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
