# board/startup_import.py
from __future__ import annotations

import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection


User = get_user_model()


def _env_bool(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


def _log(msg: str) -> None:
    print(f"[startup_import] {msg}", flush=True)


def ensure_admin_login() -> None:
    """
    Ensures a known superuser exists in production without breaking existing staff accounts.
    Uses env vars:
      DJANGO_SUPERUSER_USERNAME
      DJANGO_SUPERUSER_EMAIL
      DJANGO_SUPERUSER_PASSWORD
    """
    username = (os.getenv("DJANGO_SUPERUSER_USERNAME") or "").strip()
    email = (os.getenv("DJANGO_SUPERUSER_EMAIL") or "").strip().lower()
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD") or ""

    if not username or not email or not password:
        return

    # Prefer username match, else email match
    user = User.objects.filter(username=username).first() or User.objects.filter(email=email).first()
    if not user:
        user = User.objects.create_superuser(username=username, email=email, password=password)
        _log(f"Ensured superuser login: {username} ({email})")
        return

    # Make sure it's staff/superuser (do not reset passwords unless explicitly requested)
    changed = False
    if not user.is_staff:
        user.is_staff = True
        changed = True
    if not user.is_superuser:
        user.is_superuser = True
        changed = True
    if user.email != email:
        user.email = email
        changed = True
    if changed:
        user.save()
    _log(f"Ensured superuser login: {user.username} ({user.email})")


def wipe_business_data() -> None:
    """
    Deletes business rows but keeps auth + admin accounts.
    Controlled by BULK_WIPE_ENABLED=1.
    """
    from board.models import Employer, JobSeeker, Job, Application, Resume, Invoice, PurchasedPackage, DiscountCode, EmailTemplate

    _log("WIPE ENABLED: deleting business data...")

    # Order matters due to FK constraints
    Application.objects.all().delete()
    Resume.objects.all().delete()
    Job.objects.all().delete()
    Invoice.objects.all().delete()
    PurchasedPackage.objects.all().delete()
    DiscountCode.objects.all().delete()
    EmailTemplate.objects.all().delete()
    JobSeeker.objects.all().delete()
    Employer.objects.all().delete()

    _log("WIPE DONE.")


def run_bulk_import_if_enabled() -> None:
    """
    Runs imports ONLY if BULK_IMPORT_ENABLED=1.
    Expects CSVs in repo under board/data by default.
    """
    if not _env_bool("BULK_IMPORT_ENABLED", "0"):
        return

    base = Path(os.getenv("BULK_IMPORT_BASE", "board/data"))

    employers_csv = base / "employers.csv"
    employers_deactivated_csv = base / "employers_deactivated.csv"
    employers_pending_csv = base / "employers_pending.csv"

    jobseekers_active_csv = base / "jobseekers_active.csv"
    jobseekers_inactive_csv = base / "jobseekers_inactive.csv"
    jobseekers_pending_csv = base / "jobseekers_pending.csv"

    jobs_active_csv = base / "jobs_active.csv"
    jobs_expired_csv = base / "jobs_expired.csv"

    invoices_csv = base / "invoices.csv"

    _log("IMPORT ENABLED: starting bulk CSV imports.")

    # Employers
    _log("Importing employers.")
    call_command("import_employers_csv", str(employers_csv), "--status=active")
    call_command("import_employers_csv", str(employers_deactivated_csv), "--status=inactive")
    call_command("import_employers_csv", str(employers_pending_csv), "--status=pending")

    # Jobseekers
    _log("Importing jobseekers (active/inactive/pending).")
    call_command("import_jobseekers_csv", str(jobseekers_active_csv), "--mode=active")
    call_command("import_jobseekers_csv", str(jobseekers_inactive_csv), "--mode=inactive")
    # Contract decision: pending -> inactive/login blocked
    call_command("import_jobseekers_csv", str(jobseekers_pending_csv), "--mode=inactive")

    # Jobs
    _log("Importing jobs (active/expired).")
    call_command("import_jobs_csv", str(jobs_active_csv), str(jobs_expired_csv))

    # Invoices
    _log("Importing invoices.")
    call_command("import_invoices_csv", str(invoices_csv))

    _log("IMPORT DONE.")


def safe_startup_tasks() -> None:
    """
    This is called by AppConfig.ready().
    It must NEVER crash the worker.
    """
    try:
        # Touch DB to ensure connection is ready (prevents weird first-query issues)
        with connection.cursor() as cur:
            cur.execute("SELECT 1;")
    except Exception:
        # If DB isn't ready, don't do anything on this boot.
        return

    try:
        ensure_admin_login()
    except Exception as e:
        _log(f"ensure_admin_login failed: {e}")

    try:
        if _env_bool("BULK_WIPE_ENABLED", "0"):
            wipe_business_data()
    except Exception as e:
        _log(f"wipe failed: {e}")

    try:
        run_bulk_import_if_enabled()
    except Exception as e:
        # IMPORTANT: never crash boot
        _log(f"bulk import failed: {e}")
