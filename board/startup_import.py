# board/startup_import.py
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
    """Call a management command via Django's call_command (no shell needed)."""
    from django.core.management import call_command
    call_command(command_name, *args)


def _wipe_prod_data_if_enabled() -> None:
    """
    Production wipe (NO shell needed):
      - Controlled by env var: RUN_BULK_WIPE_ON_STARTUP=1
      - Deletes imported business data + imported non-staff users so re-import is clean.

    What it DOES NOT delete:
      - SiteSettings / PostingPackage / PaymentGatewayConfig / DiscountCode
      - staff / superusers
    """
    if not _env_true("RUN_BULK_WIPE_ON_STARTUP"):
        return

    # Safety: don't wipe local dev unless explicitly allowed
    if getattr(settings, "DEBUG", False) and not _env_true("ALLOW_WIPE_IN_DEBUG"):
        _print("[startup_import] RUN_BULK_WIPE_ON_STARTUP set but DEBUG=True. Skipping wipe.")
        return

    _print("[startup_import] WIPE ENABLED: deleting business data before import...")

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

    # Delete non-staff imported users (because Employer/JobSeeker deletes do NOT delete User)
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


def run_bulk_import_if_enabled() -> None:
    """
    Runs bulk CSV imports inside the deployed container on web start.

    Turn ON in Railway just for one deploy:
      - RUN_BULK_WIPE_ON_STARTUP=1   (wipe old production data)
      - RUN_BULK_IMPORT_ON_STARTUP=1 (import CSVs + seed emails if empty)

    Note: also supports your existing Railway var name:
      - RUN_BULK_DATA_IMPORT_ON_STARTUP=1

    Then REMOVE the wipe/import vars after success.
    """
    if not (_env_true("RUN_BULK_IMPORT_ON_STARTUP") or _env_true("RUN_BULK_DATA_IMPORT_ON_STARTUP")):
        return

    # DB might not be ready on first boot
    try:
        from .models import Employer, Job, JobSeeker, Invoice, EmailTemplate
        Employer.objects.count()
    except (OperationalError, ProgrammingError):
        _print("[startup_import] DB not ready yet; skipping this boot.")
        return

    _wipe_prod_data_if_enabled()

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

    # 1) Employers
    if employers_csv.exists():
        _print("[startup_import] Importing employers...")
        _safe_call_management_command(
            "import_employers_csv",
            str(employers_csv),
            str(employers_deactivated_csv),
            str(employers_pending_csv),
        )
    else:
        _print(f"[startup_import] WARN: {employers_csv} not found; skipping employer import.")

    # Apply status updates
    try:
        _print("[startup_import] Updating employer status...")
        _safe_call_management_command(
            "update_employers_status_csv",
            str(employers_deactivated_csv),
            str(employers_pending_csv),
        )
    except Exception as e:
        _print(f"[startup_import] WARN: employer status update failed: {e}")

    # 2) Jobs (only if empty)
    if Job.objects.count() == 0:
        _print("[startup_import] Importing jobs...")
        _safe_call_management_command(
            "import_jobs_csv",
            str(jobs_active_csv),
            str(jobs_expired_csv),
        )
    else:
        _print("[startup_import] Jobs already exist; skipping job import.")

    # 3) Job seekers (only if empty) INCLUDING pending file
    if JobSeeker.objects.count() == 0:
        _print("[startup_import] Importing job seekers...")
        _safe_call_management_command(
            "import_jobseekers_csv",
            str(jobseekers_active_csv),
            str(jobseekers_inactive_csv),
            str(jobseekers_pending_csv),
        )
    else:
        _print("[startup_import] JobSeekers already exist; skipping jobseeker import.")

    # 4) Invoices (only if empty)
    if Invoice.objects.count() == 0:
        _print("[startup_import] Importing invoices...")
        _safe_call_management_command("import_invoices_csv", str(invoices_csv))
    else:
        _print("[startup_import] Invoices already exist; skipping invoice import.")

    # 5) Seed email templates if empty
    if EmailTemplate.objects.count() == 0:
        _print("[startup_import] Seeding email templates...")
        try:
            _safe_call_management_command("seed_email_templates")
        except Exception as e:
            _print(f"[startup_import] WARN: seed_email_templates failed: {e}")

    _print("[startup_import] Bulk import finished.")
