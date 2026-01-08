# board/startup_import.py
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from django.conf import settings
from django.db import OperationalError, ProgrammingError


LOCK_PATH = Path("/tmp/pt_jobs_bulk_import.lock")


def _acquire_lock() -> bool:
    """
    Simple cross-worker guard:
    - First process to create the lock file runs imports.
    - Others skip.
    """
    if os.environ.get("BULK_IMPORT_IGNORE_LOCK") == "1":
        return True

    try:
        fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        return True
    except FileExistsError:
        return False
    except Exception:
        # If lock fails unexpectedly, fail open (but still try to avoid crashing)
        return True


def _release_lock() -> None:
    if os.environ.get("BULK_IMPORT_IGNORE_LOCK") == "1":
        return
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        pass


def run_bulk_import_if_enabled() -> None:
    """
    Enable with Railway variable:
      RUN_BULK_DATA_IMPORT_ON_STARTUP=1

    Expected files in board/data:
      - employers_pending.csv
      - employers_deactivated.csv
      - jobseekers_active.csv
      - jobseekers_inactive.csv
      - jobseekers_pending.csv
      - jobs_active.csv
      - jobs_expired.csv
      - invoices.csv   (or invoices_1.csv etc if you set env path)
    """
    if os.environ.get("RUN_BULK_DATA_IMPORT_ON_STARTUP") != "1":
        return

    blocked = {"migrate", "makemigrations", "collectstatic", "shell", "createsuperuser"}
    if any(cmd in sys.argv for cmd in blocked):
        return

    if not _acquire_lock():
        print("[BULK IMPORT] SKIP: another worker already running imports.")
        return

    try:
        # tiny delay so app registry is fully settled
        time.sleep(2)

        try:
            from board.models import Employer, JobSeeker, Job, Invoice
        except Exception as e:
            print(f"[BULK IMPORT] SKIP: model import failed: {e}")
            return

        # DB readiness check
        try:
            Employer.objects.exists()
        except (OperationalError, ProgrammingError) as e:
            print(f"[BULK IMPORT] SKIP: DB not ready: {e}")
            return

        base = Path(settings.BASE_DIR)

        def _path(env_key: str, default_rel: str) -> Path:
            rel = os.environ.get(env_key, default_rel)
            p = base / rel
            return p

        # --- Employer status updates (always safe to run if file exists) ---
        pending_csv = _path("EMPLOYERS_PENDING_CSV_PATH", "board/data/employers_pending.csv")
        deact_csv = _path("EMPLOYERS_DEACTIVATED_CSV_PATH", "board/data/employers_deactivated.csv")

        try:
            from board.management.commands.update_employers_status_csv import Command as EmpStatusCmd
            if pending_csv.exists():
                print(f"[BULK IMPORT] employers_pending -> {pending_csv}")
                EmpStatusCmd().handle(csv_path=str(pending_csv), kind="pending", dry_run=False)
            if deact_csv.exists():
                print(f"[BULK IMPORT] employers_deactivated -> {deact_csv}")
                EmpStatusCmd().handle(csv_path=str(deact_csv), kind="deactivated", dry_run=False)
        except Exception as e:
            print(f"[BULK IMPORT] WARN: employer status import failed (non-fatal): {e}")

        # --- JobSeekers (only run if none exist, unless forced) ---
        force_js = os.environ.get("BULK_IMPORT_FORCE_JOBSEEKERS") == "1"
        js_count = JobSeeker.objects.count()
        if js_count == 0 or force_js:
            try:
                from board.management.commands.import_jobseekers_csv import Command as JobSeekersCmd

                js_active = _path("JOBSEEKERS_ACTIVE_CSV_PATH", "board/data/jobseekers_active.csv")
                js_inactive = _path("JOBSEEKERS_INACTIVE_CSV_PATH", "board/data/jobseekers_inactive.csv")
                js_pending = _path("JOBSEEKERS_PENDING_CSV_PATH", "board/data/jobseekers_pending.csv")

                if js_active.exists():
                    print(f"[BULK IMPORT] jobseekers_active -> {js_active}")
                    JobSeekersCmd().handle(csv_path=str(js_active), mode="active", dry_run=False)
                if js_inactive.exists():
                    print(f"[BULK IMPORT] jobseekers_inactive -> {js_inactive}")
                    JobSeekersCmd().handle(csv_path=str(js_inactive), mode="inactive", dry_run=False)
                if js_pending.exists():
                    print(f"[BULK IMPORT] jobseekers_pending -> {js_pending}")
                    JobSeekersCmd().handle(csv_path=str(js_pending), mode="pending", dry_run=False)
            except Exception as e:
                print(f"[BULK IMPORT] WARN: jobseekers import failed (non-fatal): {e}")
        else:
            print(f"[BULK IMPORT] SKIP: JobSeekers already exist (count={js_count}).")

        # --- Jobs (only run if none exist, unless forced) ---
        force_jobs = os.environ.get("BULK_IMPORT_FORCE_JOBS") == "1"
        job_count = Job.objects.count()
        if job_count == 0 or force_jobs:
            try:
                from board.management.commands.import_jobs_csv import Command as JobsCmd

                jobs_active = _path("JOBS_ACTIVE_CSV_PATH", "board/data/jobs_active.csv")
                jobs_expired = _path("JOBS_EXPIRED_CSV_PATH", "board/data/jobs_expired.csv")

                if jobs_active.exists():
                    print(f"[BULK IMPORT] jobs_active -> {jobs_active}")
                    JobsCmd().handle(csv_path=str(jobs_active), mode="active", dry_run=False, allow_update=True)
                if jobs_expired.exists():
                    print(f"[BULK IMPORT] jobs_expired -> {jobs_expired}")
                    JobsCmd().handle(csv_path=str(jobs_expired), mode="expired", dry_run=False, allow_update=True)
            except Exception as e:
                print(f"[BULK IMPORT] WARN: jobs import failed (non-fatal): {e}")
        else:
            print(f"[BULK IMPORT] SKIP: Jobs already exist (count={job_count}).")

        # --- Invoices (only run if none exist, unless forced) ---
        force_invoices = os.environ.get("BULK_IMPORT_FORCE_INVOICES") == "1"
        inv_count = Invoice.objects.count()
        if inv_count == 0 or force_invoices:
            try:
                from board.management.commands.import_invoices_csv import Command as InvoicesCmd

                invoices = _path("INVOICES_CSV_PATH", "board/data/invoices.csv")
                if invoices.exists():
                    print(f"[BULK IMPORT] invoices -> {invoices}")
                    InvoicesCmd().handle(csv_path=str(invoices), dry_run=False, currency="CAD")
                else:
                    # If your file is named invoices_1.csv etc, set INVOICES_CSV_PATH to that.
                    print(f"[BULK IMPORT] SKIP: invoices file not found at {invoices}")
            except Exception as e:
                print(f"[BULK IMPORT] WARN: invoices import failed (non-fatal): {e}")
        else:
            print(f"[BULK IMPORT] SKIP: Invoices already exist (count={inv_count}).")

        print("[BULK IMPORT] DONE")

    finally:
        _release_lock()
