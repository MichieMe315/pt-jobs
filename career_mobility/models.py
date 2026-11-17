from django.core.validators import MinValueValidator
from django.conf import settings
from django.db import models
from .private_storage import PrivateMobilityStorage

class InternationalProfile(models.Model):
    email_verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    email_verified_address = models.EmailField(blank=True, editable=False)
    verification_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="international_pt_profile")
    country_of_education = models.CharField(max_length=100)
    citizenship_country = models.CharField(max_length=100, blank=True)
    residence_country = models.CharField(max_length=100, blank=True)
    canadian_immigration_status = models.CharField(max_length=40, blank=True)
    graduation_year = models.PositiveSmallIntegerField(null=True, blank=True)
    registered_in_education_country = models.CharField(max_length=15, blank=True)
    destination_province = models.CharField(max_length=100, blank=True)
    capr_stage = models.CharField(max_length=100, blank=True)
    application_history = models.CharField(max_length=16, default='unsure', choices=[('new','Not yet applied'),('existing','Applied before 15 October 2026'),('after','Applied on or after 15 October 2026'),('unsure','Already applied / unsure')])
    marketing_consent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    @property
    def email_is_verified(self):
        return bool(self.email_verified_at and (not self.email_verified_address or self.email_verified_address.casefold()==self.user.email.casefold()))
    def __str__(self): return self.user.email or self.user.username

class ReferenceCost(models.Model):
    KIND = [("rent","Monthly rent"),("salary","Annual PT salary"),("living","Other monthly living costs"),("licensing","Licensing allowance"),("moving_km","Moving cost per kilometre")]
    kind = models.CharField(max_length=20, choices=KIND)
    city = models.CharField(max_length=100, blank=True, help_text="Leave blank for national/default")
    province = models.CharField(max_length=100, blank=True)
    amount_cad = models.DecimalField(max_digits=12,decimal_places=2)
    source_url = models.URLField(blank=True)
    reference_period = models.CharField(max_length=90,blank=True)
    basis = models.CharField(max_length=300,blank=True)
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
    audience=models.CharField(max_length=20,choices=[('international','International candidates'),('canadian','Canadian job seekers'),('both','Both audiences')],default='both')
    kind = models.CharField(max_length=12, choices=[('file','Download / résumé access'),('workbook','Personalized workbook download'),('bundle','Bundle')], default='file')
    category=models.CharField(max_length=60,blank=True)
    short_description=models.CharField(max_length=240,blank=True)
    preview_image=models.ImageField(upload_to='career_mobility/previews/',blank=True,storage=PrivateMobilityStorage())
    storefront_order = models.PositiveSmallIntegerField(default=100, help_text="Lower numbers appear first. Products with the same number are ordered by title.")
    preview_editor = models.CharField(max_length=80, blank=True, help_text="Choose an editable demo, use the default for this product, or hide the demo.")
    title = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price_cad = models.DecimalField(max_digits=9,decimal_places=2,default=0)
    canadian_price_cad = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    international_price_cad = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])

    eligible_accounts = models.JSONField(default=list, blank=True)
    starter_quantity = models.PositiveSmallIntegerField(default=0, help_text="Free exports for accounts created after this offer is enabled. Zero disables the offer.")
    starter_since = models.DateTimeField(null=True, blank=True, editable=False)

    def save(self, *args, **kwargs):
        if self.starter_quantity and not self.starter_since:
            from django.utils import timezone
            self.starter_since = timezone.now()
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = {*kwargs['update_fields'], 'starter_since'}
        super().save(*args, **kwargs)

    @property
    def is_card_design_pack(self):
        return self.slug.removeprefix("ptjc-") == "business-card-design-files"

    @property
    def price_for_canadian(self):
        return self.price_for("canadian")

    @property
    def price_for_international(self):
        return self.price_for("international")

    def price_for(self, audience):
        override = self.international_price_cad if audience == "international" else self.canadian_price_cad
        return self.price_cad if override is None else override

    download = models.FileField(upload_to="career_mobility/products/",blank=True, storage=PrivateMobilityStorage())
    is_published = models.BooleanField(default=False)
    @property
    def journal_preview(self):
        from .editable_products import JOURNALS
        key = self.slug.removeprefix("ptjc-")
        return f"career_mobility/product-previews/journals/{key}/cover.jpg" if key in JOURNALS else ""

    @property
    def recovered_cover(self):
        from .recovered_products import FILES
        key = self.slug.removeprefix('ptjc-')
        return f'career_mobility/product-previews/recovered/{key}.jpg' if key in FILES else ''

    @property
    def includes_resume_builder(self):
        from ptjc_resumes.models import ResumeTemplate, ResumeLayoutOffer
        return bool(self.pk and (ResumeTemplate.objects.filter(access_product_id=self.pk,is_enabled=True).exists() or ResumeLayoutOffer.objects.filter(product_id=self.pk,template__is_enabled=True).exists()))
    @property
    def includes_card_builder(self):return self.slug=='international-business-card-builder-access'
    @property
    def has_editable_preview(self):
        from .shop_gallery import editor_key
        return bool(editor_key(self))

    @property
    def is_online_builder(self):return self.includes_resume_builder or self.includes_card_builder
    def __str__(self): return self.title

class StorefrontStudio(models.Model):
    key = models.SlugField(unique=True, editable=False)
    title = models.CharField(max_length=100)
    description = models.CharField(max_length=240, blank=True)
    position = models.PositiveSmallIntegerField(default=10)
    is_visible = models.BooleanField(default=True, help_text="Show this editor in the shop. Direct links and existing purchases still work.")

    class Meta:
        ordering = ("position", "pk")
        verbose_name_plural = "Storefront studios"

    def __str__(self):
        return self.title


class ProductGalleryImage(models.Model):
    product = models.ForeignKey(DigitalProduct, related_name="gallery_images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="career_mobility/previews/gallery/", storage=PrivateMobilityStorage())
    caption = models.CharField(max_length=120, help_text="Describe the page shown. This text also labels the image for screen readers.")
    position = models.PositiveSmallIntegerField(default=10)

    class Meta:
        ordering = ("position", "pk")

    def __str__(self):
        return self.caption


class ProductOrder(models.Model):
    checkout_state=models.CharField(max_length=12,choices=[('pending','Awaiting checkout'),('processing','Payment processing'),('paid','Paid'),('failed','Payment failed'),('expired','Checkout expired')],default='pending')
    list_amount_cents = models.PositiveIntegerField(null=True, blank=True)
    discount_amount_cents = models.PositiveIntegerField(default=0)
    discount = models.ForeignKey('StoreDiscount', null=True, blank=True, on_delete=models.PROTECT)
    checkout_snapshot = models.JSONField(default=list, blank=True)
    checkout_expires_at = models.DateTimeField(null=True, blank=True)
    payment_intent = models.CharField(max_length=255, blank=True)
    amount_cents = models.PositiveIntegerField(null=True,blank=True)
    currency = models.CharField(max_length=3,default="CAD")
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    product = models.ForeignKey(DigitalProduct,on_delete=models.PROTECT)
    stripe_session_id = models.CharField(max_length=255,unique=True)
    paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    @property
    def checkout_amount(self):
        from decimal import Decimal
        return Decimal(self.amount_cents)/100 if self.amount_cents is not None else None


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
    region = models.CharField(max_length=130)
    province = models.CharField(max_length=90, blank=True)
    low_hourly = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    median_hourly = models.DecimalField(max_digits=8, decimal_places=2)
    high_hourly = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    source_url = models.URLField(max_length=500)
    reference_period = models.CharField(max_length=90)
    verified_on = models.DateField()
    is_published = models.BooleanField(default=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['region','province'],name='unique_pt_wage_region_province')]
    def __str__(self):
        return self.region


class CalculatorUsageEvent(models.Model):
    """Anonymous calculator activity only; never store inputs, IPs or user IDs."""
    EVENTS = [
        ('salary_calculator_view', 'Views'),
        ('salary_calculator_start', 'Starts'),
        ('salary_comparison_complete', 'Completed comparisons'),
        ('salary_pdf_download', 'PDF downloads'),
        ('salary_comparison_saved', 'Saved comparisons'),
        ('salary_comparison_returned', 'Saved comparisons reopened'),
    ]
    country = models.CharField(max_length=100, blank=True, editable=False)
    event_id = models.UUIDField(unique=True, editable=False)
    page_id = models.UUIDField(editable=False)
    session_hash = models.CharField(max_length=64, editable=False)
    event = models.CharField(max_length=32, choices=EVENTS, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'calculator usage event'
        verbose_name_plural = 'Calculator usage'
        ordering = ['-created_at']


class InternationalActivity(models.Model):
    ACTIONS = [(x, x.replace('_', ' ').capitalize()) for x in (
        'account_created', 'signed_in', 'signed_out', 'planner_viewed', 'planner_generated', 'planner_saved', 'country_viewed',
        'resources_viewed', 'dashboard_viewed', 'profile_updated', 'checklist_completed',
        'checklist_reopened', 'checklist_downloaded', 'country_guide_downloaded',
        'checkout_started', 'purchase_confirmed', 'product_downloaded')]
    profile = models.ForeignKey(InternationalProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='activity')
    action = models.CharField(max_length=32, choices=ACTIONS)
    visitor_country = models.CharField('Visitor country (IP estimate)',max_length=100,blank=True)
    education_country = models.CharField(max_length=100, blank=True)
    residence_country = models.CharField(max_length=100, blank=True)
    page_country = models.CharField(max_length=100, blank=True)
    destination_province = models.CharField(max_length=100, blank=True)
    subject = models.CharField(max_length=160, blank=True)
    visit_hash = models.CharField(max_length=64, blank=True, editable=False)
    event_key = models.CharField(max_length=120, null=True, blank=True, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'International account activity'


class CountryResourceCollection(models.Model):
    country_slug = models.SlugField(unique=True)
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    products = models.ManyToManyField(DigitalProduct, blank=True, related_name='country_collections')
    bundle_product = models.OneToOneField(DigitalProduct, null=True, blank=True, on_delete=models.SET_NULL, related_name='country_bundle')
    is_published = models.BooleanField(default=False)
    class Meta:
        ordering = ['country_slug']
    def __str__(self):
        return self.title
    def clean(self):
        from django.core.exceptions import ValidationError
        from .country_content import get_country
        if not get_country(self.country_slug):
            raise ValidationError({'country_slug': 'Choose a country supported by the planner.'})

from .store_models import StoreBundleItem, StoreDiscount, StoreGrant, StoreEntitlement


class JournalTemplate(models.Model):
    key = models.SlugField(unique=True, editable=False)
    title = models.CharField(max_length=140)
    subtitle = models.CharField(max_length=240, default="Visit preparation, participation goals and professional learning.")
    default_design = models.CharField(max_length=12, choices=[("editorial", "Editorial"), ("minimal", "Minimal"), ("photo", "Photo")], default="editorial")
    default_colour = models.CharField(max_length=7, default="#76415d")
    content = models.JSONField(default=list, blank=True, help_text="Worksheet content is edited in the sections below.")

    def clean(self):
        import re
        from .editable_products import JOURNALS
        if self.key not in JOURNALS:
            raise __import__("django.core.exceptions", fromlist=["ValidationError"]).ValidationError({"key": "Choose a configured journal."})
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", self.default_colour):
            raise __import__("django.core.exceptions", fromlist=["ValidationError"]).ValidationError({"default_colour": "Enter a hex colour such as #76415d."})

    def __str__(self):
        return self.title


class InternationalSponsor(models.Model):
    sponsor = models.CharField(max_length=100)
    country = models.CharField(max_length=100, blank=True, help_text='Leave blank to show this sponsorship across the International portal.')
    description = models.CharField(max_length=220)
    website = models.URLField()
    enabled = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(default=10)

    class Meta:
        ordering = ('position', 'pk')

    def __str__(self):
        return self.sponsor


class ProductDraft(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(DigitalProduct, on_delete=models.CASCADE)
    data = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)


class ProductActivity(models.Model):
    product = models.ForeignKey(DigitalProduct, on_delete=models.CASCADE)
    event = models.CharField(max_length=32)
    account = models.CharField(max_length=16)
    order = models.ForeignKey(ProductOrder, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name_plural = 'Digital product activity'
        constraints = [models.UniqueConstraint(fields=['order', 'event'], name='product_activity_order_event')]


class StarterUsage(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(DigitalProduct, on_delete=models.CASCADE)
    used = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'product'], name='starter_usage_user_product')]
