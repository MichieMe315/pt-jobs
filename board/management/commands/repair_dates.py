# board/management/commands/repair_dates.py
from __future__ import annotations

import re
from typing import List, Tuple

from django.core.management.base import BaseCommand
from django.db import connection


TYPE_RE = re.compile(r"(date|time|stamp)", re.IGNORECASE)


class Command(BaseCommand):
    help = (
        "SQLite-only: scan all board_* tables, find columns declared as DATE/DATETIME/TIMESTAMP, "
        "and repair rows where those columns are non-text or blank to avoid fromisoformat crashes. "
        "Uses direct SQL updates (no ORM) and skips columns/tables that don't exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--default",
            choices=["now", "null"],
            default="now",
            help="Fallback for malformed values. 'now' = CURRENT_TIMESTAMP/DATE('now'); 'null' = set NULL.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print SQL that would run without writing changes.",
        )

    def handle(self, *args, **opts):
        if connection.vendor != "sqlite":
            self.stderr.write(
                self.style.WARNING(
                    f"This command targets SQLite only (found: {connection.vendor})."
                )
            )
            return

        default = opts["default"]
        dry_run = opts["dry_run"]

        with connection.cursor() as cur:
            # 1) discover tables
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'board_%';"
            )
            tables = [row[0] for row in cur.fetchall()]

            total_updates = 0
            total_skipped = 0
            total_errors = 0

            for table in tables:
                # 2) discover date/time-ish columns on this table
                try:
                    cur.execute(f"PRAGMA table_info({table});")
                    cols: List[Tuple[int, str, str, int, str, int]] = cur.fetchall()
                    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"{table}: cannot introspect -> {exc}"))
                    total_errors += 1
                    continue

                dt_cols = []
                for _, name, decl_type, *_ in cols:
                    decl_type = decl_type or ""
                    if TYPE_RE.search(decl_type):
                        # classify by presence of 'time' in type string: if it has 'time' then treat as datetime
                        kind = "datetime" if re.search(r"time", decl_type, re.IGNORECASE) else "date"
                        dt_cols.append((name, kind))

                if not dt_cols:
                    total_skipped += 1
                    self.stdout.write(self.style.WARNING(f"{table}: no DATE/TIME columns declared; skip"))
                    continue

                # 3) build and execute updates per column
                for col, kind in dt_cols:
                    set_expr = (
                        ("CURRENT_TIMESTAMP" if kind == "datetime" else "DATE('now')")
                        if default == "now"
                        else "NULL"
                    )
                    where = f"(typeof({col}) <> 'text' OR {col} = '')"
                    sql = f"UPDATE {table} SET {col} = {set_expr} WHERE {where};"

                    if dry_run:
                        self.stdout.write(self.style.WARNING(f"[DRY-RUN] {sql}"))
                        continue

                    try:
                        cur.execute(sql)
                        count = cur.rowcount or 0
                        total_updates += count
                        if count:
                            self.stdout.write(
                                self.style.SUCCESS(f"{table}.{col}: {count} row(s) repaired.")
                            )
                    except Exception as exc:
                        total_errors += 1
                        self.stderr.write(
                            self.style.ERROR(f"{table}.{col}: failed\n  {sql}\n  -> {exc}")
                        )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry-run complete. No changes written."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. Total rows repaired: {total_updates}; "
                    f"tables without date/time columns skipped: {total_skipped}; "
                    f"errors: {total_errors}"
                )
            )
