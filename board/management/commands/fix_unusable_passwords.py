from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import PBKDF2PasswordHasher
from django.utils.crypto import get_random_string

User = get_user_model()


class Command(BaseCommand):
    help = "Fix users with unusable passwords by setting a random usable password (so password reset works)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show how many users would be fixed without changing anything.")
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Stop after fixing this many users (0 = fix all). NOTE: limit applies to FIXED count, not scanned.",
        )
        parser.add_argument(
            "--iterations",
            type=int,
            default=0,
            help="PBKDF2 iterations to use for this command only (0 = Django default). Use e.g. 10000 for speed.",
        )
        parser.add_argument("--progress-every", type=int, default=50, help="Print progress every N fixed users.")

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        limit_fixed = int(options["limit"] or 0)
        iterations = int(options["iterations"] or 0)
        progress_every = int(options["progress_every"] or 50)

        qs = (
            User.objects.filter(is_active=True, is_staff=False, is_superuser=False)
            .exclude(email__isnull=True)
            .exclude(email__exact="")
            .order_by("id")
        )

        scanned = 0
        would_fix = 0
        fixed = 0

        # PBKDF2 (same algorithm Django understands). Optionally lower iterations for this one-off.
        hasher = PBKDF2PasswordHasher()
        if iterations > 0:
            hasher.iterations = iterations

        for u in qs.iterator(chunk_size=500):
            scanned += 1

            if u.has_usable_password():
                continue

            would_fix += 1
            if dry_run:
                continue

            raw = get_random_string(32)
            salt = hasher.salt()
            u.password = hasher.encode(raw, salt)
            u.save(update_fields=["password"])
            fixed += 1

            if progress_every > 0 and (fixed % progress_every == 0):
                self.stdout.write(f"Fixed {fixed} users so far... (scanned {scanned})")

            # IMPORTANT: limit applies to FIXED count, not scanned
            if limit_fixed > 0 and fixed >= limit_fixed:
                break

        if dry_run:
            self.stdout.write(f"DRY RUN: would fix {would_fix} (scanned {scanned}).")
        else:
            self.stdout.write(f"DONE: fixed {fixed} (scanned {scanned}).")
