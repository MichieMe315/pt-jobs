from django.conf import settings
from django.db import models
from .private_storage import PrivateMobilityStorage

class InternationalProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="international_pt_profile")
    country_of_education = models.CharField(max_length=100)
    citizenship_country = models.CharField(max_length=100, blank=True)
    residence_country = models.CharField(max_length=100, blank=True)
    canadian_immigration_status = models.CharField(max_length=40, blank=True)
    graduation_year = models.PositiveSmallIntegerField(null=True, blank=True)
    registered_in_education_country = models.CharField(max_length=15, blank=True)
    destination_province = models.CharField(max_length=100, blank=True)
    capr_stage = models.CharField(max_length=100, blank=True)
    marketing_consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.user.email or self.user.username

class ReferenceCost(models.Model):
    KIND = [("rent","Monthly rent"),("salary","Annual PT salary"),("living","Other monthly living costs"),("licensing","Licensing allowance"),("moving_km","Moving cost per kilometre")]
    kind = models.CharField(max_length=20, choices=KIND)
    city = models.CharField(max_length=100, blank=True, help_text="Leave blank for national/default")
    province = models.CharField(max_length=100, blank=True)
    amount_cad = models.DecimalField(max_digits=12,decimal_places=2)
    source_url = models.URLField(blank=True)
    verified_on = models.DateField(null=True,blank=True)
    is_published = models.BooleanField(default=False)
    class Meta:
        unique_together = ("kind","city","province")
    def __str__(self): return f"{self.kind}: {self.city}, {self.province}"

class PathwayRule(models.Model):
    country = models.CharField(max_length=100)
    pathway_label = models.CharField(max_length=160)
    summary = models.TextField()
    source_url = models.URLField()
    verified_on = models.DateField()
    is_published = models.BooleanField(default=False)
    class Meta:
        ordering = ["country"]
    def __str__(self): return self.country

class DigitalProduct(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price_cad = models.DecimalField(max_digits=9,decimal_places=2,default=0)
    download = models.FileField(upload_to="career_mobility/products/",blank=True, storage=PrivateMobilityStorage())
    is_published = models.BooleanField(default=False)
    def __str__(self): return self.title

class ProductOrder(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    product = models.ForeignKey(DigitalProduct,on_delete=models.PROTECT)
    stripe_session_id = models.CharField(max_length=255,unique=True)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class DataSource(models.Model):
    """Tracked official publication; a changed page never changes public prices automatically."""
    CADENCE = [("monthly", "Monthly"), ("quarterly", "Quarterly")]
    category = models.CharField(max_length=40)
    name = models.CharField(max_length=180, unique=True)
    url = models.URLField(max_length=500)
    cadence = models.CharField(max_length=12, choices=CADENCE, default="monthly")
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_changed_at = models.DateTimeField(null=True, blank=True)
    last_http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    content_sha256 = models.CharField(max_length=64, blank=True)
    last_error = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class DataSourceReview(models.Model):
    STATUS = [("pending", "Needs review"), ("approved", "Reviewed"), ("dismissed", "Dismissed")]
    source = models.ForeignKey(DataSource, on_delete=models.CASCADE, related_name="reviews")
    detected_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    previous_hash = models.CharField(max_length=64, blank=True)
    detected_hash = models.CharField(max_length=64)
    detail = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-detected_at"]

    def __str__(self):
        return f"{self.source.name} — {self.status}"


class ProvincialLicenceFee(models.Model):
    """One regulator fee component, reviewed before publication. Not a total cost estimate."""
    FEE_TYPES = [
        ("application", "Application/assessment"),
        ("initial", "Initial registration"),
        ("renewal", "Annual renewal"),
        ("provisional", "Provisional registration"),
        ("exam", "Exam/assessment"),
        ("other", "Other"),
    ]
    province = models.CharField(max_length=80)
    regulator = models.CharField(max_length=180)
    fee_type = models.CharField(max_length=20, choices=FEE_TYPES)
    description = models.CharField(max_length=240)
    amount_cad = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    applies_to = models.CharField(max_length=160, blank=True, help_text="e.g. Canadian graduate, internationally educated applicant, specific dates")
    effective_on = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    verified_on = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["province", "fee_type", "description"]

    def __str__(self):
        return f"{self.province}: {self.description}"

    @property
    def has_publishable_evidence(self):
        return self.amount_cad is not None and bool(self.source_url and self.verified_on and self.effective_on)

    def clean(self):
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        errors = {}
        if self.is_published and not self.has_publishable_evidence:
            errors["is_published"] = "Publishing requires amount, official source URL, effective date and verification date."
        if self.is_published and self.expires_on and self.expires_on < timezone.localdate():
            errors["expires_on"] = "Expired fees cannot be published."
        if self.expires_on and self.effective_on and self.expires_on < self.effective_on:
            errors["expires_on"] = "Expiry cannot precede effective date."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class InternationalChecklistItem(models.Model):
    profile = models.ForeignKey(InternationalProfile, on_delete=models.CASCADE, related_name="checklist_items")
    key = models.SlugField(max_length=90)
    completed = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["profile", "key"], name="mobility_unique_checklist_item")]

class SavedCareerPlan(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mobility_plans")
    plan_type = models.CharField(max_length=20, choices=[("salary", "Salary comparison"), ("relocation", "Relocation")])
    title = models.CharField(max_length=120)
    inputs = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-created_at"]

class SalaryBenchmark(models.Model):
    region = models.CharField(max_length=130, unique=True)
    province = models.CharField(max_length=90, blank=True)
    low_hourly = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    median_hourly = models.DecimalField(max_digits=8, decimal_places=2)
    high_hourly = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    source_url = models.URLField(max_length=500)
    reference_period = models.CharField(max_length=90)
    verified_on = models.DateField()
    is_published = models.BooleanField(default=False)
    def __str__(self):
        return self.region
