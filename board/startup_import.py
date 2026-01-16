import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import OperationalError, ProgrammingError


def _env_true(name: str) -> bool:
    return (os.environ.get(name, "") or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _print(msg: str) -> None:
    try:
        print(msg, flush=True)
    except Exception:
        pass


def _safe_call_management_command(command_name: str, *args: str) -> None:
    from django.core.management import call_command
    call_command(command_name, *args)


def ensure_superuser_if_enabled() -> None:
    if not _env_true("ENSURE_SUPERUSER_ON_STARTUP"):
        return

    username = (os.environ.get("DJANGO_SUPERUSER_USERNAME") or "").strip()
    email = (os.environ.get("DJANGO_SUPERUSER_EMAIL") or "").strip()
    password = (os.environ.get("DJANGO_SUPERUSER_PASSWORD") or "").strip()

    if not username or not email or not password:
        _print("[startup_import] ENSURE_SUPERUSER_ON_STARTUP=1 but missing DJANGO_SUPERUSER_* vars. Skipping.")
        return

    User = get_user_model()

    user = User.objects.filter(username=username).first()
    if user is None:
        user = User.objects.filter(email__iexact=email).first()

    if user is None:
        user = User.objects.create_user(username=username, email=email)
        _print(f"[startup_import] Created base user: {username} ({email})")

    user.email = email
    user.is_staff = True
    user.is_superuser = True
    user.set_password(password)
    user.save()

    _print(f"[startup_import] Ensured superuser login: {username} ({email})")


def wipe_prod_data_if_enabled() -> None:
    if not _env_true("RUN_BULK_WIPE_ON_STARTUP"):
        return

    # Safety: don’t wipe local dev unless explicitly allowed
    if getattr(settings, "DEBUG", False) and not _env_true("ALLOW_WIPE_IN_DEBUG"):
        _print("[startup_import] RUN_BULK_WIPE_ON_STARTUP set but DEBUG=True. Skipping wipe.")
        return

    _print("[startup_import] WIPE ENABLED: deleting business data...")

    from .models import (
        Application,
        Resume,
        JobAlert,
        Job,
        Invoice,
        PurchasedPackage,
        JobSeeker,
        Employer,
    )

    # Delete in dependency order
    for model in (Application, Resume, JobAlert, Job, Invoice, PurchasedPackage, JobSeeker, Employer):
        try:
            model.objects.all().delete()
        except Exception:
            pass

    # Remove imported non-staff users linked to Employer/JobSeeker
    User = get_user_model()
    try:
        User.objects.filter(is_staff=False, is_superuser=False, employer__isnull=False).delete()
    except Exception:
        pass
    try:
        User.objects.filter(is_staff=False, is_superuser=False, jobseeker__isnull=False).delete()
    except Exception:
        pass

    _print("[startup_import] WIPE DONE.")


def run_bulk_import_if_enabled() -> None:
    if not (_env_true("RUN_BULK_IMPORT_ON_STARTUP") or _env_true("RUN_BULK_DATA_IMPORT_ON_STARTUP")):
        return

    # DB might not be ready on first boot
    try:
        from .models import Employer
        Employer.objects.count()
    except (OperationalError, ProgrammingError):
        _print("[startup_import] DB not ready yet; skipping this boot.")
        return

    base_dir = Path(settings.BASE_DIR)

    employers_csv = base_dir / "board" / "data" / "employers.csv"
    employers_deactivated_csv = base_dir / "board" / "data" / "employers_deactivated.csv"
    employers_pending_csv = base_dir / "board" / "data" / "employers_pending.csv"

    jobs_active_csv = base_dir / "board" / "data" / "jobs_active.csv"
    jobs_expired_csv = base_dir / "board" / "data" / "jobs_expired.csv"

    jobseekers_active_csv = base_dir / "board" / "data" / "jobseekers_active.csv"
    jobseekers_inactive_csv = base_dir / "board" / "data" / "jobseekers_inactive.csv"
    jobseekers_pending_csv = base_dir / "board" / "data" / "jobseekers_pending.csv"

    invoices_csv = base_dir / "board" / "data" / "invoices.csv"

    _print("[startup_import] Importing employers...")
    _safe_call_management_command(
        "import_employers_csv",
        str(employers_csv),
        str(employers_deactivated_csv),
        str(employers_pending_csv),
    )

    try:
        _print("[startup_import] Updating employer status...")
        _safe_call_management_command(
            "update_employers_status_csv",
            str(employers_deactivated_csv),
            str(employers_pending_csv),
        )
    except Exception as e:
        _print(f"[startup_import] WARN: employer status update failed: {e}")

    _print("[startup_import] Importing jobs...")
    _safe_call_management_command("import_jobs_csv", str(jobs_active_csv), str(jobs_expired_csv))

    _print("[startup_import] Importing jobseekers...")
    _safe_call_management_command(
        "import_jobseekers_csv",
        str(jobseekers_active_csv),
        str(jobseekers_inactive_csv),
        str(jobseekers_pending_csv),
    )

    _print("[startup_import] Importing invoices...")
    _safe_call_management_command("import_invoices_csv", str(invoices_csv))

    _print("[startup_import] Bulk import finished.")


def startup_tasks() -> None:
    """
    Runs on app startup (called from apps.py):
      1) Ensure superuser (if enabled)
      2) Wipe business data (if enabled)
      3) Import (ONLY if import flag enabled)
    """
    # DB readiness check
    try:
        from .models import SiteSettings
        SiteSettings.objects.first()
    except (OperationalError, ProgrammingError):
        _print("[startup_import] DB not ready yet; skipping this boot.")
        return

    ensure_superuser_if_enabled()
    wipe_prod_data_if_enabled()
    run_bulk_import_if_enabled()
