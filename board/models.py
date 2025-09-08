from __future__ import annotations
from django.db import models
from django.contrib.auth.models import User
from datetime import date
import os
import uuid

# ---------------- Upload paths (current + legacy stubs) ----------------
def employer_logo_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"employers/logos/{uuid.uuid4().hex}{ext}"

def resume_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"resumes/{uuid.uuid4().hex}{ext}"

def application_resume_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"applications/resumes/{uuid.uuid4().hex}{ext}"

def product_image_upload_path(instance, filename):
    ext = os.path.splitext(filename)[1]
    return f"products/images/{uuid.uuid4().hex}{ext}"

# ---- Legacy migration compatibility (DO NOT REMOVE) ----
def digital_upload_path(instance, filename):
    """
    Compatibility for older migrations that reference board.models.digital_upload_path.
    Keeps historic migrations importable. Routes to a generic uploads/ folder.
    """
    ext = os.path.splitext(filename)[1]
    return f"uploads/{uuid.uuid4().hex}{ext}"

# ---------------- Shared choices ----------------
JOB_TYPE_CHOICES = [
    ("full_time", "Full-time"),
    ("part_time", "Part-time"),
    ("contractor", "Contractor"),
    ("resident", "Resident"),
    ("intern", "Intern"),
    ("locum", "Locum"),
]

REGISTRATION_STATUS_CHOICES = [
    ("yes", "Yes"),
    ("no", "No"),
    ("new_grad", "Canadian New Grad"),
    ("credentialed", "Completed Credentialing"),
    ("pce_written", "Completed Written PCE"),
]

COMPENSATION_TYPE_CHOICES = [
    ("hourly", "Hourly"),
    ("yearly", "Yearly"),
    ("percent", "% split"),
]

# ---------------- Core domain ----------------
class PostingPackage(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    price_cents = models.PositiveIntegerField(default=0)
    duration_days = models.PositiveIntegerField(default=30)
    max_jobs = models.PositiveIntegerField(default=1)
    is_featured_package = models.BooleanField(default=False)
    main_image = models.ImageField(upload_to=product_image_upload_path, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    @property
    def price_display(self) -> str:
        dollars = self.price_cents // 100
        cents = self.price_cents % 100
        return f"${dollars:,}.{cents:02d}"

class Employer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employer")
    email = models.EmailField()
    name = models.CharField(max_length=160)  # contact name
    company_name = models.CharField(max_length=160, blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    website = models.URLField(blank=True, default="")
    location = models.CharField(max_length=160)
    logo = models.ImageField(upload_to=employer_logo_upload_path, blank=True, null=True)
    description = models.TextField(blank=True, default="")
    is_approved = models.BooleanField(default=False)

    # Credits & package linkage
    posting_package = models.ForeignKey(
        PostingPackage, on_delete=models.SET_NULL, null=True, blank=True, related_name="employers"
    )
    credits_total = models.PositiveIntegerField(default=0)
    credits_used = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.company_name or self.name

    @property
    def credits_left(self) -> int:
        return max(0, (self.credits_total or 0) - (self.credits_used or 0))

    @property
    def jobs_count(self) -> int:
        return self.jobs.filter(is_active=True).count()

class Job(models.Model):
    employer = models.ForeignKey(Employer, related_name="jobs", on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=160)

    # Compensation
    compensation_type = models.CharField(max_length=10, choices=COMPENSATION_TYPE_CHOICES, default="hourly")
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    percent_split = models.PositiveIntegerField(blank=True, null=True)

    # Meta
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, blank=True, null=True)
    relocation_assistance = models.BooleanField(default=False)
    posting_date = models.DateField(default=date.today)
    expiry_date = models.DateField(blank=True, null=True)
    featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Apply methods
    application_email = models.EmailField(blank=True, null=True)
    external_apply_url = models.URLField(blank=True, null=True)

    # Simple counters
    view_count = models.PositiveIntegerField(default=0)
    application_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title

# Precision analytics
class JobView(models.Model):
    job = models.ForeignKey(Job, related_name="views", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_apply_click = models.BooleanField(default=False)

class Application(models.Model):
    job = models.ForeignKey(Job, related_name="applications", on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    email = models.EmailField()
    resume = models.FileField(upload_to=application_resume_upload_path, blank=True, null=True)
    cover_letter = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

# Commerce
class Purchase(models.Model):
    employer = models.ForeignKey(Employer, related_name="purchases", on_delete=models.CASCADE)
    package = models.ForeignKey(PostingPackage, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField(default=1)
    credits_total = models.PositiveIntegerField(default=0)
    purchased_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.employer} · {self.package} x{self.quantity}"

class Invoice(models.Model):
    employer = models.ForeignKey(Employer, related_name="invoices", on_delete=models.CASCADE)
    external_id = models.CharField(max_length=80, blank=True, default="")  # Stripe/PayPal id
    amount_cents = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=False)

    def __str__(self):
        return f"Invoice {self.id} · {self.employer}"

# Candidate side
class JobSeeker(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="jobseeker")
    email = models.EmailField()
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)

    registration_status = models.CharField(max_length=20, choices=[
        ("yes", "Yes"),
        ("no", "No"),
        ("new_grad", "Canadian New Grad"),
        ("credentialed", "Completed Credentialing"),
        ("pce_written", "Completed Written PCE"),
    ])
    opportunity_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, blank=True, null=True)
    current_location = models.CharField(max_length=160)

    open_to_relocation = models.BooleanField(default=False)
    relocation_where = models.CharField(max_length=200, blank=True, default="")
    need_sponsorship = models.BooleanField(default=False)
    seeking_immigration = models.BooleanField(default=False)

    # Legacy compatibility fields
    city = models.CharField(max_length=120, blank=True, default="")
    province = models.CharField(max_length=120, blank=True, default="")
    position_desired = models.CharField(max_length=160, blank=True, default="")
    is_registered_canada = models.BooleanField(default=False)

    resume = models.FileField(upload_to=resume_upload_path, blank=True, null=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name or self.email

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

class JobAlert(models.Model):
    email = models.EmailField()
    q = models.CharField(max_length=200, blank=True, default="")
    location = models.CharField(max_length=160, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        base = self.email
        parts = []
        if self.q:
            parts.append(f"q={self.q}")
        if self.location:
            parts.append(f"loc={self.location}")
        tail = " ".join(parts)
        return f"{base} {tail}".strip()
