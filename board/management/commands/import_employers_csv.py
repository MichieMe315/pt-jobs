import csv
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from board.models import Employer  # adjust if your Employer model is elsewhere


class Command(BaseCommand):
    help = "Import Employers from a CSV export and create/link Django Users by email."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to employers.csv")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without writing to the DB",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        dry_run = options["dry_run"]

        User = get_user_model()
        created_users = 0
        created_employers = 0
        updated_employers = 0
        skipped = 0

        def norm(s):
            return (s or "").strip()

        def build_location(row):
            parts = []
            for key in ["Location", "City", "State", "Country", "Zip Code"]:
                val = norm(row.get(key))
                if val and val not in parts:
                    parts.append(val)
            return ", ".join(parts)

        # Figure out whether your User model uses email as login field
        username_field = getattr(User, "USERNAME_FIELD", "username")

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            # One transaction keeps things consistent
            with transaction.atomic():
                for row in reader:
                    email = norm(row.get("Employer Email")).lower()
                    if not email:
                        skipped += 1
                        continue

                    full_name = norm(row.get("Full Name"))
                    company_name = norm(row.get("Company Name"))
                    phone = norm(row.get("Employer Phone"))
                    website = norm(row.get("Employer Website"))
                    company_description = row.get("Company Description") or ""
                    location = build_location(row)

                    status = norm(row.get("Status")).lower()
                    is_active = (status == "active")

                    # ---- Create or fetch User by email ----
                    user = User.objects.filter(email__iexact=email).first()
                    user_created = False

                    if not user:
                        user_kwargs = {"email": email}

                        # If username_field isn't "email", we must populate it.
                        # Common case: username_field == "username"
                        if username_field != "email":
                            # Try to set username to email (works for most setups)
                            user_kwargs[username_field] = email

                        user = User(**user_kwargs)

                        # Optional name fields if your user model has them
                        if hasattr(user, "first_name") or hasattr(user, "last_name"):
                            # best-effort split
                            parts = full_name.split()
                            if hasattr(user, "first_name") and parts:
                                user.first_name = parts[0][:150]
                            if hasattr(user, "last_name") and len(parts) > 1:
                                user.last_name = " ".join(parts[1:])[:150]

                        # IMPORTANT: force password reset flow later
                        user.set_unusable_password()

                        if dry_run:
                            user_created = True
                        else:
                            user.save()
                            user_created = True
                            created_users += 1

                    # ---- Create or update Employer ----
                    employer = Employer.objects.filter(email__iexact=email).first()

                    if not employer:
                        employer = Employer(email=email)
                        creating = True
                    else:
                        creating = False

                    # Link to user
                    employer.user = user

                    # Map fields (adjust if your Employer uses different names)
                    if hasattr(employer, "name"):
                        employer.name = full_name
                    if hasattr(employer, "company_name"):
                        employer.company_name = company_name
                    if hasattr(employer, "company_description"):
                        employer.company_description = company_description
                    if hasattr(employer, "phone"):
                        employer.phone = phone
                    if hasattr(employer, "website"):
                        employer.website = website
                    if hasattr(employer, "location"):
                        employer.location = location

                    # Approval + login flags
                    if hasattr(employer, "is_approved"):
                        employer.is_approved = is_active
                    if hasattr(employer, "login_active"):
                        employer.login_active = is_active

                    # Credits: default to 0 if field exists and empty
                    if hasattr(employer, "credits") and (employer.credits is None):
                        employer.credits = 0

                    # Dates (Registration Date)
                    reg_date = norm(row.get("Registration Date"))
                    # If your fields are DateTimeFields, you can leave them alone and let defaults handle it,
                    # or parse reg_date properly. We'll only set approved_at if present.
                    if hasattr(employer, "approved_at") and is_active and not getattr(employer, "approved_at", None):
                        employer.approved_at = timezone.now()

                    # LOGO NOTE:
                    # If employer.logo is an ImageField, URLs from CSV won't import directly.
                    # We leave logo untouched here to avoid breaking the import.

                    if dry_run:
                        action = "CREATE" if creating else "UPDATE"
                        self.stdout.write(f"[DRY RUN] {action} employer for {email} (user_created={user_created})")
                    else:
                        employer.save()
                        if creating:
                            created_employers += 1
                        else:
                            updated_employers += 1

                if dry_run:
                    # rollback everything in dry-run
                    raise transaction.TransactionManagementError("Dry run complete (rolled back).")

        self.stdout.write(self.style.SUCCESS("Done."))
        self.stdout.write(f"Users created: {created_users}")
        self.stdout.write(f"Employers created: {created_employers}")
        self.stdout.write(f"Employers updated: {updated_employers}")
        self.stdout.write(f"Rows skipped (missing email): {skipped}")
