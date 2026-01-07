from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
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
    return os.path.join("jobseekers", str(getattr(instance, "jobseeker_id", "new")), "resumes", _safe_name(filename))


def application_resume_upload_path(instance, filename):
    return os.path.join("applications", "resumes", _safe_name(filename))


# Backward-compat for an older migration that referenced this name
def resume_item_upload_path(instance, filename):
    return resume_upload_path(instance, filename)


# Some older migrations referenced this upload helper for SiteSettings branding fields.
def branding_upload_path(instance, filename):
    return os.path.join("site", "branding", _safe_name(filename))


# ------------------------
# Settings / CMS-ish models
# ------------------------
class SiteSettings(models.Model):
    """
    Admin-driven homepage + global site configuration.
    Contract: Hero Image/Title/Subtitle MUST come from here (no hardcoded fallbacks).
    """

    site_name = models.CharField(max_length=200, blank=True, default="Physiotherapy Jobs Canada")
    contact_email = models.EmailField(blank=True, default="")

    # Contract hero fields (NEW — keep legacy home_hero_* fields below)
    hero_image = models.ImageField(upload_to="site/hero/", blank=True, null=True)
    hero_title = models.CharField(max_length=200, blank=True, default="")
    hero_subtitle = models.CharField(max_length=400, blank=True, default="")

    # Contract: server-side posting duration clamp for expiry date (days)
    posting_duration_days = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1)]
    )

    # Legacy homepage fields (do NOT remove — older templates/migrations may use these)
    home_hero_image = models.ImageField(upload_to="site/home/", blank=True, null=True)
    home_hero_title = models.CharField(max_length=200, blank=True, default="")
    home_hero_subtitle = models.CharField(max_length=400, blank=True, default="")
    home_hero_cta_text = models.CharField(max_length=200, blank=True, default="")
    home_hero_cta_url = models.CharField(max_length=500, blank=True, default="")

    # Footer / layout legacy
    footer_text = models.TextField(blank=True, default="")
    employer_column_title = models.CharField(max_length=200, blank=True, default="")
    employer_column_content = models.TextField(blank=True, default="")
    jobseeker_column_title = models.CharField(max_length=200, blank=True, default="")
    jobseeker_column_content = models.TextField(blank=True, default="")

    # Social legacy
    facebook_url = models.CharField(max_length=300, blank=True, default="")
    instagram_url = models.CharField(max_length=300, blank=True, default="")
    linkedin_url = models.CharField(max_length=300, blank=True, default="")
    twitter_url = models.CharField(max_length=300, blank=True, default="")
    reddit_url = models.CharField(max_length=300, blank=True, default="")

    # Analytics / SEO legacy
    google_analytics_id = models.CharField(max_length=80, blank=True, default="")
    seo_meta_title = models.CharField(max_length=200, blank=True, default="")
    seo_meta_description = models.TextField(blank=True, default="")

    # Side banners / marketing
    side_banner_html = models.TextField(blank=True, default="")
    bottom_banner_html = models.TextField(blank=True, default="")

    # Branding legacy (older migrations referenced branding_upload_path)
    branding_logo = models.ImageField(upload_to=branding_upload_path, blank=True, null=True)
    branding_favicon = models.ImageField(upload_to=branding_upload_path, blank=True, null=True)
    branding_primary_color = models.CharField(max_length=20, blank=True, default="")
    branding_secondary_color = models.CharField(max_length=20, blank=True, default="")
    branding_footer_html = models.TextField(blank=True, default="")

    # Mapbox (optional)
    mapbox_token = models.CharField(max_length=300, blank=True, default="")

    # Webhook legacy
    social_webhook_url = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        verbose_name = "Site Settings"
        verbose_name_plural = "Site Settings"

    def __str__(self):
        return self.site_name or "SiteSettings"


class WidgetTemplate(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    html = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slug", "id"]

    def __str__(self):
        return self.slug


class SocialPostingConfig(models.Model):
    enabled = models.BooleanField(default=False)
    facebook_page_id = models.CharField(max_length=120, blank=True, default="")
    instagram_business_id = models.CharField(max_length=120, blank=True, default="")
    reddit_subreddit = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def __str__(self):
        return f"SocialPostingConfig #{self.pk or 'new'}"


class WebhookConfig(models.Model):
    enabled = models.BooleanField(default=False)
    url = models.URLField(blank=True, default="")
    secret = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def __str__(self):
        return f"WebhookConfig #{self.pk or 'new'}"


# ------------------------
# Core models
# ------------------------
class Employer(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="employer")

    email = models.EmailField(blank=True, null=True, default="")
    name = models.CharField(max_length=150, blank=True, default="", help_text="Contact person")
    company_name = models.CharField(max_length=200, blank=True, default="")

    # Keep both (legacy-safe)
    company_description = models.TextField(blank=True, default="")
    description = models.TextField(blank=True, default="")

    phone = models.CharField(max_length=50, blank=True, default="")
    website = models.URLField(blank=True, default="")
    location = models.CharField(max_length=200, blank=True, default="")
    logo = models.ImageField(upload_to=employer_logo_upload_path, blank=True, null=True)

    is_approved = models.BooleanField(default=False)
    login_active = models.BooleanField(default=True)
    credits = models.PositiveIntegerField(default=0)

    approved_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

    registered_in_canada = models.BooleanField(default=False)

    OPPORTUNITY_CHOICES = (
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contractor", "Contractor"),
        ("casual", "Casual"),
        ("locum", "Locum"),
        ("temporary", "Temporary"),
    )
    opportunity_type = models.CharField(max_length=30, choices=OPPORTUNITY_CHOICES, blank=True, default="")

    current_location = models.CharField(max_length=200, blank=True, default="")

    open_to_relocate = models.BooleanField(default=False)

    # IMPORTANT: your current code expects THIS name
    relocate_where = models.CharField(max_length=200, blank=True, default="")

    require_sponsorship = models.BooleanField(default=False)
    seeking_immigration = models.BooleanField(default=False)

    resume = models.FileField(upload_to=resume_upload_path, blank=True, null=True)

    is_approved = models.BooleanField(default=False)
    login_active = models.BooleanField(default=True)
    approved_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "id"]

    def __str__(self):
        full = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return full or (self.email or "")

    @property
    def full_name(self) -> str:
        return f"{(self.first_name or '').strip()} {(self.last_name or '').strip()}".strip()


class PostingPackage(models.Model):
    code = models.SlugField(max_length=80, unique=True, default="")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")

    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=30)

    credits = models.PositiveIntegerField(validators=[MinValueValidator(1)], default=1)

    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    price_cents = models.PositiveIntegerField(default=0)

    allows_featured = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    # Legacy fields that previously existed in some versions
    is_featured = models.BooleanField(default=False)
    priority_level = models.IntegerField(default=0)

    order = models.IntegerField(default=0)

    package_expires_days = models.PositiveIntegerField(default=365)

    class Meta:
        ordering = ["order", "name", "id"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def save(self, *args, **kwargs):
        try:
            self.price = (int(self.price_cents or 0) / 100)
        except Exception:
            pass
        super().save(*args, **kwargs)

    @property
    def price_display(self) -> str:
        return f"${(self.price_cents or 0) / 100:.2f}"


class PurchasedPackage(models.Model):
    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="purchases")
    package = models.ForeignKey(PostingPackage, on_delete=models.PROTECT, related_name="purchases")

    credits_granted = models.PositiveIntegerField(default=0)
    credits_remaining = models.PositiveIntegerField(default=0)

    purchased_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    source = models.CharField(max_length=50, blank=True, default="")

    # Legacy field
    duration_days = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-purchased_at", "id"]

    def __str__(self):
        return f"{self.employer} → {self.package} ({self.credits_remaining}/{self.credits_granted})"

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        if (is_new or not self.credits_granted) and self.package_id:
            self.credits_granted = int(self.package.credits or 0)

        if (is_new or not self.credits_remaining) and self.package_id:
            self.credits_remaining = int(self.credits_granted or 0)

        if (is_new or not self.expires_at) and self.package_id:
            self.expires_at = timezone.now() + timedelta(days=int(self.package.package_expires_days or 0))

        super().save(*args, **kwargs)


class Job(models.Model):
    JOB_TYPE_CHOICES = (
        ("full_time", "Full-time"),
        ("part_time", "Part-time"),
        ("contractor", "Contractor"),
        ("casual", "Casual"),
        ("locum", "Locum"),
        ("temporary", "Temporary"),
    )

    COMP_TYPE_CHOICES = (
        ("hourly", "Hourly"),
        ("yearly", "Yearly"),
        ("split", "Percent split"),
    )

    APPLY_VIA_CHOICES = (
        ("email", "Email"),
        ("url", "URL"),
    )

    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="jobs")

    title = models.CharField(max_length=200)
    description = models.TextField()

    job_type = models.CharField(max_length=30, choices=JOB_TYPE_CHOICES, blank=True, default="")
    compensation_type = models.CharField(max_length=20, choices=COMP_TYPE_CHOICES, blank=True, default="")

    compensation_min = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    compensation_max = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    location = models.CharField(max_length=200, blank=True, default="")

    apply_via = models.CharField(max_length=10, choices=APPLY_VIA_CHOICES, blank=True, default="")
    apply_email = models.EmailField(blank=True, default="")
    apply_url = models.URLField(blank=True, default="")

    # Legacy apply fields
    application_email = models.EmailField(blank=True, default="")
    external_apply_url = models.URLField(blank=True, default="")
    application_instructions = models.TextField(blank=True, default="")

    # IMPORTANT: your current code expects THIS name
    relocation_assistance = models.BooleanField(default=False)

    # Contract name (keep both; do not remove)
    relocation_assistance_provided = models.BooleanField(default=False)

    posting_date = models.DateField(default=timezone.now)
    expiry_date = models.DateField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    is_featured = models.BooleanField(default=False)
    featured = models.BooleanField(default=False)

    views_count = models.PositiveIntegerField(default=0)

    source = models.CharField(max_length=50, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


class Resume(models.Model):
    jobseeker = models.ForeignKey(JobSeeker, on_delete=models.CASCADE, related_name="resumes")
    title = models.CharField(max_length=200, default="Resume")
    file = models.FileField(upload_to=resume_upload_path)

    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]

    def __str__(self):
        return f"{self.title} ({self.jobseeker})"

    @property
    def label(self) -> str:
        return self.title


class Application(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="applications")
    jobseeker = models.ForeignKey(JobSeeker, on_delete=models.CASCADE, related_name="applications")

    name = models.CharField(max_length=255, blank=True, default="")
    email = models.EmailField(blank=True, default="")

    resume_selected = models.ForeignKey(
        Resume, on_delete=models.SET_NULL, blank=True, null=True, related_name="applications"
    )
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
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ("jobseeker", "job")
        ordering = ["-created_at", "id"]

    def __str__(self):
        return f"{self.jobseeker} saved {self.job}"


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
    key = models.SlugField(unique=True)
    name = models.CharField(max_length=200, blank=True, default="")
    subject = models.CharField(max_length=300, blank=True, default="")
    html = models.TextField(blank=True, default="")
    is_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key


class PaymentGatewayConfig(models.Model):
    MODE_CHOICES = (("sandbox", "Sandbox"), ("live", "Live"))

    gateway_name = models.CharField(max_length=100, default="Default")
    currency = models.CharField(max_length=10, blank=True, default="CAD")
    is_active = models.BooleanField(default=True)

    use_stripe = models.BooleanField(default=False)
    stripe_public_key = models.CharField(max_length=200, blank=True, default="")
    stripe_secret_key = models.CharField(max_length=200, blank=True, default="")

    use_paypal = models.BooleanField(default=False)
    paypal_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="sandbox")
    paypal_client_id = models.CharField(max_length=200, blank=True, default="")
    paypal_client_secret = models.CharField(max_length=200, blank=True, default="")

    # Legacy fields expected by older migrations/admin variants
    stripe_publishable_key = models.CharField(max_length=200, blank=True, default="")
    paypal_secret = models.CharField(max_length=200, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-updated_at", "-id"]

    def __str__(self):
        return f"{self.gateway_name} ({'ACTIVE' if self.is_active else 'inactive'})"

    @classmethod
    def get_active_gateway(cls):
        return cls.objects.filter(is_active=True).order_by("-updated_at", "-id").first()


class DiscountCode(models.Model):
    KIND_CHOICES = (
        ("fixed", "Fixed (cents)"),
        ("percent", "Percent (%)"),
    )

    code = models.CharField(max_length=40, unique=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="fixed")

    value = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1000000)])

    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    name = models.CharField(max_length=120, blank=True, default="")
    max_uses = models.PositiveIntegerField(blank=True, null=True)
    uses = models.PositiveIntegerField(default=0)

    # Legacy
    applicable_package = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    def is_valid_now(self) -> bool:
        if not self.is_active:
            return False
        today = timezone.now().date()
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        if self.max_uses is not None and self.uses >= self.max_uses:
            return False
        return True

    def apply_to_cents(self, price_cents: int) -> int:
        price_cents = int(price_cents or 0)
        if not self.is_valid_now():
            return price_cents

        if self.kind == "percent":
            pct = max(0, min(100, int(self.value or 0)))
            new_val = round(price_cents * (100 - pct) / 100)
        else:
            new_val = price_cents - int(self.value or 0)

        return max(0, int(new_val))


class Invoice(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
        ("void", "Void"),
    )
    PROCESSOR_CHOICES = (
        ("stripe", "Stripe"),
        ("paypal", "PayPal"),
        ("manual", "Manual"),
    )

    employer = models.ForeignKey(Employer, on_delete=models.CASCADE, related_name="invoices")

    amount = models.PositiveIntegerField(default=0)  # cents
    currency = models.CharField(max_length=10, default="CAD")

    processor = models.CharField(max_length=20, choices=PROCESSOR_CHOICES, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    order_date = models.DateTimeField(default=timezone.now)
    processor_reference = models.CharField(max_length=120, blank=True, default="")

    discount_code = models.CharField(max_length=40, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-order_date", "id"]

    def __str__(self):
        return f"Invoice #{self.pk} for {self.employer}"

    @property
    def amount_display(self) -> str:
        return f"${(self.amount or 0) / 100:.2f}"
