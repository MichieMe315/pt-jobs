from django.contrib import admin, messages
from django.urls import reverse, path
from django.utils.html import format_html
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect
from datetime import timedelta

from .models import (
    Employer,
    JobSeeker,
    Job,
    Application,
    Resume,
    PostingPackage,
    PurchasedPackage,
    Invoice,
    DiscountCode,
    SiteSettings,
    EmailTemplate,
    WidgetTemplate,
    JobAlert,
    PaymentGatewayConfig,
    SocialPostingConfig,
    WebhookConfig,
)


def _admin_change_url(obj):
    return reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])


def _set_duplicate_expiry(job, today):
    """
    Ensures duplicated jobs NEVER have expiry in the past.
    If a duration field exists, expiry = today + duration.
    Otherwise clamp expiry >= today.
    """
    duration = None
    for cand in ("posting_duration_days", "duration_days"):
        try:
            job._meta.get_field(cand)
            duration = getattr(job, cand, None)
            break
        except Exception:
            continue

    try:
        job._meta.get_field("expiry_date")
        if duration:
            job.expiry_date = today + timedelta(days=int(duration))
        else:
            if job.expiry_date and job.expiry_date < today:
                job.expiry_date = today
    except Exception:
        pass


@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "company_name", "email", "credits", "is_approved", "login_active", "created_at")
    search_fields = ("name", "company_name", "email")
    list_filter = ("is_approved", "login_active")
    ordering = ("-created_at",)


@admin.register(JobSeeker)
class JobSeekerAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "first_name", "last_name", "position_desired",
                    "registered_in_canada", "require_sponsorship", "is_approved",
                    "login_active", "created_at")
    search_fields = ("email", "first_name", "last_name")
    list_filter = ("registered_in_canada", "require_sponsorship", "is_approved", "login_active")
    ordering = ("-created_at",)


def duplicate_selected_jobs(modeladmin, request, queryset):
    today = timezone.localdate()
    count = 0

    for job in queryset:
        job.pk = None
        job.views_count = 0
        job.posting_date = today
        job.is_active = False
        _set_duplicate_expiry(job, today)
        job.save()
        count += 1

    modeladmin.message_user(request, f"Duplicated {count} job(s).", level=messages.SUCCESS)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    change_form_template = "admin/board/job/change_form.html"
    actions = [duplicate_selected_jobs]

    list_display = ("id", "title", "employer_link", "location", "posting_date",
                    "expiry_date", "is_active", "duplicate_button")
    search_fields = ("title", "employer__company_name", "location")
    list_filter = ("is_active", "job_type", "compensation_type")
    ordering = ("-posting_date", "-id")

    # hide duplicate admin-only fields
    exclude = (
        "application_email",
        "external_apply_url",
        "application_instructions",
        "relocation_assistance_provided",
        "featured",
    )

    def employer_link(self, obj):
        url = reverse("admin:board_employer_change", args=[obj.employer_id])
        return format_html('<a href="{}">{}</a>', url, obj.employer)

    employer_link.short_description = "Employer"

    # duplicate route
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("<int:job_id>/duplicate/",
                 self.admin_site.admin_view(self.duplicate_job_view),
                 name="board_job_duplicate"),
        ]
        return custom + urls

    def duplicate_button(self, obj):
        url = reverse("admin:board_job_duplicate", args=[obj.pk])
        return format_html('<a class="button" href="{}">Duplicate</a>', url)

    duplicate_button.short_description = "Duplicate"

    def duplicate_job_view(self, request, job_id):
        job = get_object_or_404(Job, pk=job_id)
        today = timezone.localdate()

        job.pk = None
        job.views_count = 0
        job.posting_date = today
        job.is_active = False
        _set_duplicate_expiry(job, today)
        job.save()

        self.message_user(request, "Job duplicated (expiry clamped).", level=messages.SUCCESS)
        return redirect(_admin_change_url(job))


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "jobseeker", "created_at")
    ordering = ("-created_at",)


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("id", "jobseeker", "created_at")
    ordering = ("-created_at",)


@admin.register(PostingPackage)
class PostingPackageAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "duration_days", "credits", "price", "is_active", "order")
    list_filter = ("is_active",)


@admin.register(PurchasedPackage)
class PurchasedPackageAdmin(admin.ModelAdmin):
    list_display = ("id", "employer", "package", "credits_remaining", "expires_at")
    ordering = ("-purchased_at",)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "employer", "amount", "status", "created_at")


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "kind", "value", "is_active")


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "site_name", "google_analytics_id")


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "subject", "is_enabled")


@admin.register(WidgetTemplate)
class WidgetTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug")


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "active")


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "gateway_name", "is_active")


@admin.register(SocialPostingConfig)
class SocialPostingConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "enabled")


@admin.register(WebhookConfig)
class WebhookConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "enabled")
