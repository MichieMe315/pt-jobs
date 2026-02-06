from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string


class Command(BaseCommand):
    help = "Set random usable passwords for active non-staff users with unusable passwords."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        limit = int(opts["limit"] or 0)

        User = get_user_model()
        qs = User.objects.filter(is_active=True, is_staff=False, is_superuser=False).only("id", "password")

        fixed = 0
        scanned = 0

        for u in qs.iterator(chunk_size=500):
            scanned += 1
            if not u.has_usable_password():
                if not dry:
                    u.set_password(get_random_string(32))
                    u.save(update_fields=["password"])
                fixed += 1

                if limit and fixed >= limit:
                    break

        if dry:
            self.stdout.write(self.style.SUCCESS(f"DRY RUN: would fix {fixed} (scanned {scanned})."))
        else:
            self.stdout.write(self.style.SUCCESS(f"FIXED: {fixed} (scanned {scanned})."))
