from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from . import models as m

# --- Inline(s)

class PurchasedPackageInline(admin.TabularInline):
    model = m.PurchasedPackage
    extra = 0
    readonly_fields = ("credits_total", "purchased_at", "expires_at")


# --- PostingPackage

@admin.register(m.PostingPackage)
class PostingPackageAdmin(ImportExportModelAdmin):
    list_display = ("name", "code", "duration_days", "max_jobs", "price_cents", "is_active", "order")
    list_editable = ("duration_days", "max_jobs", "price_cents", "is_active", "order")
    search_fields = ("name", "code")
    ordering = ("order", "name")


# --- Employer

@admin.register(m.Employer)
class EmployerAdmin(ImportExportModelAdmin):
    list_display = ("company_name", "name", "email", "location", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at")
    search_fields = ("company_name", "name", "email", "location")
    inlines = [PurchasedPackageInline]


# --- JobSeeker

@admin.register(m.JobSeeker)
class JobSeekerAdmin(ImportExportModelAdmin):
    list_display = ("first_name", "last_name", "email", "current_location", "is_approved", "created_at")
    list_filter = ("is_approved", "created_at", "registration_status", "opportunity_type", "open_to_relocation")
    search_fields = ("first_name", "last_name", "email", "current_location")


# --- Job

@admin.register(m.Job)
class JobAdmin(ImportExportModelAdmin):
    list_display = (
        "title",
        "employer",
        "location",
        "job_type",
        "compensation_type",
        "posting_date",
        "expiry_date",
        "is_active",
        "featured",
    )
    list_filter = ("is_active", "featured", "job_type", "compensation_type", "posting_date", "expiry_date")
    search_fields = ("title", "employer__company_name", "employer__name", "location", "description")
    autocomplete_fields = ("employer",)
    date_hierarchy = "posting_date"


# --- PurchasedPackage

@admin.register(m.PurchasedPackage)
class PurchasedPackageAdmin(ImportExportModelAdmin):
    list_display = ("employer", "package", "credits_total", "credits_used", "purchased_at", "expires_at")
    list_filter = ("purchased_at", "expires_at", "package")
    search_fields = ("employer__company_name", "employer__name", "package__name")


# --- JobAlert

@admin.register(m.JobAlert)
class JobAlertAdmin(ImportExportModelAdmin):
    list_display = ("email", "q", "location", "created_at")
    list_filter = ("created_at",)
    search_fields = ("email", "q", "location")


# --- Invoice

@admin.register(m.Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
    list_display = ("id", "employer", "amount_cents", "created_at")
    list_filter = ("created_at",)
    search_fields = ("employer__company_name", "employer__name")
