import secrets
import string
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.text import slugify
from board.models import Employer, JobSeeker


def random_password(length: int = 12) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


def unique_username(base: str) -> str:
    base_slug = slugify(base) or "user"
    username = base_slug
    i = 1
    while User.objects.filter(username=username).exists():
        i += 1
        username = f"{base_slug}{i}"
    return username


class Command(BaseCommand):
    help = (
        "Create auth.User accounts for Employer/JobSeeker rows missing 'user' and link them. "
        "Users are created with is_active=False for admin approval."
    )

    def handle(self, *args, **options):
        created_users = 0

        # ---- Employers without user ----
        for emp in Employer.objects.filter(user__isnull=True):
            base = emp.name if emp.name else "employer"
            username = unique_username(base)
            user = User.objects.create_user(
                username=username,
                email="",
                password=random_password(),
                is_active=False,  # pending admin approval
            )
            emp.user = user
            emp.save(update_fields=["user"])
            created_users += 1
            self.stdout.write(
                self.style.SUCCESS(f"Linked Employer '{emp.name}' to User '{username}'")
            )

        # ---- JobSeekers without user ----
        for js in JobSeeker.objects.filter(user__isnull=True):
            if js.first_name or js.last_name:
                base = f"{js.first_name}-{js.last_name}"
            elif js.email:
                base = js.email.split("@")[0]
            else:
                base = "jobseeker"
            username = unique_username(base)
            user = User.objects.create_user(
                username=username,
                email=js.email or "",
                password=random_password(),
                is_active=False,  # pending admin approval
            )
            js.user = user
            js.save(update_fields=["user"])
            created_users += 1
            self.stdout.write(
                self.style.SUCCESS(f"Linked JobSeeker '{js}' to User '{username}'")
            )

        if created_users == 0:
            self.stdout.write(self.style.WARNING("No profiles needed backfilling."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Backfill complete. Created {created_users} users."))
