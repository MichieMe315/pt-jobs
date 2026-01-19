import csv
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from board.models import Employer


def _norm(val) -> str:
    return (val or "").strip()


def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _truncate_for_model(model_cls, field_name: str, value: str) -> str:
    """
    Truncate string values to the model field's max_length (if any).
    Prevents Postgres: value too long for type character varying(N)
    """
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


def status_from_filename(filename: str) -> str:
    name = (filename or "").lower()
    if "pending" in name:
        return "pending"
    if "deactivated" in name or "inactive" in name:
        return "inactive"
    return "active"


class Command(BaseCommand):
    help = "Import employers from CSV. Status inferred from filename (active/pending/inactive)."

    def add_arguments(self, parser):
        parser.add_argument("csv_paths", nargs="+", type=str)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        csv_paths = opts["csv_paths"]
        dry_run = bool(opts["dry_run"])

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        User = get_user_model()

        def abs_path(p: str) -> Path:
            pp = Path(p)
            return pp if pp.is_absolute() else Path(settings.BASE_DIR) / pp

        with transaction.atomic():
            for raw in csv_paths:
                path = abs_path(raw)
                if not path.exists():
                    raise FileNotFoundError(f"CSV not found: {path}")

                status = status_from_filename(path.name)
                is_approved = status == "active"
                login_active = status == "active"

                self.stdout.write(
                    f"\n--- Importing: {path.name} | status={status} (is_approved={is_approved}, login_active={login_active}) ---"
                )

                with path.open(newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)

                    for idx, row in enumerate(reader, start=2):
                        try:
                            # --- Required ---
                            email = _norm(row.get("Email") or row.get("email") or row.get("Employer Email") or "").lower()
                            if not email:
                                skipped += 1
                                continue

                            company_name = _norm(
                                row.get("Company Name")
                                or row.get("Company")
                                or row.get("Clinic")
                                or row.get("Employer Name")
                                or ""
                            )

                            # --- Optional fields (keep your existing mappings) ---
                            phone = _norm(row.get("Phone") or row.get("phone") or "")
                            website = _norm(row.get("Website") or row.get("website") or "")
                            location = _norm(row.get("Location") or row.get("location") or "")

                            # Some files have long HTML-ish descriptions
                            company_description = _strip_html(_norm(row.get("Company Description") or row.get("Description") or ""))

                            # ---- TRUNCATE to model max_length (prevents varchar(200) crash) ----
                            email = _truncate_for_model(Employer, "email", email)
                            company_name = _truncate_for_model(Employer, "company_name", company_name)
                            phone = _truncate_for_model(Employer, "phone", phone)
                            website = _truncate_for_model(Employer, "website", website)
                            location = _truncate_for_model(Employer, "location", location)

                            # company_description is usually TextField; still cap for sanity (won't break DB)
                            company_description = (company_description or "")[:5000]

                            # Create/ensure user
                            user = User.objects.filter(email__iexact=email).first()
                            if not user:
                                user = User.objects.create_user(username=email, email=email, password=None)
                                user.set_unusable_password()
                                user.save(update_fields=["password"])

                            # Create or update employer
                            employer = Employer.objects.filter(email__iexact=email).first()
                            data = {
                                "user": user,
                                "email": email,
                                "company_name": company_name or email,
                                "company_description": company_description,
                                "phone": phone,
                                "website": website,
                                "location": location,
                                "is_approved": bool(is_approved),
                                "login_active": bool(login_active),
                            }

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

                        except Exception as e:
                            errors += 1
                            self.stderr.write(f"[Row {idx}] ERROR: {e}")

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            "\n[employers] "
            + ("DRY-RUN: no DB writes performed.\n" if dry_run else "")
            + f"created={created} updated={updated} skipped={skipped} errors={errors}\n"
        )
