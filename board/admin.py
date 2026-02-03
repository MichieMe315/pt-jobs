from datetime import timedelta

from django.contrib import admin, messages
from django.urls import reverse, path
from django.utils import timezone
from django.utils.html import format_html
from django.shortcuts import get_object_or_404, redirect

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


def _admin_change_url(obj) -> str:
    return reverse(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change", args=[obj.pk])


def _model_has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def _set_duplicate_expiry(job, today):
    """
    Duplicated job should never have expiry in the past.
    If a duration field exists, expiry = today + duration.
    Otherwise clamp expiry >= today (if expiry_date exists).
    """
    duration = None
    for cand in ("posting_duration_days", "duration_days"):
        if _model_has_field(job.__class__, cand):
            duration = getattr(job, cand, None)
            break

    if _model_has_field(job.__class__, "expiry_date"):
        if duration:
            job.expiry_date = today + timedelta(days=int(duration))
        else:
            if getattr(job, "expiry_date", None) and job.expiry_date < today:
                job.expiry_date = today


# -----------------------------
# Employer: inline purchased packages + buttons
# -----------------------------

class PurchasedPackageInline(admin.TabularInline):
    model = PurchasedPackage
    extra = 0
    fields = ("package", "credits_granted", "credits_remaining", "purchased_at", "expires_at", "source")
    readonly_fields = ("purchased_at",)


@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    inlines = [PurchasedPackageInline]

    list_display = (
        "id",
        "name",
        "company_name",
        "email",
        "credits",
        "is_approved",
        "login_active",
        "created_at",
    )
    list_display_links = ("id", "name", "company_name")
    search_fields = ("name", "company_name", "email")
    list_filter = ("is_approved", "login_active")
    ordering = ("-created_at",)

    readonly_fields = ("view_employer_jobs", "view_employer_packages")

    def view_employer_jobs(self, obj):
        if not obj or not obj.pk:
            return "-"
        url = reverse("admin:board_job_changelist")
        return format_html(
            '<a class="button" href="{}?employer__id__exact={}">View Employer Jobs</a>',
            url,
            obj.pk,
        )

    view_employer_jobs.short_description = "Jobs"

    def view_employer_packages(self, obj):
        if not obj or not obj.pk:
            return "-"
        url = reverse("admin:board_purchasedpackage_changelist")
        return format_html(
            '<a class="button" href="{}?employer__id__exact={}">View Employer Packages</a>',
            url,
            obj.pk,
        )

    view_employer_packages.short_description = "Packages"

    def get_fieldsets(self, request, obj=None):
        # Show quick links + your normal employer fields (only if they exist)
        preferred = [
            "user",
            "email",
            "name",
            "company_name",
            "company_description",
            "phone",
            "website",
            "location",
            "logo",
            "credits",
            "is_approved",
            "login_active",
        ]
        fields = [f for f in preferred if _model_has_field(self.model, f)]
        return (
            ("Quick links", {"fields": ("view_employer_jobs", "view_employer_packages")}),
            ("Employer", {"fields": tuple(fields)}),
        )


# -----------------------------
# JobSeeker
# -----------------------------

@admin.register(JobSeeker)
class JobSeekerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "first_name",
        "last_name",
        "position_desired",
        "registered_in_canada",
        "require_sponsorship",
        "is_approved",
        "login_active",
        "created_at",
    )
    list_display_links = ("id", "email")
    search_fields = ("email", "first_name", "last_name", "position_desired")
    list_filter = ("registered_in_canada", "require_sponsorship", "is_approved", "login_active")
    ordering = ("-created_at",)


# -----------------------------
# Jobs: duplicate + expiry clamp + title clickable + employer link in job
# -----------------------------

def duplicate_selected_jobs(modeladmin, request, queryset):
    today = timezone.localdate()
    count = 0
    for job in queryset:
        job.pk = None
        if hasattr(job, "views_count"):
            job.views_count = 0
        if hasattr(job, "posting_date"):
            job.posting_date = today
        if hasattr(job, "is_active"):
            job.is_active = False

        _set_duplicate_expiry(job, today)

        job.save()
        count += 1

    modeladmin.message_user(request, f"Duplicated {count} job(s).", level=messages.SUCCESS)


duplicate_selected_jobs.short_description = "Duplicate selected jobs"


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    # Template you already created:
    # templates/admin/board/job/change_form.html
    change_form_template = "admin/board/job/change_form.html"

    actions = [duplicate_selected_jobs]

    list_display = (
        "id",
        "title",
        "employer_link",
        "location",
        "posting_date",
        "expiry_date",
        "is_active",
        "source",
        "duplicate_button",
    )
    # ✅ title clickable (and id too)
    list_display_links = ("id", "title")

    search_fields = ("title", "employer__name", "employer__company_name", "location")
    list_filter = ("is_active", "job_type", "compensation_type", "source")
    ordering = ("-posting_date", "-id")

    # ✅ button on Job change page to open employer profile
    readonly_fields = ("employer_profile_link",)

    def employer_link(self, obj):
        if not obj.employer_id:
            return "-"
        url = reverse("admin:board_employer_change", args=[obj.employer_id])
        return format_html('<a href="{}">{}</a>', url, str(obj.employer))

    employer_link.short_description = "Employer"

    def employer_profile_link(self, obj):
        if not obj or not getattr(obj, "employer_id", None):
            return "-"
        url = reverse("admin:board_employer_change", args=[obj.employer_id])
        return format_html('<a class="button" href="{}">Open Employer Profile</a>', url)

    employer_profile_link.short_description = "Employer Profile"

    # Hide duplicate/legacy fields in admin only (ONLY if they exist)
    def get_exclude(self, request, obj=None):
        exclude = set(super().get_exclude(request, obj) or [])
        hide_if_exists = [
            "application_email",
            "external_apply_url",
            "application_instructions",
            "relocation_assistance_provided",
            "featured",
        ]
        for name in hide_if_exists:
            if _model_has_field(self.model, name):
                exclude.add(name)
        return tuple(exclude)

    # Put the employer profile button at top of the form + keep fields sane
    def get_fieldsets(self, request, obj=None):
        excluded = set(self.get_exclude(request, obj) or [])
        fields = ["employer_profile_link"]

        if _model_has_field(self.model, "employer") and "employer" not in excluded:
            fields.append("employer")

        preferred = [
            "title",
            "description",
            "job_type",
            "compensation_type",
            "min_compensation",
            "max_compensation",
            "compensation_min",
            "compensation_max",
            "location",
            "apply_via",
            "apply_email",
            "apply_url",
            "relocation_assistance",
            "expiry_date",
            "posting_date",
            "is_active",
            "is_featured",
            "source",
            "views_count",
        ]
        for name in preferred:
            if name in excluded:
                continue
            if _model_has_field(self.model, name) and name not in fields:
                fields.append(name)

        return (("Job", {"fields": tuple(fields)}),)

    # --- Duplicate button + URL ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:job_id>/duplicate/",
                self.admin_site.admin_view(self.duplicate_job_view),
                name="board_job_duplicate",
            ),
        ]
        return custom_urls + urls

    def duplicate_button(self, obj):
        url = reverse("admin:board_job_duplicate", args=[obj.pk])
        return format_html('<a class="button" href="{}">Duplicate</a>', url)

    duplicate_button.short_description = "Duplicate"

    def duplicate_job_view(self, request, job_id: int):
        job = get_object_or_404(Job, pk=job_id)
        today = timezone.localdate()

        job.pk = None
        if hasattr(job, "views_count"):
            job.views_count = 0
        if hasattr(job, "posting_date"):
            job.posting_date = today
        if hasattr(job, "is_active"):
            job.is_active = False

        _set_duplicate_expiry(job, today)

        job.save()
        self.message_user(request, "Job duplicated (posting_date=today; expiry clamped; inactive).", level=messages.SUCCESS)
        return redirect(_admin_change_url(job))


# -----------------------------
# The rest
# -----------------------------

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "jobseeker", "created_at")
    list_display_links = ("id",)
    search_fields = ("job__title", "jobseeker__email")
    ordering = ("-created_at",)


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("id", "jobseeker", "created_at")
    list_display_links = ("id",)
    search_fields = ("jobseeker__email",)
    ordering = ("-created_at",)


@admin.register(PostingPackage)
class PostingPackageAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "duration_days", "credits", "price", "is_active", "order")
    list_display_links = ("id", "code", "name")
    search_fields = ("code", "name")
    list_filter = ("is_active",)
    ordering = ("order", "id")


@admin.register(PurchasedPackage)
class PurchasedPackageAdmin(admin.ModelAdmin):
    list_display = ("id", "employer", "package", "credits_granted", "credits_remaining", "purchased_at", "expires_at", "source")
    list_display_links = ("id",)
    search_fields = ("employer__email", "employer__name", "package__name", "package__code")
    list_filter = ("source",)
    ordering = ("-purchased_at", "-id")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "employer", "amount", "currency", "processor", "status", "order_date", "processor_reference", "created_at")
    list_display_links = ("id",)
    search_fields = ("employer__email", "processor_reference")
    list_filter = ("processor", "status", "currency")
    ordering = ("-created_at", "-id")


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "kind", "value", "is_active", "start_date", "end_date", "max_uses", "uses", "applicable_package")
    list_display_links = ("id", "code")
    search_fields = ("code", "name")
    list_filter = ("kind", "is_active", "start_date", "end_date")
    ordering = ("-created_at", "-id")


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "site_name", "contact_email", "google_analytics_id")
    list_display_links = ("id", "site_name")


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "name", "subject", "is_enabled", "created_at")
    list_display_links = ("id", "key", "name")
    search_fields = ("key", "name", "subject")
    list_filter = ("is_enabled",)
    ordering = ("-created_at", "-id")


@admin.register(WidgetTemplate)
class WidgetTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    list_display_links = ("id", "name", "slug")
    search_fields = ("name", "slug")
    ordering = ("-created_at", "-id")


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "q", "location", "active", "created_at")
    list_display_links = ("id",)
    search_fields = ("email", "q", "location")
    list_filter = ("active",)
    ordering = ("-created_at", "-id")


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "gateway_name", "currency", "is_active", "use_stripe", "use_paypal", "created_at")
    list_display_links = ("id", "gateway_name")
    search_fields = ("gateway_name",)
    list_filter = ("is_active", "use_stripe", "use_paypal", "currency")
    ordering = ("-created_at", "-id")


@admin.register(SocialPostingConfig)
class SocialPostingConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "enabled", "facebook_page_id", "instagram_business_id", "reddit_subreddit", "created_at")
    list_display_links = ("id",)
    list_filter = ("enabled",)
    ordering = ("-created_at", "-id")


@admin.register(WebhookConfig)
class WebhookConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "enabled", "url", "created_at")
    list_display_links = ("id",)
    list_filter = ("enabled",)
    ordering = ("-created_at", "-id")
