# board/management/commands/import_invoices_csv.py
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from board.models import Employer, Invoice


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


def _parse_date_to_dt(s: Any):
    """
    Invoice export sample: 'Dec 17, 2025'
    We'll store it as a datetime at noon local time (safe, timezone-aware later).
    """
    s = _clean(s)
    if not s:
        return timezone.now()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            # store as timezone-aware-ish by using current tz and noon
            return timezone.make_aware(datetime(d.year, d.month, d.day, 12, 0, 0))
        except Exception:
            continue
    return timezone.now()


def _parse_total_to_cents(s: Any) -> int:
    s = _clean(s)
    if not s:
        return 0
    # "$75.00" -> 7500
    s = s.replace("$", "").replace(",", "").strip()
    try:
        return int(round(float(s) * 100))
    except Exception:
        return 0


PROCESSOR_MAP = {
    "stripe": "stripe",
    "paypal": "paypal",
    "manual": "manual",
}

STATUS_MAP = {
    "paid": "paid",
    "pending": "pending",
    "failed": "failed",
    "refunded": "refunded",
    "void": "void",
}


@dataclass
class ImportStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


class Command(BaseCommand):
    help = "Import Invoices from legacy export CSV (matches by Employer.company_name)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument("--dry-run", action="store_true", help="Parse + validate, but do not write to DB.")
        parser.add_argument(
            "--currency",
            type=str,
            default="CAD",
            help="Currency to use when CSV does not include a currency column (default CAD).",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        dry_run = options["dry_run"]
        default_currency = (options["currency"] or "CAD").upper()

        p = Path(csv_path)
        if not p.is_absolute():
            p = Path(settings.BASE_DIR) / p

        if not p.exists():
            raise FileNotFoundError(f"CSV not found: {p}")

        with p.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            required = {"Invoice #", "Customer Name", "Date", "Payment Method", "Total", "Status"}
            missing = [h for h in required if h not in set(headers)]
            if missing:
                raise ValueError(f"CSV missing required columns: {missing}. Found headers: {headers}")

            stats = ImportStats()
            ctx = transaction.atomic() if not dry_run else _NoopCtx()

            with ctx:
                for idx, row in enumerate(reader, start=2):
                    try:
                        inv_id = _parse_int(row.get("Invoice #"))
                        customer = _clean(row.get("Customer Name"))
                        if not inv_id or not customer:
                            stats.skipped += 1
                            continue

                        # Match Employer by company_name (case-insensitive exact match)
                        employer = Employer.objects.filter(company_name__iexact=customer).first()

                        # If not found, try a looser match (unique contains)
                        if not employer:
                            qs = Employer.objects.filter(company_name__icontains=customer).order_by("id")
                            if qs.count() == 1:
                                employer = qs.first()

                        if not employer:
                            stats.skipped += 1
                            continue

                        total_cents = _parse_total_to_cents(row.get("Total"))
                        dt = _parse_date_to_dt(row.get("Date"))

                        processor_raw = _lower(row.get("Payment Method"))
                        processor = PROCESSOR_MAP.get(processor_raw, "")
                        status_raw = _lower(row.get("Status"))
                        status = STATUS_MAP.get(status_raw, "pending")

                        # Validate max_length fields (avoid DB crash)
                        if processor and len(processor) > 20:
                            raise ValueError(f"processor too long (len={len(processor)} > 20) invoice={inv_id}")
                        if status and len(status) > 20:
                            raise ValueError(f"status too long (len={len(status)} > 20) invoice={inv_id}")
                        if len(default_currency) > 10:
                            raise ValueError("currency too long (>10)")

                        existing = Invoice.objects.filter(id=inv_id).first()

                        if dry_run:
                            if existing:
                                stats.updated += 1
                            else:
                                stats.created += 1
                            continue

                        if existing:
                            inv = existing
                        else:
                            inv = Invoice(id=inv_id)

                        inv.employer = employer
                        inv.amount = int(total_cents or 0)
                        inv.currency = default_currency
                        inv.processor = processor
                        inv.status = status
                        inv.order_date = dt

                        # No reference / discount code in this export
                        inv.processor_reference = inv.processor_reference or ""
                        inv.discount_code = inv.discount_code or ""

                        inv.save()

                        if existing:
                            stats.updated += 1
                        else:
                            stats.created += 1

                    except Exception as e:
                        stats.errors += 1
                        stats.skipped += 1
                        self.stdout.write(self.style.ERROR(f"[invoices] Row {idx} ERROR: {e}"))

                if dry_run:
                    self.stdout.write(self.style.WARNING("[invoices] DRY-RUN: no DB writes performed."))

            self.stdout.write(
                self.style.SUCCESS(
                    f"[invoices] created={stats.created} updated={stats.updated} skipped={stats.skipped} errors={stats.errors}"
                )
            )


class _NoopCtx:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
