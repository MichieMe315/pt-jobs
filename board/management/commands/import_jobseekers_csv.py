import csv
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from board.models import JobSeeker

User = get_user_model()


def norm(val):
    return (val or "").strip()


def truncate(val, max_len):
    v = norm(val)
    return v[:max_len] if (max_len and isinstance(max_len, int)) else v


# Flexible header keys
EMAIL_KEYS = ["email", "Email", "Job Seeker Email", "jobseeker_email", "JobSeekerEmail"]
FIRST_NAME_KEYS = ["first_name", "First Name", "firstname", "FirstName"]
LAST_NAME_KEYS = ["last_name", "Last Name", "lastname", "LastName"]
POSITION_KEYS = ["position_desired", "Position Desired", "Desired Position", "position"]
OPPORTUNITY_KEYS = ["opportunity_type", "Opportunity Type", "Type", "opportunity"]
LOCATION_KEYS = ["current_location", "Current Location", "Location", "location"]
RELOCATE_WHERE_KEYS = ["relocate_where", "Relocate Where", "Relocation Where", "relocate"]


def pick(row, keys):
    for k in keys:
        if k in row and norm(row.get(k)):
            return norm(row.get(k))
    return ""


def _mode_from_filename(filename: str) -> str:
    """
    Auto-detect jobseeker status from file name.
    - *pending* => inactive (new site: pending should NOT be active)
    - *inactive* / *deactivated* => inactive
    - default => active
    """
    name = (filename or "").lower()
    if "pending" in name:
        return "inactive"
    if "inactive" in name or "deactivated" in name:
        return "inactive"
    if "active" in name:
        return "active"
    return "active"


class Command(BaseCommand):
    help = "Import JobSeekers from one or more CSVs. Pending treated as inactive."

    def add_arguments(self, parser):
        parser.add_argument("csv_paths", nargs="+", type=str)
        parser.add_argument(
            "--mode",
            choices=["active", "inactive"],
            default=None,
            help="Force a single mode for all files (otherwise auto-detected from filename).",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        csv_paths = opts["csv_paths"]
        forced_mode = opts["mode"]
        dry_run = opts["dry_run"]

        users_created = 0
        users_updated = 0
        users_existing = 0
        js_created = 0
        js_updated = 0
        skipped = 0
        errors = 0

        def _abs_path(p: str) -> Path:
            pp = Path(p)
            if not pp.is_absolute():
                pp = Path(settings.BASE_DIR) / pp
            return pp

        with transaction.atomic():
            for raw_path in csv_paths:
                path = _abs_path(raw_path)
                if not path.exists():
                    raise FileNotFoundError(f"CSV not found: {path}")

                mode = forced_mode or _mode_from_filename(path.name)
                is_approved = mode == "active"
                login_active = mode == "active"

                self.stdout.write(
                    self.style.WARNING(
                        f"\n--- Importing: {path.name} | mode={mode} "
                        f"(is_approved={is_approved}, login_active={login_active}) ---"
                    )
                )

                with path.open(newline="", encoding="utf-8-sig") as f:
                    reader = csv.DictReader(f)

                    for idx, row in enumerate(reader, start=2):
                        try:
                            email = pick(row, EMAIL_KEYS).lower()
                            if not email:
                                skipped += 1
                                continue

                            # DRY RUN: do NOT write anything (no get_or_create), just count
                            if dry_run:
                                user_exists = User.objects.filter(email=email).exists()
                                js_exists = JobSeeker.objects.filter(email=email).exists()

                                if user_exists:
                                    users_existing += 1
                                else:
                                    users_created += 1  # would create

                                if js_exists:
                                    js_updated += 1  # would update
                                else:
                                    js_created += 1  # would create

                                continue

                            # REAL RUN: create/update user
                            user = User.objects.filter(email=email).first()
                            if not user:
                                user = User.objects.create_user(
                                    username=email,
                                    email=email,
                                    password=None,
                                    is_active=login_active,
                                )
                                users_created += 1
                            else:
                                users_existing += 1
                                if user.is_active != login_active:
                                    user.is_active = login_active
                                    user.save(update_fields=["is_active"])
                                    users_updated += 1

                            # REAL RUN: create/update jobseeker (user_id must never be null)
                            js, created = JobSeeker.objects.get_or_create(
                                email=email,
                                defaults={"user": user},
                            )

                            if js.user_id != user.id:
                                js.user = user

                            js.first_name = truncate(pick(row, FIRST_NAME_KEYS), 80)
                            js.last_name = truncate(pick(row, LAST_NAME_KEYS), 80)
                            js.position_desired = truncate(pick(row, POSITION_KEYS), 200)
                            js.opportunity_type = truncate(pick(row, OPPORTUNITY_KEYS), 30)
                            js.current_location = truncate(pick(row, LOCATION_KEYS), 200)
                            js.relocate_where = truncate(pick(row, RELOCATE_WHERE_KEYS), 200)

                            js.is_approved = is_approved
                            js.login_active = login_active
                            js.approved_at = timezone.now() if is_approved else None

                            js.save()

                            if created:
                                js_created += 1
                            else:
                                js_updated += 1

                        except Exception as e:
                            errors += 1
                            self.stderr.write(f"[Row {idx}] ERROR: {e}")

            # Dry-run rollback safety (no writes should have happened anyway)
            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                "\nDONE\n"
                f"Users would be created: {users_created}\n"
                f"Users existing: {users_existing}\n"
                f"Users would be updated: {users_updated}\n"
                f"JobSeekers would be created: {js_created}\n"
                f"JobSeekers would be updated: {js_updated}\n"
                f"Rows skipped (missing email): {skipped}\n"
                f"Errors: {errors}\n"
            )
        )
