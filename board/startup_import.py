import os

from django.conf import settings
from django.contrib.auth import get_user_model

from board.management.commands.import_employers_csv import Command as ImportEmployers
from board.management.commands.import_jobseekers_csv import Command as ImportJobSeekers
from board.management.commands.import_jobs_csv import Command as ImportJobs
from board.management.commands.import_invoices_csv import Command as ImportInvoices

from board.models import Employer, JobSeeker, Job, Invoice


def _env_bool(name: str, default: str = "0") -> bool:
    return (os.getenv(name, default) or "").strip().lower() in ("1", "true", "yes", "on")


def ensure_superuser():
    """
    Ensures a known superuser exists so you can get into /admin even after wipes.
    Controlled by env vars:
      DJANGO_SUPERUSER_EMAIL
      DJANGO_SUPERUSER_USERNAME
      DJANGO_SUPERUSER_PASSWORD
    """
    email = (os.getenv("DJANGO_SUPERUSER_EMAIL") or "").strip().lower()
    username = (os.getenv("DJANGO_SUPERUSER_USERNAME") or email).strip()
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD") or ""

    if not email or not password:
        return

    User = get_user_model()
    u = User.objects.filter(email__iexact=email).first()
    if not u:
        u = User.objects.create_superuser(username=username, email=email, password=password)
    else:
        # Ensure staff/superuser and password are correct
        changed = False
        if not u.is_staff:
            u.is_staff = True
            changed = True
        if not u.is_superuser:
            u.is_superuser = True
            changed = True
        if password:
            u.set_password(password)
            changed = True
        if changed:
            u.save()

    print(f"[startup_import] Ensured superuser login: {username} ({email})")


def wipe_business_data():
    """
    Wipes ONLY business data (not auth users, not migrations):
    Employer/JobSeeker/Job/Invoice (and related rows via cascade).
    """
    print("[startup_import] WIPE ENABLED: deleting business data...")

    Invoice.objects.all().delete()
    Job.objects.all().delete()
    JobSeeker.objects.all().delete()
    Employer.objects.all().delete()

    print("[startup_import] WIPE DONE.")


def run_bulk_import_if_enabled():
    """
    Run imports exactly when PTJOBS_STARTUP_IMPORT=1.
    After it succeeds, you MUST set PTJOBS_STARTUP_IMPORT=0 and redeploy
    so the app stops importing on every restart.
    """
    if not _env_bool("PTJOBS_STARTUP_IMPORT", "0"):
        return

    print("[startup_import] IMPORT ENABLED: starting bulk CSV imports.")

    base_dir = getattr(settings, "BASE_DIR", None)
    if not base_dir:
        print("[startup_import] ERROR: BASE_DIR not available.")
        return

    # CSV locations inside repo
    data_dir = os.path.join(str(base_dir), "board", "data")

    employers_csv = os.path.join(data_dir, "employers.csv")
    employers_deactivated_csv = os.path.join(data_dir, "employers_deactivated.csv")
    employers_pending_csv = os.path.join(data_dir, "employers_pending.csv")

    jobseekers_active_csv = os.path.join(data_dir, "jobseekers_active.csv")
    jobseekers_inactive_csv = os.path.join(data_dir, "jobseekers_inactive.csv")
    jobseekers_pending_csv = os.path.join(data_dir, "jobseekers_pending.csv")  # treat as inactive (cannot log in)

    jobs_active_csv = os.path.join(data_dir, "jobs_active.csv")
    jobs_expired_csv = os.path.join(data_dir, "jobs_expired.csv")

    invoices_csv = os.path.join(data_dir, "invoices.csv")

    # 1) Employers FIRST (active + deactivated + pending)
    print("[startup_import] Importing employers (active/deactivated/pending).")
    ImportEmployers().handle(
        employers_csv,
        employers_deactivated_csv,
        employers_pending_csv,
        dry_run=False,
    )

    # 2) Jobseekers (active + inactive + pending->inactive)
    print("[startup_import] Importing jobseekers (active/inactive/pending->inactive).")
    ImportJobSeekers().handle(
        jobseekers_active_csv,
        dry_run=False,
        mode="active",
    )
    ImportJobSeekers().handle(
        jobseekers_inactive_csv,
        dry_run=False,
        mode="inactive",
    )
    ImportJobSeekers().handle(
        jobseekers_pending_csv,
        dry_run=False,
        mode="inactive",
    )

    # 3) Jobs
    print("[startup_import] Importing jobs (active/expired).")
    ImportJobs().handle(
        jobs_active_csv,
        jobs_expired_csv,
        dry_run=False,
    )

    # 4) Invoices
    print("[startup_import] Importing invoices.")
    ImportInvoices().handle(
        invoices_csv,
        dry_run=False,
    )

    print("[startup_import] IMPORT DONE.")
