# board/management/commands/update_employers_status_csv.py
import csv
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction

from board.models import Employer


EMAIL_KEYS = [
    "email",
    "Email",
    "Employer Email",
    "employer_email",
    "EmployerEmail",
]


def pick_email_key(fieldnames: list[str] | None) -> Optional[str]:
    if not fieldnames:
        return None
    for k in EMAIL_KEYS:
        if k in fieldnames:
            return k
    return None


def normalize_email(val: str) -> str:
    return (val or "").strip().lower()


class Command(BaseCommand):
    help = "Mark employers from CSV as inactive (pending or deactivated legacy lists)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument(
            "--kind",
            required=True,
            choices=["pending", "deactivated"],
            help="Legacy status type; both result in inactive employers.",
        )
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **opts):
        csv_path: str = opts["csv_path"]
        kind: str = opts["kind"]
        dry_run: bool = opts["dry_run"]

        updated = 0
        skipped = 0
        errors = 0

        # CONTRACT RULE:
        # pending + deactivated => NOT approved, login blocked
        target_is_approved = False
        target_login_active = False

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            email_key = pick_email_key(reader.fieldnames)

            if not email_key:
                raise ValueError(
                    f"CSV must include an email column. Found headers: {reader.fieldnames}"
                )

            for idx, row in enumerate(reader, start=2):
                try:
                    email = normalize_email(row.get(email_key, ""))
                    if not email:
                        skipped += 1
                        continue

                    emp = Employer.objects.filter(email__iexact=email).first()
                    if not emp:
                        skipped += 1
                        continue

                    # already inactive → skip
                    if (
                        emp.is_approved is False
                        and emp.login_active is False
                    ):
                        skipped += 1
                        continue

                    if dry_run:
                        updated += 1
                        continue

                    with transaction.atomic():
                        emp.is_approved = target_is_approved
                        emp.login_active = target_login_active
                        emp.save(update_fields=["is_approved", "login_active"])

                    updated += 1

                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f"[employers:{kind}] Row {idx} ERROR: {e}")
                    )

        if dry_run:
            self.stdout.write(self.style.WARNING("[employers] DRY-RUN: no DB writes performed."))

        self.stdout.write(
            self.style.SUCCESS(
                f"[employers:{kind}] updated={updated} skipped={skipped} errors={errors}"
            )
        )
