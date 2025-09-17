from __future__ import annotations

import os
import uuid
from datetime import timedelta, date

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


# ------------------------
# Upload helpers
# ------------------------
def _safe_name(filename: str) -> str:
    base, ext = os.path.splitext(filename or "")
    base = slugify(base or "file") or "file"
    return f"{base}-{uuid.uuid4().hex[:8]}{ext.lower()}"

def employer_logo_upload_path(instance, filename):
    return os.path.join("employers", str(instance.pk or "new"), "logos", _safe_name(filename))

def resume_upload_path(instance, filename):
    # jobseeker resumes
    return os.path.join("jobseekers", str(getattr(instance, "jobseeker_id", "new")), _safe_name(filename))

def application_resume_upload_path(instance, filename):
    # resumes attached to applications
    return os.path.join("applications", "resumes", _safe_name(filename))

# Backward-compat for an older migration that referenced this name
def resume_item_upload_path(instance, filename):
    return resume_upload_path(instance, filename)


# ------------------------
# Core models
# ------------------------
class Employer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employer")
    email = models.EmailField(blank=True, null=True, default="")
    name = models.CharField(max_length=150, blank=True, default="", help_text="Contact person")
    company_name = models.CharField(max_length=200, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    website = models.URLField(blank=True, default="")
    location = models.CharField(max_length=200, blank=True, default="")
    logo = models.ImageField(upload_to=employer_logo_upload_path, blank=True, null=True)
    description = models.TextField(blank=True, default="")
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["company_name", "name", "id"]

    def __str__(self):
        return self.company_name or self.name or (self.email or "")

    def get_absolute_url(self):
        return reverse("employer_public_profile", args=[self.pk])


class JobSeeker(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="jobseeker")
    email = models.EmailField(blank=True, null=True, default="")
    first_name = models.CharField(max_length=80, blank=True, null=True, default="")
    last_name = models.CharField(max_length=80, blank=True, null=True, default="")
    position_desired = models.CharField(max_length=200, blank=True, default="")
    opportunity_type = models.CharField(max_length=200, blank=True, default="")
    current_location = models.CharField(max_length=200, blank=True, default="")
    registration_status = models.CharField(max_length=50, blank=True, default="")
    open_to_relocation = models.BooleanField(default=False)
    relocation_where = models.CharField(max_length=200, blank=True, default="")
    need_sponsorship = models.BooleanField(default=False)
    seeking_immigration = models.BooleanField(default=False)
    resume = models.FileField(upload_to=resume_upload_path, blank=True, null=True)
    is_approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["last_name", "first_name", "id"]

    def __str__(self):
        full = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return full or (self.email or "")

    @property
    def full_name(self) -> str:
        return f"{(self.first_name or '').strip()} {(self.last_name or '').strip()}".strip()


class PostingPackage(models.Model):
    code = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")
    duration_days = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        default=30,
        help_text="How long each job post can run.",
    )
    max_jobs = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)
    price_cents = models.PositiveIntegerField(default=0)
    allows_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    package_expires_days = models.PositiveIntegerField(
        default=365,
        help_text="When a package is purchased, credits expire N days later.",
    )

    class Meta:
        ordering = ["order", "name", "id"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def price_display(self) -> str:
        return f"${(self.price_cents or 0) / 100:.2f}"


class PurchasedPackage(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="purchases")
    package = models.ForeignKey(PostingPackage, on_delete=models.PROTECT, related_name="purchases")
    credits_total = models.PositiveIntegerField(default=0)
    credits_used = models.PositiveIntegerField(default=0)
    purchased_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-purchased_at", "id"]

    def __str__(self):
        return f"{self.employer} → {self.package} ({self.credits_used}/{self.credits_total})"

    @property
    def credits_left(self) -> int:
        return max(int(self.credits_total or 0) - int(self.credits_used or 0), 0)

    @property
    def purchase_price_cents(self) -> int:
        try:
            return int(self.package.price_cents or 0)
        except Exception:
            return 0

    @property
    def purchase_price_display(self) -> str:
        return f"${self.purchase_price_cents / 100:.2f}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if not self.credits_total and self.package_id:
            self.credits_total = self.package.max_jobs
        if (is_new or not self.expires_at) and self.package_id:
            base_dt = timezone.now()
            days = int(self.package.package_expires_days or 0)
            self.expires_at = base_dt + timedelta(days=days)
        super().save(*args, **kwargs)


class Job(models.Model):
    COMP_CHOICES = (("yearly", "Yearly"), ("hourly", "Hourly"), ("split", "Percent split"))
    JOB_TYPE_CHOICES = (
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contractor", "Contractor"),
        ("resident", "Resident"),
        ("intern", "Intern"),
        ("locum", "Locum"),
    )

    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="jobs")
    title = models.CharField(max_length=200)
    description = models.TextField()
    location = models.CharField(max_length=200, blank=True, default="")
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, blank=True, default="")
    compensation_type = models.CharField(max_length=10, choices=COMP_CHOICES, blank=True, default="")
    salary_min = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    salary_max = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    percent_split = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    application_email = models.EmailField(blank=True, default="")
    external_apply_url = models.URLField(blank=True, default="")
    application_instructions = models.TextField(blank=True, default="")
    relocation_assistance_provided = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)
    posting_date = models.DateField(auto_now_add=True)
    expiry_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    views_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-posting_date", "-id"]

    def __str__(self):
        return f"{self.title} @ {self.employer}"

    def get_absolute_url(self):
        return reverse("job_detail", args=[self.pk])

    @property
    def is_expired(self) -> bool:
        if not self.expiry_date:
            return False
        return date.today() > self.expiry_date


# ------------------------
# Resumes / Applications / Saved jobs
# ------------------------
class Resume(models.Model):
    jobseeker = models.ForeignKey(JobSeeker, on_delete=models.CASCADE, related_name="resumes")
    title = models.CharField(max_length=200, default="Resume")
    file = models.FileField(upload_to=resume_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at", "id"]

    def __str__(self):
        return f"{self.title} ({self.jobseeker})"

    # For admin compatibility (some configs used 'label' in list_display)
    @property
    def label(self) -> str:
        return self.title


class Application(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    jobseeker = models.ForeignKey(JobSeeker, on_delete=models.CASCADE, related_name="applications")
    name = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    resume = models.FileField(upload_to=application_resume_upload_path, blank=True, null=True)
    cover_letter = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def __str__(self):
        return f"{self.jobseeker} → {self.job}"


class SavedJob(models.Model):
    jobseeker = models.ForeignKey(JobSeeker, on_delete=models.CASCADE, related_name="saved_jobs")
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="saved_by")
    # CHANGED: use default=timezone.now (no interactive prompt needed)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ("jobseeker", "job")
        ordering = ["-created_at", "id"]

    def __str__(self):
        return f"{self.jobseeker} saved {self.job}"


# ------------------------
# Alerts / Emails / Invoices
# ------------------------
class JobAlert(models.Model):
    email = models.EmailField()
    q = models.CharField(max_length=200, blank=True, default="")
    location = models.CharField(max_length=200, blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def __str__(self):
        return f"{self.email} ({self.q} @ {self.location})"


class EmailTemplate(models.Model):
    slug = models.SlugField(unique=True)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self):
        return self.slug


class Invoice(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="invoices")
    created_at = models.DateTimeField(auto_now_add=True)
    amount_cents = models.PositiveIntegerField(default=0)
    external_reference = models.CharField(max_length=100, blank=True, default="")
    # IMPORTANT: match initial migration field name to avoid rename prompts
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at", "id"]

    def __str__(self):
        return f"Invoice #{self.pk} for {self.employer}"

    @property
    def amount_display(self) -> str:
        return f"${(self.amount_cents or 0) / 100:.2f}"

    # Backward-compat alias if any code/templates use `description`
    @property
    def description(self) -> str:
        return self.notes

# --- Payments & Discounts -----------------------------------------------------
from django.utils import timezone

class PaymentGatewayConfig(models.Model):
    """
    Manage Stripe/PayPal keys from Admin. Mark one row active (is_active=True).
    """
    MODE_CHOICES = (("sandbox", "Sandbox"), ("live", "Live"))

    name = models.CharField(max_length=100, default="Default")
    is_active = models.BooleanField(default=True)

    # Stripe
    use_stripe = models.BooleanField(default=False)
    stripe_public_key = models.CharField(max_length=200, blank=True, default="")
    stripe_secret_key = models.CharField(max_length=200, blank=True, default="")

    # PayPal
    use_paypal = models.BooleanField(default=False)
    paypal_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="sandbox")
    paypal_client_id = models.CharField(max_length=200, blank=True, default="")
    paypal_client_secret = models.CharField(max_length=200, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-updated_at", "-id"]

    def __str__(self):
        labels = []
        if self.use_stripe:
            labels.append("Stripe")
        if self.use_paypal:
            labels.append("PayPal")
        flags = ", ".join(labels) or "No gateway enabled"
        state = "ACTIVE" if self.is_active else "inactive"
        return f"{self.name} ({flags}, {state})"

    @classmethod
    def get_active_gateway(cls):
        return cls.objects.filter(is_active=True).order_by("-updated_at", "-id").first()


class DiscountCode(models.Model):
    """
    Discount codes usable on package checkout: fixed amount or percentage.
    """
    TYPE_CHOICES = (("fixed", "Fixed amount (cents)"), ("percent", "Percent (%)"))

    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120, blank=True, default="")
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="fixed")

    # For 'fixed', amount_cents applies; for 'percent', percent applies.
    amount_cents = models.PositiveIntegerField(default=0)
    percent = models.PositiveIntegerField(default=0, help_text="0–100 for percent discounts")

    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank for unlimited")
    uses = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    notes = models.CharField(max_length=200, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    def is_valid_now(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now > self.ends_at:
            return False
        if self.max_uses is not None and self.uses >= self.max_uses:
            return False
        return True

    def apply_to_cents(self, price_cents: int) -> int:
        price_cents = int(price_cents or 0)
        if not self.is_valid_now():
            return price_cents
        if self.type == "percent":
            pct = max(0, min(100, int(self.percent or 0)))
            new_val = round(price_cents * (100 - pct) / 100)
        else:
            amt = int(self.amount_cents or 0)
            new_val = price_cents - amt
        return max(0, int(new_val))

