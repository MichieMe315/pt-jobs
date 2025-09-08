from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from board.models import PostingPackage, Employer, Job, JobSeeker
from datetime import date, timedelta


class Command(BaseCommand):
    help = "Seed the database with test data (packages, employer, job, jobseeker)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Seeding test data…"))

        # --- Posting Packages ---
        PostingPackage.objects.all().delete()
        pkg1 = PostingPackage.objects.create(
            code="basic-30",
            name="Basic 30-day Posting",
            description="1 job posting, active for 30 days.",
            price_cents=5000,
            duration_days=30,
            max_jobs=1,
            is_featured_package=False,
            is_active=True,
            order=1,
        )
        pkg2 = PostingPackage.objects.create(
            code="featured-60",
            name="Featured 60-day Posting",
            description="Highlight your job for 60 days.",
            price_cents=12000,
            duration_days=60,
            max_jobs=3,
            is_featured_package=True,
            is_active=True,
            order=2,
        )
        self.stdout.write(self.style.SUCCESS("Created packages"))

        # --- Employer ---
        Employer.objects.all().delete()
        user_emp = User.objects.create_user(
            username="employer1",
            email="employer1@example.com",
            password="test1234",
        )
        employer = Employer.objects.create(
            user=user_emp,
            email="employer1@example.com",
            name="Jane Doe",
            company_name="Physio Clinic Inc.",
            location="Toronto, ON",
            is_approved=True,
            posting_package=pkg2,
            credits_total=3,
            credits_used=0,
        )
        self.stdout.write(self.style.SUCCESS("Created employer"))

        # --- Job ---
        Job.objects.all().delete()
        job = Job.objects.create(
            employer=employer,
            title="Physiotherapist",
            description="Join our busy clinic and help patients recover!",
            location="Toronto, ON",
            compensation_type="hourly",
            salary_min=35,
            salary_max=50,
            job_type="full_time",
            relocation_assistance=True,
            posting_date=date.today(),
            expiry_date=date.today() + timedelta(days=30),
            featured=True,
            is_active=True,
        )
        self.stdout.write(self.style.SUCCESS("Created job"))

        # --- JobSeeker ---
        JobSeeker.objects.all().delete()
        user_js = User.objects.create_user(
            username="jobseeker1",
            email="jobseeker1@example.com",
            password="test1234",
        )
        seeker = JobSeeker.objects.create(
            user=user_js,
            email="jobseeker1@example.com",
            first_name="John",
            last_name="Smith",
            registration_status="yes",
            opportunity_type="full_time",
            current_location="Vancouver, BC",
            open_to_relocation=True,
            relocation_where="Toronto, ON",
            need_sponsorship=False,
            seeking_immigration=False,
            is_approved=True,
        )
        self.stdout.write(self.style.SUCCESS("Created jobseeker"))

        self.stdout.write(self.style.SUCCESS("✅ Database seeding complete!"))
