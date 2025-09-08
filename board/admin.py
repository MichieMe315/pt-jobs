from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from . import models as m
from . import resources as r


# ----- Employers -----
@admin.register(m.Employer)
class EmployerAdmin(ImportExportModelAdmin):
    resource_classes = [r.EmployerResource]
    list_display = (
        "__str__",
        "email",
        "location",
        "is_approved",
        "posting_package",
        "credits_total",
        "credits_used",
        "credits_left",
    )
    list_filter = ("is_approved", "posting_package")
    search_fields = ("company_name", "name", "email", "location")
    readonly_fields = ("credits_left",)
    fieldsets = (
        ("Identity", {"fields": ("user", "email", "name", "company_name", "location")}),
        ("Contact", {"fields": ("phone", "website")}),
        ("Branding", {"fields": ("logo", "description")}),
        ("Status", {"fields": ("is_approved",)}),
        ("Package & Credits", {"fields": ("posting_package", "credits_total", "credits_used", "credits_left")}),
    )


# ----- Job Seekers -----
@admin.register(m.JobSeeker)
class JobSeekerAdmin(ImportExportModelAdmin):
    resource_classes = [r.JobSeekerResource]
    list_display = (
        "full_name",
        "email",
        "registration_status",
        "opportunity_type",
        "current_location",
        "is_approved",
        "created_at",
    )
    list_filter = ("registration_status", "opportunity_type", "is_approved", "created_at")
    search_fields = ("first_name", "last_name", "email", "current_location")


# ----- (Keep other admin models functional) -----
@admin.register(m.PostingPackage)
class PostingPackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "code",
        "price_display",
        "duration_days",
        "max_jobs",
        "is_featured_package",
        "is_active",
        "order",
    )
    list_filter = ("is_active", "is_featured_package")
    search_fields = ("name", "code", "description")


@admin.register(m.Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "employer",
        "location",
        "job_type",
        "compensation_type",
        "posting_date",
        "expiry_date",
        "featured",
        "is_active",
    )
    list_filter = ("job_type", "compensation_type", "featured", "is_active", "posting_date")
    search_fields = ("title", "description", "location", "employer__company_name", "employer__name")
    autocomplete_fields = ("employer",)
    fieldsets = (
        ("Basics", {"fields": ("employer", "title", "description", "location")}),
        ("Compensation", {"fields": ("compensation_type", "salary_min", "salary_max", "percent_split")}),
        ("Meta", {"fields": ("job_type", "relocation_assistance", "posting_date", "expiry_date", "featured", "is_active")}),
        ("Apply", {"fields": ("application_email", "external_apply_url")}),
        ("Counters", {"fields": ("view_count", "application_count")}),
    )
    readonly_fields = ("view_count", "application_count")


@admin.register(m.JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ("email", "q", "location", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("email", "q", "location")


@admin.register(m.Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("job", "name", "email", "created_at")
    list_filter = ("created_at", "job")
    search_fields = ("name", "email", "job__title")
    readonly_fields = ("job", "name", "email", "resume", "cover_letter", "created_at")


@admin.register(m.JobView)
class JobViewAdmin(admin.ModelAdmin):
    list_display = ("job", "created_at", "is_apply_click")
    list_filter = ("is_apply_click", "created_at")
    search_fields = ("job__title", "job__employer__company_name")


@admin.register(m.Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ("employer", "package", "quantity", "credits_total", "purchased_at", "expires_at")
    list_filter = ("purchased_at", "package")
    search_fields = ("employer__company_name", "employer__name", "package__name")


@admin.register(m.Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("employer", "external_id", "amount_cents", "paid", "created_at")
    list_filter = ("paid", "created_at")
    search_fields = ("employer__company_name", "employer__name", "external_id")
