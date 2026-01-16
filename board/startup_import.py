# board/startup_import.py
import os
import sys
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


def _blocked_by_command() -> bool:
    # Don't run these during management commands like migrate/collectstatic
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
    return any(cmd in sys.argv for cmd in blocked)


def _db_ready() -> bool:
    try:
        # Lightweight check that DB is up and tables exist
        from .models import Employer  # noqa: F401

        Employer.objects.count()
        return True
    except (OperationalError, ProgrammingError):
        return False
    except Exception:
        # If anything weird happens, treat as not ready
        return False


def ensure_superuser_if_enabled() -> None:
    """
    Ensures a known admin user exists (no shell needed).
    Enable ONLY when you need it:
      - RUN_ENSURE_SUPERUSER_ON_STARTUP=1

    Required:
      - DJANGO_SUPERUSER_PASSWORD

    Optional:
      - DJANGO_SUPERUSER_USERNAME (default: siteadmin)
      - DJANGO_SUPERUSER_EMAIL (default: cheekythreadz@protonmail.com)
      - DJANGO_SUPERUSER_FORCE_PASSWORD=1 (force reset password every boot while enabled)
    """
    if not _env_true("RUN_ENSURE_SUPERUSER_ON_STARTUP"):
        return

    if _blocked_by_command():
        return

    if not _db_ready():
        _print("[startup_import] DB not ready yet; skipping ensure_superuser this boot.")
        return

    username = (os.environ.get("DJANGO_SUPERUSER_USERNAME") or "siteadmin").strip()
    email = (os.environ.get("DJANGO_SUPERUSER_EMAIL") or "cheekythreadz@protonmail.com").strip()
    password = (os.environ.get("DJANGO_SUPERUSER_PASSWORD") or "").strip()
    force_pw = _env_true("DJANGO_SUPERUSER_FORCE_PASSWORD")

    if not password:
        _print("[startup_import] RUN_ENSURE_SUPERUSER_ON_STARTUP set but DJANGO_SUPERUSER_PASSWORD is missing. Skipping.")
        return

    User = get_user_model()
    user, created = User.objects.get_or_create(username=username, defaults={"email": email})
    # Make sure it's staff/superuser
    changed = False
    if getattr(user, "email", "") != email:
        user.email = email
        changed = True
    if not user.is_staff:
        user.is_staff = True
        changed = True
    if not user.is_superuser:
        user.is_superuser = True
        changed = True

    if created or force_pw:
        user.set_password(password)
        changed = True

    if changed:
        user.save()

    _print(f"[startup_import] Ensured superuser login: {username} ({email})")


def _wipe_prod_data() -> None:
    from .models import (
        Application,
        Resume,
        Job,
        JobAlert,
        PurchasedPackage,
        Invoice,
        Employer,
        JobSeeker,
    )

    deleted = {}

    # Delete in dependency order
    for model in (Application, Resume, JobAlert, Job, Invoice, PurchasedPackage, JobSeeker, Employer):
        try:
            deleted[model.__name__] = model.objects.all().delete()[0]
        except Exception:
            deleted[model.__name__] = 0

    # Optional model(s)
    try:
        from .models import SavedJob  # type: ignore

        deleted["SavedJob"] = SavedJob.objects.all().delete()[0]
    except Exception:
        pass

    # Delete non-staff imported users (Employer/JobSeeker deletes do NOT delete User)
    User = get_user_model()
    users_deleted = 0
    try:
        users_deleted += User.objects.filter(is_staff=False, is_superuser=False, employer__isnull=False).delete()[0]
    except Exception:
        pass
    try:
        users_deleted += User.objects.filter(is_staff=False, is_superuser=False, jobseeker__isnull=False).delete()[0]
    except Exception:
        pass

    _print(
        "[startup_import] WIPE DONE: "
        + ", ".join([f"{k}={v}" for k, v in deleted.items()])
        + f", Users={users_deleted}"
    )


def run_wipe_if_enabled() -> None:
    """
    Production wipe (NO shell needed):
      - Controlled by env var: RUN_BULK_WIPE_ON_STARTUP=1

    What it DOES NOT delete:
      - SiteSettings / PostingPackage / PaymentGatewayConfig / DiscountCode
      - staff / superusers
    """
    if not _env_true("RUN_BULK_WIPE_ON_STARTUP"):
        return

    if _blocked_by_command():
        return

    # Safety: don't wipe local dev unless explicitly allowed
    if getattr(settings, "DEBUG", False) and not _env_true("ALLOW_WIPE_IN_DEBUG"):
        _print("[startup_import] RUN_BULK_WIPE_ON_STARTUP set but DEBUG=True. Skipping wipe.")
        return

    if not _db_ready():
        _print("[startup_import] DB not ready yet; skipping wipe this boot.")
        return

    marker = Path("/tmp/ptjobs_wipe_done")
    if marker.exists():
        _print("[startup_import] WIPE already completed for this container; skipping.")
        return

    _print("[startup_import] WIPE ENABLED: deleting business data before import.")
    _wipe_prod_data()
    try:
        marker.write_text("done")
    except Exception:
        pass


def _safe_call_management_command(command_name: str, *args: str) -> None:
    from django.core.management import call_command

    call_command(command_name, *args)


def run_bulk_import_if_enabled() -> None:
    """
    Runs bulk CSV imports inside the deployed container.
    Turn ON in Railway just for one deploy:
      - RUN_BULK_IMPORT_ON_STARTUP=1   (imports CSVs)
    Also supports:
      - RUN_BULK_DATA_IMPORT_ON_STARTUP=1

    Note: wipe is separate now (RUN_BULK_WIPE_ON_STARTUP).
    """
    if not (_env_true("RUN_BULK_IMPORT_ON_STARTUP") or _env_true("RUN_BULK_DATA_IMPORT_ON_STARTUP")):
        return

    if _blocked_by_command():
        return

    if not _db_ready():
        _print("[startup_import] DB not ready yet; skipping import this boot.")
        return

    marker = Path("/tmp/ptjobs_import_done")
    if marker.exists():
        _print("[startup_import] IMPORT already completed for this container; skipping.")
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

    _print("[startup_import] IMPORT ENABLED: starting bulk CSV imports.")

    # 1) Employers
    if employers_csv.exists():
        _print("[startup_import] Importing employers.")
        _safe_call_management_command(
            "import_employers_csv",
            str(employers_csv),
            str(employers_deactivated_csv),
            str(employers_pending_csv),
        )

    # 2) JobSeekers (includes pending)
    if jobseekers_active_csv.exists() or jobseekers_inactive_csv.exists() or jobseekers_pending_csv.exists():
        _print("[startup_import] Importing jobseekers (active/inactive/pending).")
        _safe_call_management_command(
            "import_jobseekers_csv",
            str(jobseekers_active_csv),
            str(jobseekers_inactive_csv),
            str(jobseekers_pending_csv),
        )

    # 3) Jobs
    if jobs_active_csv.exists() or jobs_expired_csv.exists():
        _print("[startup_import] Importing jobs (active/expired).")
        _safe_call_management_command("import_jobs_csv", str(jobs_active_csv), str(jobs_expired_csv))

    # 4) Invoices
    if invoices_csv.exists():
        _print("[startup_import] Importing invoices.")
        _safe_call_management_command("import_invoices_csv", str(invoices_csv))

    try:
        marker.write_text("done")
    except Exception:
        pass

    _print("[startup_import] IMPORT DONE.")
