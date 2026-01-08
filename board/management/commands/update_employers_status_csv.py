# board/management/commands/update_employers_status_csv.py
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from board.models import Employer


def _clean(s: Any) -> str:
    if s is None:
        return ""
    val = str(s).strip()
    return "" if val.lower() in {"nan", "none", "null"} else val


@dataclass
class Stats:
    updated: int = 0
    skipped: int = 0
    errors: int = 0


class Command(BaseCommand):
    help = "Update Employer status from legacy CSV exports (employers_deactivated/employers_pending)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument("--kind", choices=["deactivated", "pending"], required=True)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        kind = options["kind"]
        dry_run = options["dry_run"]

        p = Path(csv_path)
        if not p.is_absolute():
            p = Path(settings.BASE_DIR) / p
        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")

        with p.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            if "Employer Email" not in set(headers):
                raise ValueError(f"CSV must include 'Employer Email'. Found headers: {headers}")

            stats = Stats()
            ctx = transaction.atomic() if not dry_run else _NoopCtx()

            with ctx:
                for idx, row in enumerate(reader, start=2):
                    try:
                        email = _clean(row.get("Employer Email")).lower()
                        if not email:
                            stats.skipped += 1
                            continue

                        emp = Employer.objects.filter(email__iexact=email).first()
                        if not emp:
                            stats.skipped += 1
                            continue

                        if kind == "deactivated":
                            emp.is_approved = False
                            emp.login_active = False
                        else:  # pending
                            emp.is_approved = False
                            emp.login_active = True

                        if not dry_run:
                            emp.save()

                        stats.updated += 1

                    except Exception as e:
                        stats.errors += 1
                        stats.skipped += 1
                        self.stdout.write(self.style.ERROR(f"[employers:{kind}] Row {idx} ERROR: {e}"))

                if dry_run:
                    self.stdout.write(self.style.WARNING(f"[employers:{kind}] DRY-RUN: no DB writes performed."))

            self.stdout.write(
                self.style.SUCCESS(f"[employers:{kind}] updated={stats.updated} skipped={stats.skipped} errors={stats.errors}")
            )


class _NoopCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
