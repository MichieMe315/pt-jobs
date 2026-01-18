import csv
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from board.models import Employer, Job


def _clean_str(v):
    if v is None:
        return ""
    s = str(v).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _max_len_for(model_cls, field_name: str):
    try:
        f = model_cls._meta.get_field(field_name)
        return getattr(f, "max_length", None)
    except Exception:
        return None


def _truncate_to_field(model_cls, field_name: str, value):
    if value is None:
        return None
    s = str(value)
    max_len = _max_len_for(model_cls, field_name)
    if max_len and len(s) > int(max_len):
        return s[: int(max_len)]
    return s


class Command(BaseCommand):
    help = "Import Jobs from one CSV file. Use --mode active|expired to set is_active."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument("--mode", type=str, default="active", choices=["active", "expired"])
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **opts):
        csv_path = Path(opts["csv_path"])
        mode = (opts["mode"] or "active").strip().lower()
        dry_run = bool(opts["dry_run"])

        is_active = True if mode == "active" else False

        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        created = 0
        updated = 0
        skipped = 0
        errors = 0
        truncated_fields = 0

        def _set(data: dict, field_name: str, raw_value, allow_blank=True):
            nonlocal truncated_fields
            s = _clean_str(raw_value)
            if not s and allow_blank:
                data[field_name] = ""
                return
            before = s
            s2 = _truncate_to_field(Job, field_name, s)
            if s2 is not None and before != s2:
                truncated_fields += 1
            data[field_name] = s2

        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader, start=1):
                try:
                    # Employer lookup
                    employer_email = _clean_str(row.get("employer_email") or row.get("Employer Email") or row.get("email") or "")
                    employer = None
                    if employer_email:
                        employer = Employer.objects.filter(email__iexact=employer_email).first()

                    if employer is None:
                        # fallback: employer_id if present
                        employer_id = _clean_str(row.get("employer_id") or row.get("Employer ID") or "")
                        if employer_id.isdigit():
                            employer = Employer.objects.filter(id=int(employer_id)).first()

                    if employer is None:
                        skipped += 1
                        continue

                    data = {}
                    _set(data, "title", row.get("title") or row.get("Title") or "", allow_blank=False)
                    _set(data, "location", row.get("location") or row.get("Location") or "", allow_blank=True)

                    # Description is typically TextField; keep as-is (your cleanup script can sanitize HTML later)
                    desc = row.get("description") or row.get("Description") or ""
                    data["description"] = desc if desc is not None else ""

                    # Optional fields (only if they exist on your model)
                    for fld, keys in [
                        ("job_type", ["job_type", "Job Type"]),
                        ("compensation_type", ["compensation_type", "Compensation Type"]),
                        ("apply_via", ["apply_via", "Apply Via"]),
                        ("apply_email", ["apply_email", "Apply Email"]),
                        ("apply_url", ["apply_url", "Apply URL"]),
                    ]:
                        if hasattr(Job, fld):
                            v = ""
                            for k in keys:
                                if row.get(k):
                                    v = row.get(k)
                                    break
                            _set(data, fld, v, allow_blank=True)

                    # Min/max comp numeric
                    if hasattr(Job, "compensation_min"):
                        raw = _clean_str(row.get("compensation_min") or row.get("Min Compensation") or "")
                        if raw:
                            try:
                                data["compensation_min"] = float(raw)
                            except Exception:
                                pass

                    if hasattr(Job, "compensation_max"):
                        raw = _clean_str(row.get("compensation_max") or row.get("Max Compensation") or "")
                        if raw:
                            try:
                                data["compensation_max"] = float(raw)
                            except Exception:
                                pass

                    # Posting/expiry (only set if present; otherwise keep defaults)
                    # IMPORTANT: do NOT overwrite posting_date/expiry_date with "today" unless your CSV is missing them.
                    if hasattr(Job, "posting_date"):
                        raw = _clean_str(row.get("posting_date") or row.get("Posting Date") or "")
                        if raw:
                            try:
                                data["posting_date"] = timezone.datetime.fromisoformat(raw).date()
                            except Exception:
                                pass

                    if hasattr(Job, "expiry_date"):
                        raw = _clean_str(row.get("expiry_date") or row.get("Expiry Date") or row.get("Expiration Date") or "")
                        if raw:
                            try:
                                data["expiry_date"] = timezone.datetime.fromisoformat(raw).date()
                            except Exception:
                                pass

                    data["is_active"] = bool(is_active)
                    data["employer"] = employer

                    # Upsert key: if your CSV has id, use it; otherwise use (employer,title)
                    existing = None
                    raw_id = _clean_str(row.get("id") or row.get("Job ID") or "")
                    if raw_id.isdigit():
                        existing = Job.objects.filter(id=int(raw_id)).first()

                    if existing is None:
                        existing = Job.objects.filter(employer=employer, title=data["title"]).order_by("-id").first()

                    if dry_run:
                        created += 1 if existing is None else 0
                        updated += 1 if existing is not None else 0
                        continue

                    with transaction.atomic():
                        if existing is None:
                            Job.objects.create(**data)
                            created += 1
                        else:
                            for k, v in data.items():
                                setattr(existing, k, v)
                            existing.save()
                            updated += 1

                except Exception as e:
                    errors += 1
                    self.stderr.write(self.style.ERROR(f"[Row {i}] ERROR: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"[jobs:{mode}] done. created={created} updated={updated} skipped={skipped} errors={errors} truncated_fields={truncated_fields}"
            )
        )
