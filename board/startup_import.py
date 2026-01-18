from __future__ import annotations

import os
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, transaction


LOCK_KEY = 923487234  # arbitrary constant for advisory lock


def _env_true(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


def _should_skip_for_command_context() -> bool:
    """
    Avoid running imports during deploy steps that call Django:
    - migrate
    - collectstatic
    - any management command
    """
    argv = " ".join(sys.argv).lower()
    if "manage.py" in argv:
        # If ANY explicit management command is running, skip.
        # (Railway runs migrate/collectstatic in predeploy.)
        if any(cmd in argv for cmd in ["migrate", "collectstatic", "createsuperuser", "shell", "loaddata"]):
            return True
        # If it is a management command at all, safest to skip:
        if len(sys.argv) > 1:
            return True
    return False


def _try_advisory_lock() -> bool:
    """
    Prevent the import from running multiple times (e.g., multiple gunicorn workers).
    Works on Postgres. On SQLite, just runs once per process.
    """
    try:
        if connection.vendor == "postgresql":
            with connection.cursor() as cur:
                cur.execute("SELECT pg_try_advisory_lock(%s);", [LOCK_KEY])
                row = cur.fetchone()
                return bool(row and row[0])
    except Exception:
        return True
    return True


def _release_advisory_lock() -> None:
    try:
        if connection.vendor == "postgresql":
            with connection.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s);", [LOCK_KEY])
    except Exception:
        return


def _log(msg: str) -> None:
    print(f"[startup_import] {msg}", flush=True)


def _ensure_superuser_from_env() -> None:
    """
    Optional: ensure an admin exists if env is provided.
    Uses:
      DJANGO_SUPERUSER_USERNAME (or email if not provided)
      DJANGO_SUPERUSER_EMAIL
      DJANGO_SUPERUSER_PASSWORD
    """
    username = (os.getenv("DJANGO_SUPERUSER_USERNAME") or "").strip()
    email = (os.getenv("DJANGO_SUPERUSER_EMAIL") or "").strip()
    password = (os.getenv("DJANGO_SUPERUSER_PASSWORD") or "").strip()

    if not email or not password:
        return

    if not username:
        username = email

    User = get_user_model()
    try:
        u = User.objects.filter(username=username).first() or User.objects.filter(email=email).first()
        if not u:
            u = User.objects.create_superuser(username=username, email=email, password=password)
            _log(f"Ensured superuser login: {u.username} ({u.email}) [CREATED]")
        else:
            # Ensure staff/superuser flags are correct, and reset password (optional but useful)
            changed = False
            if not u.is_staff:
                u.is_staff = True
                changed = True
            if not u.is_superuser:
                u.is_superuser = True
                changed = True
            if changed:
                u.save(update_fields=["is_staff", "is_superuser"])
            # If you want to force the password to match the env:
            u.set_password(password)
            u.save(update_fields=["password"])
            _log(f"Ensured superuser login: {u.username} ({u.email})")
    except Exception:
        return


def _wipe_business_data() -> None:
    """
    Deletes only business data from board app.
    Does NOT delete superusers/staff users.
    """
    from board.models import (
        Application,
        DiscountCode,
        EmailTemplate,
        Employer,
        Invoice,
        Job,
        JobSeeker,
        PostingPackage,
        PurchasedPackage,
        Resume,
        SiteSettings,
    )

    _log("WIPE ENABLED: deleting business data...")

    # Order matters due to FK constraints
    with transaction.atomic():
        Application.objects.all().delete()
        Resume.objects.all().delete()
        Job.objects.all().delete()
        Invoice.objects.all().delete()
        PurchasedPackage.objects.all().delete()
        PostingPackage.objects.all().delete()
        DiscountCode.objects.all().delete()

        # Keep SiteSettings + EmailTemplate if you want, but you can wipe too.
        # If you do NOT want them wiped, comment these out.
        EmailTemplate.objects.all().delete()
        SiteSettings.objects.all().delete()

        JobSeeker.objects.all().delete()
        Employer.objects.all().delete()

    _log("WIPE DONE.")


def _data_dir() -> Path:
    base = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent))
    return base / "board" / "data"


def run_startup_tasks_if_enabled() -> None:
    """
    Entry point called from apps.py ready().
    """
    if _should_skip_for_command_context():
        return

    # Always allow ensuring a superuser if env provided
    _ensure_superuser_from_env()

    do_wipe = _env_true("RUN_STARTUP_WIPE", "0")
    do_import = _env_true("RUN_STARTUP_IMPORT", "0")

    if not do_wipe and not do_import:
        return

    if not _try_advisory_lock():
        _log("Another worker/process holds the startup lock. Skipping.")
        return

    try:
        if do_wipe:
            _wipe_business_data()

        if do_import:
            d = _data_dir()

            employers_csv = d / "employers.csv"
            employers_deactivated_csv = d / "employers_deactivated.csv"
            employers_pending_csv = d / "employers_pending.csv"

            jobseekers_active_csv = d / "jobseekers_active.csv"
            jobseekers_inactive_csv = d / "jobseekers_inactive.csv"
            jobseekers_pending_csv = d / "jobseekers_pending.csv"

            jobs_active_csv = d / "jobs_active.csv"
            jobs_expired_csv = d / "jobs_expired.csv"

            invoices_csv = d / "invoices.csv"

            _log("IMPORT ENABLED: starting bulk CSV imports.")

            _log("Importing employers.")
            call_command("import_employers_csv", str(employers_csv))
            call_command("import_employers_csv", str(employers_deactivated_csv))
            call_command("import_employers_csv", str(employers_pending_csv))

            _log("Importing jobseekers (active/inactive/pending).")
            call_command("import_jobseekers_csv", str(jobseekers_active_csv))
            call_command("import_jobseekers_csv", str(jobseekers_inactive_csv))
            # Contract: you said pending should import as inactive so they cannot log in
            call_command("import_jobseekers_csv", str(jobseekers_pending_csv))

            _log("Importing jobs (active/expired).")
            call_command("import_jobs_csv", str(jobs_active_csv), str(jobs_expired_csv))

            _log("Importing invoices.")
            call_command("import_invoices_csv", str(invoices_csv))

            _log("IMPORT DONE.")
    finally:
        _release_advisory_lock()
