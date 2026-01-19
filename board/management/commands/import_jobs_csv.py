import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from board.models import Employer, Job


EMAIL_KEYS = ["Employer Email", "EmployerEmail", "email", "Email", "employer_email"]
TITLE_KEYS = ["Title", "Job Title", "job_title"]
DESC_KEYS = ["Description", "Job Description", "description"]
CITY_KEYS = ["City", "city"]
PROV_KEYS = ["Province", "State", "province", "state"]
LOCATION_KEYS = ["Location", "location"]
JOB_TYPE_KEYS = ["Job Type", "job_type", "Type"]
COMP_TYPE_KEYS = ["Compensation Type", "compensation_type"]
COMP_MIN_KEYS = ["Compensation Min", "compensation_min", "Min Pay", "min_pay"]
COMP_MAX_KEYS = ["Compensation Max", "compensation_max", "Max Pay", "max_pay"]
APPLY_VIA_KEYS = ["Apply Via", "apply_via"]
APPLY_EMAIL_KEYS = ["Apply Email", "apply_email"]
APPLY_URL_KEYS = ["Apply URL", "apply_url"]
POSTING_DATE_KEYS = ["Posting Date", "posting_date", "Date Posted"]
EXPIRY_DATE_KEYS = ["Expiry Date", "expiry_date", "Expiration Date"]
FEATURED_KEYS = ["Featured", "is_featured"]


def norm(val):
    return (val or "").strip()


def pick(row, keys):
    for k in keys:
        if k in row and norm(row.get(k)):
            return norm(row.get(k))
    return ""


def parse_date(val: str) -> Optional[datetime]:
    v = norm(val)
    if not v:
        return None

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(v, fmt)
        except Exception:
            pass

    return None


def parse_decimal(val: str):
    v = norm(val).replace("$", "").replace(",", "")
    if not v:
        return None
    try:
        return float(v)
    except Exception:
        return None


def mode_from_filename(filename: str) -> str:
    name = (filename or "").lower()
    if "expired" in name or "inactive" in name:
        return "expired"
    return "active"


def _truncate_for_model(model_cls, field_name: str, value: str) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    try:
        field = model_cls._meta.get_field(field_name)
        max_len = getattr(field, "max_length", None)
        if max_len and len(value) > max_len:
            return value[:max_len]
    except Exception:
        pass
    return value


class Command(BaseCommand):
    help = "Import Jobs from CSVs (active vs expired inferred from filename)."

    def add_arguments(self, parser):
        parser.add_argument("csv_paths", nargs="+", type=str)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        csv_paths = opts["csv_paths"]
        dry_run = bool(opts["dry_run"])

        created = 0
        skipped = 0
        missing_employer = 0
        errors = 0

        def abs_path(p: str) -> Path:
            pp = Path(p)
            return pp if pp.is_absolute() else Path(settings.BASE_DIR) / pp

        with transaction.atomic():
            for raw in csv_paths:
                path = abs_path(raw)
                if not path.exists():
                    raise FileNotFoundError(f"CSV not found: {path}")

                mode = mode_from_filename(path.name)
                is_active = mode == "active"

                self.stdout.write(f"\n--- Importing {path.name} | mode={mode} (is_active={is_active}) ---")

                with path.open(newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)

                    for idx, row in enumerate(reader, start=2):
                        try:
                            employer_email = pick(row, EMAIL_KEYS).lower()
                            title = pick(row, TITLE_KEYS)
                            description = pick(row, DESC_KEYS)

                            if not employer_email or not title:
                                skipped += 1
                                continue

                            employer = Employer.objects.filter(email__iexact=employer_email).first()
                            if not employer:
                                missing_employer += 1
                                continue

                            location = pick(row, LOCATION_KEYS)
                            if not location:
                                city = pick(row, CITY_KEYS)
                                prov = pick(row, PROV_KEYS)
                                location = ", ".join([p for p in [city, prov] if p])

                            job_type = pick(row, JOB_TYPE_KEYS)
                            comp_type = pick(row, COMP_TYPE_KEYS)
                            apply_via = pick(row, APPLY_VIA_KEYS)
                            apply_email = pick(row, APPLY_EMAIL_KEYS)
                            apply_url = pick(row, APPLY_URL_KEYS)

                            # ---- TRUNCATE to Job model max_length for CharFields ----
                            title = _truncate_for_model(Job, "title", title)
                            location = _truncate_for_model(Job, "location", location)
                            job_type = _truncate_for_model(Job, "job_type", job_type)
                            comp_type = _truncate_for_model(Job, "compensation_type", comp_type)
                            apply_via = _truncate_for_model(Job, "apply_via", apply_via)
                            apply_email = _truncate_for_model(Job, "apply_email", apply_email)
                            apply_url = _truncate_for_model(Job, "apply_url", apply_url)

                            job = Job(
                                employer=employer,
                                title=title,
                                description=description,  # TextField: no varchar limit
                                location=location,
                                job_type=job_type,
                                compensation_type=comp_type,
                                compensation_min=parse_decimal(pick(row, COMP_MIN_KEYS)),
                                compensation_max=parse_decimal(pick(row, COMP_MAX_KEYS)),
                                apply_via=apply_via,
                                apply_email=apply_email,
                                apply_url=apply_url,
                                is_active=is_active,
                                is_featured=pick(row, FEATURED_KEYS).lower() in ("1", "true", "yes"),
                            )

                            posting_dt = parse_date(pick(row, POSTING_DATE_KEYS))
                            expiry_dt = parse_date(pick(row, EXPIRY_DATE_KEYS))
                            if posting_dt:
                                job.posting_date = posting_dt.date()
                            if expiry_dt:
                                job.expiry_date = expiry_dt.date()

                            if not dry_run:
                                job.save()

                            created += 1

                        except Exception as e:
                            errors += 1
                            self.stderr.write(f"[Row {idx}] ERROR: {e}")

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            "\nDONE\n"
            + ("[jobs] DRY-RUN: no DB writes performed.\n" if dry_run else "")
            + f"Jobs created: {created}\n"
            + f"Skipped rows: {skipped}\n"
            + f"Missing employer: {missing_employer}\n"
            + f"Errors: {errors}\n"
        )
