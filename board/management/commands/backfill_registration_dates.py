from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Optional

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from board.models import Employer, JobSeeker


def _parse_dt(value: str):
    v = (value or "").strip()
    if not v:
        return None
    dt = parse_datetime(v)
    if dt is None:
        # Try date-only (rare), treat as midnight local time
        try:
            d = timezone.datetime.fromisoformat(v).date()
            dt = timezone.datetime(d.year, d.month, d.day, 0, 0, 0)
        except Exception:
            return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


class Command(BaseCommand):
    help = "Backfill Employer/JobSeeker created_at (and related User.date_joined) from CSV Registration Date."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            action="append",
            default=[],
            help="Path to a CSV file (can be used multiple times). Must include Registration Date + Employer Id or Job Seeker Id.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Show what would change without saving.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Update even if created_at is already different (normally only updates when it looks wrong).",
        )

    def handle(self, *args, **options):
        csv_paths = options["csv"] or []
        dry_run: bool = options["dry_run"]
        force: bool = options["force"]

        if not csv_paths:
            self.stderr.write("You must pass at least one --csv path.")
            return

        total_updates = 0
        total_missing = 0
        total_bad_date = 0

        for p in csv_paths:
            path = Path(p)
            if not path.exists():
                self.stderr.write(f"Missing CSV: {path}")
                continue

            self.stdout.write(f"\nReading: {path}")
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                cols = set(reader.fieldnames or [])
                has_employer_id = "Employer Id" in cols
                has_jobseeker_id = "Job Seeker Id" in cols
                if "Registration Date" not in cols or (not has_employer_id and not has_jobseeker_id):
                    self.stderr.write(
                        "CSV must include 'Registration Date' and either 'Employer Id' or 'Job Seeker Id'."
                    )
                    continue

                for row in reader:
                    reg_dt = _parse_dt(row.get("Registration Date", ""))
                    if not reg_dt:
                        total_bad_date += 1
                        continue

                    if has_employer_id and row.get("Employer Id"):
                        try:
                            pk = int(str(row["Employer Id"]).strip())
                        except Exception:
                            continue
                        try:
                            obj = Employer.objects.select_related("user").get(pk=pk)
                        except Employer.DoesNotExist:
                            total_missing += 1
                            continue

                        if (not force) and obj.created_at:
                            # Only change if it looks like an import overwrite
                            if abs((obj.created_at - reg_dt).total_seconds()) < 60:
                                continue

                        self.stdout.write(f"Employer {pk}: {obj.created_at} -> {reg_dt}")
                        if not dry_run:
                            Employer.objects.filter(pk=pk).update(created_at=reg_dt)
                            # Keep auth user aligned if present
                            if getattr(obj, "user_id", None):
                                type(obj.user).objects.filter(pk=obj.user_id).update(date_joined=reg_dt)
                        total_updates += 1

                    if has_jobseeker_id and row.get("Job Seeker Id"):
                        try:
                            pk = int(str(row["Job Seeker Id"]).strip())
                        except Exception:
                            continue
                        try:
                            obj = JobSeeker.objects.select_related("user").get(pk=pk)
                        except JobSeeker.DoesNotExist:
                            total_missing += 1
                            continue

                        if (not force) and obj.created_at:
                            if abs((obj.created_at - reg_dt).total_seconds()) < 60:
                                continue

                        self.stdout.write(f"JobSeeker {pk}: {obj.created_at} -> {reg_dt}")
                        if not dry_run:
                            JobSeeker.objects.filter(pk=pk).update(created_at=reg_dt)
                            if getattr(obj, "user_id", None):
                                type(obj.user).objects.filter(pk=obj.user_id).update(date_joined=reg_dt)
                        total_updates += 1

        self.stdout.write("\nDone.")
        self.stdout.write(f"Updated: {total_updates}")
        self.stdout.write(f"Missing records: {total_missing}")
        self.stdout.write(f"Bad/unparsed dates: {total_bad_date}")
