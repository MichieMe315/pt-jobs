from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Employer,
    JobSeeker,
    PostingPackage,
    PurchasedPackage,
    Job,
    Resume,
    Application,
    SavedJob,
    JobAlert,
    EmailTemplate,
    Invoice,
)


# ---------- Inlines ----------
class PurchasedPackageInline(admin.TabularInline):
    model = PurchasedPackage
    extra = 0
    autocomplete_fields = ("package",)
    readonly_fields = ("purchased_at",)
    fields = ("package", "credits_total", "credits_used", "expires_at", "purchased_at")


# ---------- Employers ----------
@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ("company_name", "name", "email", "is_approved", "jobs_count")
    list_display_links = ("company_name", "name")
    list_editable = ("is_approved",)
    search_fields = ("company_name", "name", "email", "user__username", "user__email")
    list_filter = ("is_approved",)
    inlines = [PurchasedPackageInline]

    @admin.display(description="Jobs")
    def jobs_count(self, obj: Employer) -> int:
        try:
            return obj.jobs.count()
        except Exception:
            return 0


# ---------- Job Seekers ----------
@admin.register(JobSeeker)
class JobSeekerAdmin(admin.ModelAdmin):
    list_display = ("full_name_display", "email", "is_approved")
    list_display_links = ("full_name_display",)
    list_editable = ("is_approved",)
    search_fields = (
        "first_name",
        "last_name",
        "email",
        "user__username",
        "user__email",
        "current_location",
    )
    list_filter = ("is_approved", "open_to_relocation", "need_sponsorship", "seeking_immigration")

    @admin.display(description="Name")
    def full_name_display(self, obj: JobSeeker) -> str:
        return obj.full_name or obj.email or ""


# ---------- Packages ----------
@admin.register(PostingPackage)
class PostingPackageAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "price_display_admin", "max_jobs", "duration_days", "package_expires_days", "is_active", "order")
    list_editable = ("is_active", "order")
    search_fields = ("name", "code", "description")
    list_filter = ("is_active",)

    @admin.display(description="Price")
    def price_display_admin(self, obj: PostingPackage) -> str:
        return obj.price_display


@admin.register(PurchasedPackage)
class PurchasedPackageAdmin(admin.ModelAdmin):
    list_display = (
        "employer",
        "package",
        "purchase_price_display_admin",
        "credits_progress",
        "expires_at",
        "purchased_at",
    )
    autocomplete_fields = ("employer", "package")
    readonly_fields = ("purchased_at",)
    list_filter = ("package", "expires_at")
    search_fields = ("employer__company_name", "employer__name", "employer__email")

    @admin.display(description="Price")
    def purchase_price_display_admin(self, obj: PurchasedPackage) -> str:
        return obj.purchase_price_display

    @admin.display(description="Credits")
    def credits_progress(self, obj: PurchasedPackage) -> str:
        return f"{obj.credits_used}/{obj.credits_total} (Left: {obj.credits_left})"


# ---------- Jobs ----------
@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "employer",
        "job_type",
        "compensation_type",
        "salary_min",
        "salary_max",
        "posting_date",
        "expiry_date",
        "is_active",
    )
    list_editable = ("is_active",)
    list_filter = ("is_active", "job_type", "compensation_type", "relocation_assistance_provided", "featured")
    search_fields = ("title", "description", "location", "employer__company_name", "employer__name")
    autocomplete_fields = ("employer",)


# ---------- Resumes / Applications / Saved ----------
@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("jobseeker", "title", "uploaded_at")
    search_fields = ("title", "jobseeker__first_name", "jobseeker__last_name", "jobseeker__email")
    autocomplete_fields = ("jobseeker",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("job", "jobseeker", "email", "created_at")
    list_filter = ("created_at",)
    search_fields = ("job__title", "jobseeker__first_name", "jobseeker__last_name", "email")
    autocomplete_fields = ("job", "jobseeker")


@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ("jobseeker", "job", "created_at")
    list_filter = ("created_at",)
    search_fields = ("job__title", "jobseeker__first_name", "jobseeker__last_name")
    autocomplete_fields = ("jobseeker", "job")


# ---------- Alerts / Templates / Invoices ----------
@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ("email", "q", "location", "active", "created_at")
    list_filter = ("active", "created_at")
    search_fields = ("email", "q", "location")


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("slug", "subject", "is_active")
    list_editable = ("is_active",)
    search_fields = ("slug", "subject", "body")
    list_filter = ("is_active",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("employer", "amount_display_admin", "external_reference", "created_at")
    search_fields = ("employer__company_name", "employer__name", "external_reference")
    list_filter = ("created_at",)

    @admin.display(description="Amount")
    def amount_display_admin(self, obj: Invoice) -> str:
        return obj.amount_display

# --- Payments & Discounts in Admin -------------------------------------------
from django.contrib import admin

try:
    from .models import PaymentGatewayConfig, DiscountCode
except Exception:
    PaymentGatewayConfig = None
    DiscountCode = None

if PaymentGatewayConfig:
    @admin.register(PaymentGatewayConfig)
    class PaymentGatewayConfigAdmin(admin.ModelAdmin):
        list_display = (
            "name",
            "is_active",
            "use_stripe",
            "use_paypal",
            "paypal_mode",
            "updated_at",
        )
        list_filter = ("is_active", "use_stripe", "use_paypal", "paypal_mode")
        search_fields = ("name", "stripe_public_key", "paypal_client_id")
        list_editable = ("is_active", "use_stripe", "use_paypal", "paypal_mode")

if DiscountCode:
    @admin.register(DiscountCode)
    class DiscountCodeAdmin(admin.ModelAdmin):
        list_display = (
            "code",
            "type",
            "amount_cents",
            "percent",
            "is_active",
            "starts_at",
            "ends_at",
            "uses",
            "max_uses",
        )
        list_filter = ("is_active", "type")
        search_fields = ("code", "name", "notes")
        list_editable = ("is_active",)

