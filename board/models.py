from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Max, Q
from django.utils import timezone


def employer_logo_upload_path(instance, filename):
    return f"employers/{instance.id or 'new'}/logo/{filename}"


def product_image_upload_path(instance, filename):
    return f"packages/{instance.id or 'new'}/main/{filename}"


def resume_upload_path(instance, filename):
    return f"jobseekers/{instance.jobseeker_id or 'new'}/resumes/{filename}"


def application_resume_upload_path(instance, filename):
    return f"applications/{instance.job_id or 'new'}/{filename}"


class PostingPackage(models.Model):
    name = models.CharField(max_length=120)
    code = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    duration_days = models.PositiveIntegerField(default=30)
    max_jobs = models.PositiveIntegerField(default=1)
    price_cents = models.PositiveIntegerField(default=0)
    main_image = models.ImageField(upload_to=product_image_upload_path, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "name")

    def __str__(self) -> str:
        return f"{self.name} ({self.duration_days}d, {self.max_jobs} jobs)"


class Employer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employer")
    email = models.EmailField()
    name = models.CharField(max_length=120)
    company_name = models.CharField(max_length=180, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=180)
    logo = models.ImageField(upload_to=employer_logo_upload_path, blank=True, null=True)
    description = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.company_name or self.name

    # ---- Credit helpers ----
    def active_purchases_qs(self):
        now = timezone.now()
        return self.purchases.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))

    def max_package_duration_days(self) -> int:
        """Best-available duration among active purchases (used only by Admin when blank)."""
        days = self.active_purchases_qs().aggregate(m=Max("package__duration_days")).get("m")
        return int(days or 30)


REGISTRATION_CHOICES = (
    ("yes", "Yes"),
    ("no", "No"),
    ("canadian_new_grad", "Canadian New Grad"),
    ("credentialing_done", "Completed Credentialing"),
    ("pce_written_done", "Completed Written PCE"),
)

OPPORTUNITY_CHOICES = (
    ("full_time", "Full-time"),
    ("part_time", "Part-time"),
    ("contractor", "Contractor"),
    ("resident", "Resident"),
    ("intern", "Intern"),
    ("locum", "Locum"),
)

JOB_TYPE_CHOICES = OPPORTUNITY_CHOICES

COMP_CHOICES = (
    ("yearly", "Yearly"),
    ("hourly", "Hourly"),
    ("percent", "Split (%)"),
)


class JobSeeker(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobseeker")
    email = models.EmailField()
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    current_location = models.CharField(max_length=180)
    position_desired = models.CharField(max_length=180, blank=True)
    registration_status = models.CharField(max_length=40, choices=REGISTRATION_CHOICES)
    opportunity_type = models.CharField(max_length=40, choices=OPPORTUNITY_CHOICES)
    open_to_relocation = models.BooleanField(default=False)
    relocation_where = models.CharField(max_length=180, blank=True)
    need_sponsorship = models.BooleanField(default=False)
    seeking_immigration = models.BooleanField(default=False)
    resume = models.FileField(upload_to=resume_upload_path, blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


class Job(models.Model):
    employer = models.ForeignKey(Employer, related_name="jobs", on_delete=models.CASCADE)

    title = models.CharField(max_length=180)
    description = models.TextField()
    location = models.CharField(max_length=180)

    job_type = models.CharField(max_length=32, choices=JOB_TYPE_CHOICES, blank=True)

    # Compensation
    compensation_type = models.CharField(max_length=16, choices=COMP_CHOICES, blank=True)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    relocation_assistance = models.BooleanField(default=False)

    # Dates
    posting_date = models.DateField(default=timezone.localdate)
    expiry_date = models.DateField(blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)
    featured = models.BooleanField(default=False)

    # Apply
    application_email = models.EmailField(blank=True, null=True)
    external_apply_url = models.URLField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-posting_date", "-id")

    def __str__(self) -> str:
        return self.title


class PurchasedPackage(models.Model):
    employer = models.ForeignKey(Employer, related_name="purchases", on_delete=models.CASCADE)
    package = models.ForeignKey(PostingPackage, on_delete=models.PROTECT)
    credits_total = models.PositiveIntegerField(default=0)
    credits_used = models.PositiveIntegerField(default=0)
    purchased_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-purchased_at",)

    def __str__(self) -> str:
        return f"{self.employer} · {self.package} ({self.credits_used}/{self.credits_total})"


class JobAlert(models.Model):
    email = models.EmailField()
    q = models.CharField(max_length=180, blank=True)
    location = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return self.email


class Invoice(models.Model):
    employer = models.ForeignKey(Employer, related_name="invoices", on_delete=models.CASCADE)
    amount_cents = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Invoice {self.id} – {self.employer}"
