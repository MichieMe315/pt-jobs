# board/startup_import.py
import os
import sys
from pathlib import Path

from django.conf import settings
from django.db import OperationalError, ProgrammingError


def run_bulk_import_if_enabled() -> None:
    """
    Runs bulk CSV imports ONCE on web start, controlled by env var.

    Set in production (Railway/DO env vars):
      RUN_BULK_IMPORT_ON_STARTUP=1

    Optional overrides:
      BULK_IMPORT_EMPLOYERS=board/data/employers.csv
      BULK_IMPORT_EMPLOYERS_PENDING=board/data/employers_pending.csv
      BULK_IMPORT_EMPLOYERS_DEACTIVATED=board/data/employers_deactivated.csv
      BULK_IMPORT_JOBSEEKERS_ACTIVE=board/data/jobseekers_active.csv
      BULK_IMPORT_JOBSEEKERS_INACTIVE=board/data/jobseekers_inactive.csv
      BULK_IMPORT_JOBSEEKERS_PENDING=board/data/jobseekers_pending.csv
      BULK_IMPORT_JOBS_ACTIVE=board/data/jobs_active.csv
      BULK_IMPORT_JOBS_EXPIRED=board/data/jobs_expired.csv
      BULK_IMPORT_INVOICES=board/data/invoices.csv
    """
    if os.environ.get("RUN_BULK_IMPORT_ON_STARTUP") != "1":
        return

    # Never run during management commands that shouldn't be affected
    blocked = {
        "migrate",
        "makemigrations",
        "collectstatic",
        "shell",
        "createsuperuser",
        "dbshell",
        "check",
        "test",
    }
    if any(cmd in sys.argv for cmd in blocked):
        return

    # Basic file map
    files = {
        "employers": os.environ.get("BULK_IMPORT_EMPLOYERS", "board/data/employers.csv"),
        "employers_pending": os.environ.get(
            "BULK_IMPORT_EMPLOYERS_PENDING", "board/data/employers_pending.csv"
        ),
        "employers_deactivated": os.environ.get(
            "BULK_IMPORT_EMPLOYERS_DEACTIVATED", "board/data/employers_deactivated.csv"
        ),
        "jobseekers_active": os.environ.get(
            "BULK_IMPORT_JOBSEEKERS_ACTIVE", "board/data/jobseekers_active.csv"
        ),
        "jobseekers_inactive": os.environ.get(
            "BULK_IMPORT_JOBSEEKERS_INACTIVE", "board/data/jobseekers_inactive.csv"
        ),
        "jobseekers_pending": os.environ.get(
            "BULK_IMPORT_JOBSEEKERS_PENDING", "board/data/jobseekers_pending.csv"
        ),
        "jobs_active": os.environ.get("BULK_IMPORT_JOBS_ACTIVE", "board/data/jobs_active.csv"),
        "jobs_expired": os.environ.get("BULK_IMPORT_JOBS_EXPIRED", "board/data/jobs_expired.csv"),
        "invoices": os.environ.get("BULK_IMPORT_INVOICES", "board/data/invoices.csv"),
    }

    # Resolve to absolute paths
    resolved = {k: (Path(settings.BASE_DIR) / v) for k, v in files.items()}

    # If nothing exists, skip quietly
    if not any(p.exists() for p in resolved.values()):
        print("[BULK IMPORT] SKIP: no CSV files found.")
        return

    try:
        from board.models import Employer, JobSeeker, Job, Invoice  # noqa: F401
    except Exception as e:
        print(f"[BULK IMPORT] SKIP: model import failed: {e}")
        return

    # DB readiness check
    try:
        from board.models import Employer as EmployerModel
        EmployerModel.objects.exists()
    except (OperationalError, ProgrammingError) as e:
        print(f"[BULK IMPORT] SKIP: DB not ready: {e}")
        return

    try:
        # Importers
        from board.management.commands.import_employers_csv import Command as ImportEmployers
        from board.management.commands.update_employers_status_csv import (
            Command as UpdateEmployerStatus,
        )
        from board.management.commands.import_jobseekers_csv import Command as ImportJobSeekers
        from board.management.commands.import_jobs_csv import Command as ImportJobs
        from board.management.commands.import_invoices_csv import Command as ImportInvoices

        # Employers (main)
        if resolved["employers"].exists():
            print(f"[BULK IMPORT] employers -> {resolved['employers']}")
            ImportEmployers().handle(csv_path=str(resolved["employers"]), dry_run=False)

        # Employers: pending/deactivated lists
        if resolved["employers_pending"].exists():
            print(f"[BULK IMPORT] employers_pending -> {resolved['employers_pending']}")
            UpdateEmployerStatus().handle(
                csv_path=str(resolved["employers_pending"]), kind="pending", dry_run=False
            )

        if resolved["employers_deactivated"].exists():
            print(f"[BULK IMPORT] employers_deactivated -> {resolved['employers_deactivated']}")
            UpdateEmployerStatus().handle(
                csv_path=str(resolved["employers_deactivated"]), kind="deactivated", dry_run=False
            )

        # JobSeekers
        from board.models import JobSeeker as JobSeekerModel

        js_count = JobSeekerModel.objects.count()
        if js_count == 0:
            if resolved["jobseekers_active"].exists():
                ImportJobSeekers().handle(
                    csv_path=str(resolved["jobseekers_active"]), mode="active"
                )
            if resolved["jobseekers_inactive"].exists():
                ImportJobSeekers().handle(
                    csv_path=str(resolved["jobseekers_inactive"]), mode="inactive"
                )
            if resolved["jobseekers_pending"].exists():
                ImportJobSeekers().handle(
                    csv_path=str(resolved["jobseekers_pending"]), mode="pending"
                )
        else:
            print(f"[BULK IMPORT] SKIP: JobSeekers already exist (count={js_count}).")

        # Jobs
        from board.models import Job as JobModel

        jobs_count = JobModel.objects.count()
        if jobs_count == 0:
            if resolved["jobs_active"].exists():
                ImportJobs().handle(csv_path=str(resolved["jobs_active"]), mode="active", dry_run=False)
            if resolved["jobs_expired"].exists():
                ImportJobs().handle(
                    csv_path=str(resolved["jobs_expired"]), mode="expired", dry_run=False
                )
        else:
            print(f"[BULK IMPORT] SKIP: Jobs already exist (count={jobs_count}).")

        # Invoices
        from board.models import Invoice as InvoiceModel

        inv_count = InvoiceModel.objects.count()
        if inv_count == 0 and resolved["invoices"].exists():
            ImportInvoices().handle(csv_path=str(resolved["invoices"]), dry_run=False)
        else:
            print(f"[BULK IMPORT] SKIP: Invoices already exist (count={inv_count}).")

        print("[BULK IMPORT] DONE")

    except Exception as e:
        # CRITICAL: do not kill the web process
        print(f"[BULK IMPORT] ERROR (non-fatal): {e}")
        return
