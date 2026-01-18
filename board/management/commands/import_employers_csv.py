import csv
import re
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from board.models import Employer


def _clean_str(v):
    if v is None:
        return ""
    s = str(v).strip()
    # collapse internal whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def _max_len_for(model_cls, field_name: str):
    try:
        f = model_cls._meta.get_field(field_name)
        return getattr(f, "max_length", None)
    except Exception:
        return None


def _truncate_to_field(model_cls, field_name: str, value):
    """
    Enforce model field max_length WITHOUT changing models.
    If field has max_length and value is longer, truncate safely.
    """
    if value is None:
        return None
    s = str(value)
    max_len = _max_len_for(model_cls, field_name)
    if max_len and len(s) > int(max_len):
        return s[: int(max_len)]
    return s


class Command(BaseCommand):
    help = "Import Employers from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **opts):
        csv_path = Path(opts["csv_path"])
        dry_run = bool(opts["dry_run"])

        if not csv_path.exists():
            self.stderr.write(self.style.ERROR(f"CSV not found: {csv_path}"))
            return

        created = 0
        updated = 0
        skipped = 0
        errors = 0
        truncated_fields = 0

        User = get_user_model()

        # You want: most recent in admin = order_by("-id") in admin.py (separate),
        # this importer just ensures data is safe + consistent.

        def _set(data: dict, field_name: str, raw_value, allow_blank=True):
            nonlocal truncated_fields
            s = _clean_str(raw_value)

            if not s and allow_blank:
                data[field_name] = ""
                return

            # Enforce max_length if applicable
            before = s
            s2 = _truncate_to_field(Employer, field_name, s)
            if s2 is not None and before != s2:
                truncated_fields += 1
            data[field_name] = s2

        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader, start=1):
                try:
                    # --- REQUIRED MINIMUMS ---
                    email = _clean_str(row.get("email") or row.get("Email") or "")
                    if not email:
                        skipped += 1
                        continue

                    # Find or create user
                    user = User.objects.filter(email__iexact=email).first()
                    if not user:
                        # Username fallback (if your auth model uses username)
                        username = _clean_str(row.get("username") or row.get("Username") or "")
                        if not username:
                            username = email.split("@")[0][:150]

                        # Create user WITHOUT setting a password (unusable) unless CSV provides one
                        password = row.get("password") or row.get("Password") or None
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            password=password if password else None,
                        )

                    # Employer row
                    employer = Employer.objects.filter(user=user).first()

                    data = {}

                    # These field names MUST match your model (contract: no renames).
                    # We defensively map common CSV headers -> your model fields.
                    _set(data, "email", email, allow_blank=False)

                    # Prefer company_name if present, else name
                    company_name = _clean_str(
                        row.get("company_name")
                        or row.get("Company Name")
                        or row.get("company")
                        or row.get("Company")
                        or row.get("name")
                        or row.get("Name")
                        or ""
                    )
                    if company_name:
                        _set(data, "company_name", company_name)
                    else:
                        # Some projects use Employer.name; keep both if your model has both.
                        # Only set fields that exist.
                        if hasattr(Employer, "name"):
                            _set(data, "name", _clean_str(row.get("name") or row.get("Name") or ""), allow_blank=True)

                    # Description fields (often long; only max_length enforced if model has it)
                    if hasattr(Employer, "company_description"):
                        _set(
                            data,
                            "company_description",
                            row.get("company_description") or row.get("Company Description") or "",
                            allow_blank=True,
                        )
                    if hasattr(Employer, "description"):
                        _set(
                            data,
                            "description",
                            row.get("description") or row.get("Description") or "",
                            allow_blank=True,
                        )

                    # Contact & meta
                    if hasattr(Employer, "phone"):
                        _set(data, "phone", row.get("phone") or row.get("Phone") or "", allow_blank=True)
                    if hasattr(Employer, "website"):
                        _set(data, "website", row.get("website") or row.get("Website") or "", allow_blank=True)
                    if hasattr(Employer, "location"):
                        _set(data, "location", row.get("location") or row.get("Location") or "", allow_blank=True)

                    # Credits
                    if hasattr(Employer, "credits"):
                        raw_credits = _clean_str(row.get("credits") or row.get("Credits") or "")
                        if raw_credits:
                            try:
                                data["credits"] = int(float(raw_credits))
                            except Exception:
                                pass

                    # Approval/login flags
                    # If your CSV includes these, honor them; else default approved+active for main employers.csv
                    # (Your status CSV scripts handle pending/deactivated separately.)
                    if hasattr(Employer, "is_approved"):
                        raw = _clean_str(row.get("is_approved") or row.get("approved") or "")
                        if raw:
                            data["is_approved"] = raw.lower() in ("1", "true", "yes", "y")
                        else:
                            data["is_approved"] = True

                    if hasattr(Employer, "login_active"):
                        raw = _clean_str(row.get("login_active") or row.get("active") or "")
                        if raw:
                            data["login_active"] = raw.lower() in ("1", "true", "yes", "y")
                        else:
                            data["login_active"] = True

                    if dry_run:
                        # Do not write anything
                        created += 1 if employer is None else 0
                        updated += 1 if employer is not None else 0
                        continue

                    with transaction.atomic():
                        if employer is None:
                            data["user"] = user
                            Employer.objects.create(**data)
                            created += 1
                        else:
                            for k, v in data.items():
                                setattr(employer, k, v)
                            employer.save()
                            updated += 1

                except IntegrityError as e:
                    errors += 1
                    self.stderr.write(self.style.ERROR(f"[Row {i}] ERROR (Integrity): {e}"))
                except Exception as e:
                    errors += 1
                    self.stderr.write(self.style.ERROR(f"[Row {i}] ERROR: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"[employers] done. created={created} updated={updated} skipped={skipped} errors={errors} truncated_fields={truncated_fields}"
            )
        )
