# board/management/commands/import_jobseekers_csv.py
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from board.models import JobSeeker


def _clean(s: Any) -> str:
    if s is None:
        return ""
    val = str(s).strip()
    return "" if val.lower() in {"nan", "none", "null"} else val


def _lower(s: Any) -> str:
    return _clean(s).lower()


def _parse_bool_yes_no(s: Any) -> bool:
    s = _lower(s)
    return s in {"1", "true", "yes", "y", "on"}


def _split_name(full: str) -> Tuple[str, str]:
    full = _clean(full)
    if not full:
        return "", ""
    parts = [p for p in re.split(r"\s+", full) if p]
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _parse_datetime(s: Any):
    s = _clean(s)
    if not s:
        return None
    # Expected: 2025-08-05 16:27:07
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


OPPORTUNITY_MAP = {
    "full-time": "full_time",
    "full time": "full_time",
    "full_time": "full_time",
    "part-time": "part_time",
    "part time": "part_time",
    "part_time": "part_time",
    "contractor": "contractor",
    "contract": "contractor",
    "casual": "casual",
    "locum": "locum",
    "temporary": "temporary",
}


@dataclass
class ImportStats:
    users_created: int = 0
    users_existing: int = 0
    jobseekers_created: int = 0
    jobseekers_updated: int = 0
    skipped: int = 0
    errors: int = 0


class Command(BaseCommand):
    help = "Import Job Seekers from legacy export CSVs (jobseekers_active/inactive/pending)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument(
            "--mode",
            choices=["active", "inactive", "pending", "infer"],
            default="infer",
            help="Force is_approved/login_active based on file type.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Parse + validate, but do not write to DB.")

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        mode = options["mode"]
        dry_run = options["dry_run"]

        p = Path(csv_path)
        if not p.is_absolute():
            p = Path(settings.BASE_DIR) / p

        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")

        with p.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            required = {"Email", "Full Name"}
            missing = [h for h in required if h not in set(headers)]
            if missing:
                raise ValueError(f"CSV missing required columns: {missing}. Found headers: {headers}")

            stats = ImportStats()
            User = get_user_model()

            ctx = transaction.atomic() if not dry_run else _NoopCtx()

            with ctx:
                for idx, row in enumerate(reader, start=2):
                    try:
                        email = _clean(row.get("Email")).lower()
                        if not email:
                            stats.skipped += 1
                            continue

                        full_name = _clean(row.get("Full Name"))
                        first_name, last_name = _split_name(full_name)

                        position_desired = _clean(row.get("Position Desired"))
                        registered = _parse_bool_yes_no(row.get("Are you a Registered Professional in Canada?"))

                        opp_raw = _lower(row.get("What type of opportunity are you interested in?"))
                        opp = OPPORTUNITY_MAP.get(opp_raw, "")

                        current_location = _clean(row.get("Where are you currently located?"))
                        open_to_relocate = _parse_bool_yes_no(row.get("Are you open to relocating?"))
                        relocate_where = _clean(row.get("If yes, where?"))

                        require_sponsorship = _parse_bool_yes_no(row.get("Do you require sponsorship to work in Canada?"))
                        seeking_immigration = _parse_bool_yes_no(row.get("Are you seeking immigration to Canada?"))

                        status_raw = _lower(row.get("Status"))
                        reg_dt = _parse_datetime(row.get("Registration Date"))

                        # Decide approval/login based on mode
                        if mode == "active":
                            is_approved = True
                            login_active = True
                        elif mode == "inactive":
                            is_approved = False
                            login_active = False
                        elif mode == "pending":
                            is_approved = False
                            login_active = True
                        else:
                            # infer from Status
                            if "not active" in status_raw or "inactive" in status_raw:
                                is_approved = False
                                login_active = False
                            elif "pending" in status_raw:
                                is_approved = False
                                login_active = True
                            else:
                                is_approved = True
                                login_active = True

                        if len(position_desired) > 200:
                            raise ValueError(f"Position Desired too long (len={len(position_desired)} > 200) for {email}")
                        if len(current_location) > 200:
                            raise ValueError(f"Current Location too long (len={len(current_location)} > 200) for {email}")
                        if len(relocate_where) > 200:
                            raise ValueError(f"Relocate Where too long (len={len(relocate_where)} > 200) for {email}")

                        # Create or fetch User
                        user = User.objects.filter(username__iexact=email).first()
                        created_user = False
                        if not user:
                            user = User(username=email, email=email)
                            if not dry_run:
                                # Imported users should use password reset to set their password
                                user.set_unusable_password()
                                user.save()
                            created_user = True
                            stats.users_created += 1
                        else:
                            stats.users_existing += 1

                        # Create/update JobSeeker
                        js = JobSeeker.objects.filter(user=user).first()
                        if dry_run:
                            if js:
                                stats.jobseekers_updated += 1
                            else:
                                stats.jobseekers_created += 1
                            continue

                        if not js:
                            js = JobSeeker(user=user)
                            stats.jobseekers_created += 1
                        else:
                            stats.jobseekers_updated += 1

                        js.email = email
                        js.first_name = first_name
                        js.last_name = last_name
                        js.position_desired = position_desired
                        js.registered_in_canada = registered
                        js.opportunity_type = opp
                        js.current_location = current_location
                        js.open_to_relocate = open_to_relocate
                        js.relocate_where = relocate_where
                        js.require_sponsorship = require_sponsorship
                        js.seeking_immigration = seeking_immigration

                        js.is_approved = is_approved
                        js.login_active = login_active

                        if is_approved and not js.approved_at:
                            js.approved_at = timezone.now()

                        # NOTE: resume import is NOT supported from these exports
                        # (Has Resume column is informational only)
                        js.save()

                    except Exception as e:
                        stats.errors += 1
                        stats.skipped += 1
                        self.stdout.write(self.style.ERROR(f"[jobseekers] Row {idx} ERROR: {e}"))

                if dry_run:
                    self.stdout.write(self.style.WARNING("[jobseekers] DRY-RUN: no DB writes performed."))

            self.stdout.write(
                self.style.SUCCESS(
                    "[jobseekers] "
                    f"users_created={stats.users_created} users_existing={stats.users_existing} "
                    f"js_created={stats.jobseekers_created} js_updated={stats.jobseekers_updated} "
                    f"skipped={stats.skipped} errors={stats.errors}"
                )
            )


class _NoopCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
