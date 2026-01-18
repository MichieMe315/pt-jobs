from __future__ import annotations

import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError, transaction

from board.models import Employer


def _norm(val: str | None) -> str:
    return (val or "").strip()


def _fit(model_cls, field_name: str, value):
    """Trim strings to the model field's max_length (if present).

    This prevents Postgres errors like:
      value too long for type character varying(200)

    We do *not* rename any fields; we simply ensure imported CSV values
    fit the existing schema.
    """
    if value is None:
        return None

    # Only trim strings
    if not isinstance(value, str):
        return value

    try:
        f = model_cls._meta.get_field(field_name)
        max_len = getattr(f, "max_length", None)
    except Exception:
        max_len = None

    if max_len and len(value) > int(max_len):
        return value[: int(max_len)]
    return value


def _pick_status_from_filename(path: Path) -> str:
    name = path.name.lower()
    if "pending" in name:
        return "pending"
    if "deactiv" in name or "inactive" in name:
        return "inactive"
    return "active"


class Command(BaseCommand):
    help = "Import employers from one or more CSV files."

    def add_arguments(self, parser):
        parser.add_argument("csv_paths", nargs="+", type=str)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        User = get_user_model()

        dry_run: bool = bool(options.get("dry_run"))
        csv_paths = [Path(p) for p in options["csv_paths"]]

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        # Use a single outer transaction; per-row savepoints keep the transaction usable
        # even if one row fails.
        outer_ctx = transaction.atomic() if not dry_run else transaction.atomic()
        with outer_ctx:
            for csv_path in csv_paths:
                status = _pick_status_from_filename(csv_path)

                if status == "active":
                    is_approved = True
                    login_active = True
                elif status == "inactive":
                    is_approved = False
                    login_active = False
                else:  # pending
                    # You said: pending shouldn't be active / can't login.
                    is_approved = False
                    login_active = False

                self.stdout.write(
                    f"--- Importing: {csv_path.name} | status={status} (is_approved={is_approved}, login_active={login_active}) ---"
                )

                if not csv_path.exists():
                    self.stdout.write(self.style.ERROR(f"File not found: {csv_path}"))
                    errors += 1
                    continue

                with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    for row_idx, row in enumerate(reader, start=2):
                        # Per-row savepoint so DataError/IntegrityError doesn't poison the transaction.
                        with transaction.atomic():
                            try:
                                email = _norm(row.get("email") or row.get("Email") or row.get("EMAIL"))
                                if not email:
                                    skipped += 1
                                    continue

                                # Company name can appear under different headers in your exports.
                                company_name = _norm(
                                    row.get("company_name")
                                    or row.get("Company Name")
                                    or row.get("company")
                                    or row.get("name")
                                    or row.get("Name")
                                )

                                # Optional fields
                                phone = _norm(row.get("phone") or row.get("Phone"))
                                website = _norm(row.get("website") or row.get("Website"))
                                location = _norm(row.get("location") or row.get("Location"))

                                # Some datasets use company_description; others use description.
                                company_description = row.get("company_description")
                                if company_description is None:
                                    company_description = row.get("company_description ")
                                company_description = (company_description if company_description is not None else row.get("description"))
                                company_description = (company_description or "").strip()

                                # Create/update user first.
                                user = User.objects.filter(email__iexact=email).first()
                                if not user:
                                    # username max_length is usually 150 (Django default) - trim if necessary.
                                    username_val = _fit(User, "username", email)
                                    user = User.objects.create(username=username_val, email=_fit(User, "email", email))
                                    user.set_unusable_password()
                                    user.is_active = True
                                    user.save(update_fields=["password", "is_active"])

                                data = {
                                    "user": user,
                                    "email": _fit(Employer, "email", email),
                                    "company_name": _fit(Employer, "company_name", company_name),
                                    "company_description": company_description,
                                    "phone": _fit(Employer, "phone", phone),
                                    "website": _fit(Employer, "website", website),
                                    "location": _fit(Employer, "location", location),
                                    "is_approved": is_approved,
                                    "login_active": login_active,
                                }

                                employer = Employer.objects.filter(email__iexact=email).first()
                                if employer:
                                    for k, v in data.items():
                                        setattr(employer, k, v)
                                    if not dry_run:
                                        employer.save()
                                    updated += 1
                                else:
                                    if not dry_run:
                                        Employer.objects.create(**data)
                                    created += 1

                            except (IntegrityError,) as e:
                                errors += 1
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"[Row {row_idx}] ERROR: {type(e).__name__}: {e}"
                                    )
                                )
                            except Exception as e:
                                # Includes DataError 'value too long...' and any unexpected column weirdness.
                                errors += 1
                                self.stdout.write(
                                    self.style.ERROR(
                                        f"[Row {row_idx}] ERROR: {type(e).__name__}: {e}"
                                    )
                                )

            if dry_run:
                # Roll back everything.
                transaction.set_rollback(True)

        if dry_run:
            self.stdout.write(self.style.WARNING("[employers] DRY-RUN: no DB writes performed."))
        self.stdout.write(
            self.style.SUCCESS(
                f"[employers] created={created} updated={updated} skipped={skipped} errors={errors}"
            )
        )
