# board/startup_import.py
import os
import sys
from pathlib import Path

from django.conf import settings
from django.db import OperationalError, ProgrammingError


def run_bulk_import_if_enabled() -> None:
    """
    Runs bulk CSV imports ONCE on web start, controlled by env var.

    Set in production env vars:
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

    # Never run during these management commands
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

    files = {
        "employers": os.environ.get("BULK_IMPORT_EMPLOYERS", "board/data/employers.csv"),
        "employers_pending": os.environ.get("BULK_IMPORT_EMPLOYERS_PENDING", "board/data/employers_pending.csv"),
        "employers_deactivated": os.environ.get("BULK_IMPORT_EMPLOYERS_DEACTIVATED", "board/data/employers_deactivated.csv"),
        "jobseekers_active": os.environ.get("BULK_IMPORT_JOBSEEKERS_ACTIVE", "board/data/jobseekers_active.csv"),
        "jobseekers_inactive": os.environ.get("BULK_IMPORT_JOBSEEKERS_INACTIVE", "board/data/jobseekers_inactive.csv"),
        "jobseekers_pending": os.environ.get("BULK_IMPORT_JOBSEEKERS_PENDING", "board/data/jobseekers_pending.csv"),
        "jobs_active": os.environ.get("BULK_IMPORT_JOBS_ACTIVE", "board/data/jobs_active.csv"),
        "jobs_expired": os.environ.get("BULK_IMPORT_JOBS_EXPIRED", "board/data/jobs_expired.csv"),
        "invoices": os.environ.get("BULK_IMPORT_INVOICES", "board/data/invoices.csv"),
    }

    resolved = {k: (Path(settings.BASE_DIR) / v) for k, v in files.items()}

    if not any(p.exists() for p in resolved.values()):
        print("[startup_import] SKIP: no CSV files found.")
        return

    # DB readiness check
    try:
        from board.models import Employer as EmployerModel
        EmployerModel.objects.exists()
    except (OperationalError, ProgrammingError) as e:
        print(f"[startup_import] SKIP: DB not ready: {e}")
        return
    except Exception as e:
        print(f"[startup_import] SKIP: DB check failed: {e}")
        return

    def _safe(label: str, fn):
        try:
            fn()
        except Exception as e:
            # CRITICAL: never crash web boot
            print(f"[startup_import] ERROR during {label} (non-fatal): {e}")

    try:
        from board.management.commands.import_employers_csv import Command as ImportEmployers
        from board.management.commands.update_employers_status_csv import Command as UpdateEmployerStatus
        from board.management.commands.import_jobseekers_csv import Command as ImportJobSeekers
        from board.management.commands.import_jobs_csv import Command as ImportJobs
        from board.management.commands.import_invoices_csv import Command as ImportInvoices
        from board.models import JobSeeker, Job, Invoice
    except Exception as e:
        print(f"[startup_import] SKIP: could not import commands/models: {e}")
        return

    print("[startup_import] IMPORT ENABLED: starting bulk CSV imports.")

    if resolved["employers"].exists():
        _safe("import_employers", lambda: ImportEmployers().handle(csv_path=str(resolved["employers"]), dry_run=False))

    if resolved["employers_pending"].exists():
        _safe("employers_pending_status", lambda: UpdateEmployerStatus().handle(csv_path=str(resolved["employers_pending"]), kind="pending", dry_run=False))

    if resolved["employers_deactivated"].exists():
        _safe("employers_deactivated_status", lambda: UpdateEmployerStatus().handle(csv_path=str(resolved["employers_deactivated"]), kind="deactivated", dry_run=False))

    js_count = JobSeeker.objects.count()
    if js_count == 0:
        if resolved["jobseekers_active"].exists():
            _safe("jobseekers_active", lambda: ImportJobSeekers().handle(csv_path=str(resolved["jobseekers_active"]), mode="active"))
        if resolved["jobseekers_inactive"].exists():
            _safe("jobseekers_inactive", lambda: ImportJobSeekers().handle(csv_path=str(resolved["jobseekers_inactive"]), mode="inactive"))
        if resolved["jobseekers_pending"].exists():
            _safe("jobseekers_pending", lambda: ImportJobSeekers().handle(csv_path=str(resolved["jobseekers_pending"]), mode="pending"))
    else:
        print(f"[startup_import] SKIP: JobSeekers already exist (count={js_count}).")

    jobs_count = Job.objects.count()
    if jobs_count == 0:
        if resolved["jobs_active"].exists():
            _safe("jobs_active", lambda: ImportJobs().handle(csv_path=str(resolved["jobs_active"]), mode="active", dry_run=False))
        if resolved["jobs_expired"].exists():
            _safe("jobs_expired", lambda: ImportJobs().handle(csv_path=str(resolved["jobs_expired"]), mode="expired", dry_run=False))
    else:
        print(f"[startup_import] SKIP: Jobs already exist (count={jobs_count}).")

    inv_count = Invoice.objects.count()
    if inv_count == 0 and resolved["invoices"].exists():
        _safe("invoices", lambda: ImportInvoices().handle(csv_path=str(resolved["invoices"]), dry_run=False))
    else:
        print(f"[startup_import] SKIP: Invoices already exist (count={inv_count}).")

    print("[startup_import] DONE")
