# board/admin.py
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse, NoReverseMatch
from django.utils import timezone
from django.utils.html import format_html

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


def _model_has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def _default_from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", None) or "info@physiotherapyjobscanada.ca"


def _site_login_url() -> str:
    """
    Stable: do not require request object from admin actions/save_model.
    """
    base = (
        getattr(settings, "SITE_URL", None)
        or getattr(settings, "BASE_URL", None)
        or "https://physiotherapyjobscanada.ca"
    )
    return f"{str(base).rstrip('/')}/login/"


def _send_approval_email(to_email: str, subject: str, body: str) -> None:
    # Keep admin stable even if email sending fails
    send_mail(subject, body, _default_from_email(), [to_email], fail_silently=True)


def _render_email_template(key: str, context: dict) -> tuple[str, str] | None:
    """
    EmailTemplate model has:
      key, name, subject, html, is_enabled, created_at
    """
    tmpl = EmailTemplate.objects.filter(key=key, is_enabled=True).first()
    if not tmpl:
        return None

    subject = (getattr(tmpl, "subject", "") or "").strip()
    body = (getattr(tmpl, "html", "") or "").strip()
    if not subject or not body:
        return None

    # simple {{ token }} replacement (NOT Django template rendering)
    for k, v in context.items():
        subject = subject.replace(f"{{{{{k}}}}}", str(v))
        body = body.replace(f"{{{{{k}}}}}", str(v))

    return subject.strip(), body.strip()


def _send_employer_approved_email(employer: Employer) -> bool:
    email = (getattr(employer, "email", "") or "") or (
        employer.user.email if getattr(employer, "user_id", None) else ""
    )
    if not email:
        return False

    rendered = _render_email_template(
        "employer_approved",
        {
            "email": email,
            "company_name": getattr(employer, "company_name", ""),
            "login_url": _site_login_url(),
        },
    )
    if rendered:
        subject, body = rendered
    else:
        subject = "Your employer account is approved"
        body = (
            "Your employer account on Physiotherapy Jobs Canada has been approved.\n\n"
            f"Log in: {_site_login_url()}\n\n"
            "— Physiotherapy Jobs Canada"
        )

    _send_approval_email(email, subject, body)
    return True


def _send_jobseeker_approved_email(js: JobSeeker) -> bool:
    email = (getattr(js, "email", "") or "") or (js.user.email if getattr(js, "user_id", None) else "")
    if not email:
        return False

    rendered = _render_email_template(
        "jobseeker_approved",
        {
            "email": email,
            "first_name": getattr(js, "first_name", ""),
            "last_name": getattr(js, "last_name", ""),
            "login_url": _site_login_url(),
        },
    )
    if rendered:
        subject, body = rendered
    else:
        subject = "Your job seeker account is approved"
        body = (
            "Your job seeker account on Physiotherapy Jobs Canada has been approved.\n\n"
            f"Log in: {_site_login_url()}\n\n"
            "— Physiotherapy Jobs Canada"
        )

    _send_approval_email(email, subject, body)
    return True


def _set_duplicate_expiry(job: Job, today):
    """
    Duplicate job should have expiry recalculated safely.
    Uses SiteSettings.posting_duration_days if available.
    """
    duration_days = None
    ss = SiteSettings.objects.first()
    if ss and getattr(ss, "posting_duration_days", None):
        try:
            duration_days = int(ss.posting_duration_days)
        except Exception:
            duration_days = None

    if _model_has_field(Job, "expiry_date"):
        if duration_days:
            job.expiry_date = today + timedelta(days=duration_days)
        else:
            if getattr(job, "expiry_date", None) and job.expiry_date < today:
                job.expiry_date = today


# ---------------------------
# Inlines
# ---------------------------

class PurchasedPackageInline(admin.TabularInline):
    model = PurchasedPackage
    extra = 0

    def get_fields(self, request, obj=None):
        # Prevent admin 500s if production schema differs from local.
        wanted = ("package", "credits_granted", "credits_remaining", "purchased_at", "expires_at", "source")
        return [f for f in wanted if _model_has_field(PurchasedPackage, f)]

    def get_readonly_fields(self, request, obj=None):
        wanted = ("purchased_at",)
        return [f for f in wanted if _model_has_field(PurchasedPackage, f)]


# ---------------------------
# Approval actions (bulk)
# ---------------------------

def approve_selected_employers(modeladmin, request, queryset):
    updated = 0
    emailed = 0

    for employer in queryset:
        if getattr(employer, "is_approved", False):
            continue

        Employer.objects.filter(pk=employer.pk).update(
            is_approved=True,
            login_active=True,
            approved_at=timezone.now(),
        )
        updated += 1

        if _send_employer_approved_email(employer):
            emailed += 1

    modeladmin.message_user(
        request,
        f"Approved {updated} employer(s). Sent {emailed} approval email(s).",
        level=messages.SUCCESS,
    )


approve_selected_employers.short_description = "Approve selected employers (and email them)"


def approve_selected_jobseekers(modeladmin, request, queryset):
    updated = 0
    emailed = 0

    for js in queryset:
        if getattr(js, "is_approved", False):
            continue

        JobSeeker.objects.filter(pk=js.pk).update(
            is_approved=True,
            login_active=True,
            approved_at=timezone.now(),
        )
        updated += 1

        if _send_jobseeker_approved_email(js):
            emailed += 1

    modeladmin.message_user(
        request,
        f"Approved {updated} job seeker(s). Sent {emailed} approval email(s).",
        level=messages.SUCCESS,
    )


approve_selected_jobseekers.short_description = "Approve selected job seekers (and email them)"


# ---------------------------
# Employer / JobSeeker admins
# ---------------------------

@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    inlines = [PurchasedPackageInline]
    actions = [approve_selected_employers]

    list_display = (
        "id",
        "company_name",
        "email",
        "location",
        "credits",
        "is_approved",
        "login_active",
        "created_at",
    )
    list_display_links = ("id", "company_name", "email")
    search_fields = ("company_name", "name", "email", "location")
    list_filter = ("is_approved", "login_active")
    # Newest signups first; unapproved records win only when timestamps match.
    ordering = ("-created_at", "is_approved", "-id")

    # Buttons
    readonly_fields = ("view_employer_jobs", "view_employer_packages")

    def get_fieldsets(self, request, obj=None):
        base = list(super().get_fieldsets(request, obj))
        quick = ("Quick Actions", {"fields": ("view_employer_jobs", "view_employer_packages")})
        if base and base[0][0] == "Quick Actions":
            return tuple(base)
        return tuple([quick] + base)

    def view_employer_jobs(self, obj):
        if not obj or not obj.pk:
            return "-"
        try:
            url = reverse("admin:board_job_changelist")
        except NoReverseMatch:
            return "-"
        return format_html(
            '<a class="button" href="{}?employer__id__exact={}">View Employer Jobs</a>',
            url,
            obj.pk,
        )

    view_employer_jobs.short_description = "Jobs"

    def view_employer_packages(self, obj):
        if not obj or not obj.pk:
            return "-"
        try:
            url = reverse("admin:board_purchasedpackage_changelist")
        except NoReverseMatch:
            return "-"
        return format_html(
            '<a class="button" href="{}?employer__id__exact={}">View Employer Packages</a>',
            url,
            obj.pk,
        )

    view_employer_packages.short_description = "Packages"

    def save_model(self, request, obj, form, change):
        """
        CONTRACT: When admin approves, email must be sent to the user.
        Covers approving inside the employer profile (not just bulk action).
        """
        was_approved = False
        if change and obj and obj.pk:
            prev = Employer.objects.filter(pk=obj.pk).only("is_approved").first()
            was_approved = bool(getattr(prev, "is_approved", False)) if prev else False

        super().save_model(request, obj, form, change)

        now_approved = bool(getattr(obj, "is_approved", False))
        if change and (not was_approved) and now_approved:
            updates = {}
            if _model_has_field(Employer, "login_active"):
                updates["login_active"] = True
            if _model_has_field(Employer, "approved_at"):
                updates["approved_at"] = timezone.now()
            if updates:
                Employer.objects.filter(pk=obj.pk).update(**updates)

            sent = _send_employer_approved_email(obj)
            if sent:
                self.message_user(request, "Approval email sent to employer.", level=messages.SUCCESS)
            else:
                self.message_user(
                    request,
                    "Employer approved, but no email address found to send approval email.",
                    level=messages.WARNING,
                )


@admin.register(JobSeeker)
class JobSeekerAdmin(admin.ModelAdmin):
    actions = [approve_selected_jobseekers]

    list_display = (
        "id",
        "email",
        "first_name",
        "last_name",
        "position_desired",
        "current_location",
        "registered_in_canada",
        "require_sponsorship",
        "is_approved",
        "login_active",
        "created_at",
    )
    list_display_links = ("id", "email", "first_name")
    search_fields = ("email", "first_name", "last_name", "position_desired", "current_location")
    list_filter = ("registered_in_canada", "require_sponsorship", "is_approved", "login_active")
    # Newest signups first; unapproved records win only when timestamps match.
    ordering = ("-created_at", "is_approved", "-id")

    def save_model(self, request, obj, form, change):
        """
        CONTRACT: When admin approves, email must be sent to the user.
        Covers approving inside the job seeker profile.
        """
        was_approved = False
        if change and obj and obj.pk:
            prev = JobSeeker.objects.filter(pk=obj.pk).only("is_approved").first()
            was_approved = bool(getattr(prev, "is_approved", False)) if prev else False

        super().save_model(request, obj, form, change)

        now_approved = bool(getattr(obj, "is_approved", False))
        if change and (not was_approved) and now_approved:
            updates = {}
            if _model_has_field(JobSeeker, "login_active"):
                updates["login_active"] = True
            if _model_has_field(JobSeeker, "approved_at"):
                updates["approved_at"] = timezone.now()
            if updates:
                JobSeeker.objects.filter(pk=obj.pk).update(**updates)

            sent = _send_jobseeker_approved_email(obj)
            if sent:
                self.message_user(request, "Approval email sent to job seeker.", level=messages.SUCCESS)
            else:
                self.message_user(
                    request,
                    "Job seeker approved, but no email address found to send approval email.",
                    level=messages.WARNING,
                )


# ---------------------------
# Jobs (duplicate action + admin button URL)
# ---------------------------

def duplicate_selected_jobs(modeladmin, request, queryset):
    today = timezone.localdate()
    count = 0

    for job in queryset:
        job.pk = None
        job.posting_date = today
        job.is_active = False  # duplicate starts as draft/inactive

        if hasattr(job, "views_count"):
            job.views_count = 0

        _set_duplicate_expiry(job, today)
        job.save()
        count += 1

    modeladmin.message_user(request, f"Duplicated {count} job(s).", level=messages.SUCCESS)


duplicate_selected_jobs.short_description = "Duplicate selected jobs"


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
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
    )
    list_display_links = ("id", "title")
    search_fields = ("title", "employer__company_name", "employer__name", "location")
    list_filter = ("is_active", "job_type", "compensation_type", "source")
    ordering = ("-posting_date", "-id")

    def employer_link(self, obj):
        if not getattr(obj, "employer_id", None):
            return "-"
        url = reverse("admin:board_employer_change", args=[obj.employer_id])
        return format_html('<a href="{}">{}</a>', url, str(obj.employer))

    employer_link.short_description = "Employer"

    def get_exclude(self, request, obj=None):
        """
        CONTRACT: keep only the canonical job fields.
        Hide duplicate/legacy fields if they exist (admin-only UI change).
        """
        exclude = list(super().get_exclude(request, obj) or [])

        # Duplicates you showed:
        for field_name in ("relocation_assistance_provided", "featured"):
            if _model_has_field(Job, field_name) and field_name not in exclude:
                exclude.append(field_name)

        # Extra apply/application fields (legacy duplicates in some builds)
        for field_name in ("application_email", "external_apply_url", "application_instructions"):
            if _model_has_field(Job, field_name) and field_name not in exclude:
                exclude.append(field_name)

        return exclude

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/duplicate/",
                self.admin_site.admin_view(self.duplicate_job_view),
                name="board_job_duplicate",
            ),
        ]
        return custom + urls

    def duplicate_job_view(self, request, object_id):
        today = timezone.localdate()
        original = get_object_or_404(Job, pk=object_id)

        original.pk = None
        original.posting_date = today
        original.is_active = False

        if hasattr(original, "views_count"):
            original.views_count = 0

        _set_duplicate_expiry(original, today)
        original.save()

        self.message_user(request, "Job duplicated (new draft created).", level=messages.SUCCESS)
        return redirect("admin:board_job_change", original.pk)


# ---------------------------
# Remaining model admins
# ---------------------------

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "jobseeker", "created_at")
    list_display_links = ("id", "job")
    search_fields = ("job__title", "jobseeker__email", "jobseeker__first_name", "jobseeker__last_name")
    list_filter = ("created_at",)
    ordering = ("-created_at", "-id")


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("id", "jobseeker", "title", "created_at")
    list_display_links = ("id", "jobseeker", "title")
    search_fields = ("jobseeker__email", "title")
    ordering = ("-created_at", "-id")


@admin.register(PostingPackage)
class PostingPackageAdmin(admin.ModelAdmin):

    def get_list_display(self, request):
        base = [
            "id",
            "code",
            "name",
            "credits",
            "duration_days",
            "price_cents",
            "is_active",
            "order",
            "package_expires_days",
        ]
        return tuple([f for f in base if _model_has_field(PostingPackage, f)])

    def get_list_filter(self, request):
        base = ["is_active"]
        if _model_has_field(PostingPackage, "allows_featured"):
            base.append("allows_featured")
        return tuple(base)

    list_display_links = ("id", "code", "name")
    search_fields = ("code", "name")
    ordering = ("order", "name", "id")


@admin.register(PurchasedPackage)
class PurchasedPackageAdmin(admin.ModelAdmin):
    def get_list_display(self, request):
        base = ["id", "employer", "package", "credits_granted", "credits_remaining", "purchased_at"]
        if _model_has_field(PurchasedPackage, "expires_at"):
            base.append("expires_at")
        if _model_has_field(PurchasedPackage, "source"):
            base.append("source")
        return tuple(base)

    list_display_links = ("id", "employer", "package")
    search_fields = ("employer__company_name", "package__name")
    list_filter = ("package", "purchased_at")
    ordering = ("-purchased_at", "-id")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "employer_link", "amount_display", "currency", "processor", "status", "order_date", "discount_code")
    list_display_links = ("id", "employer_link")
    search_fields = ("employer__company_name", "processor_reference", "discount_code")
    list_filter = ("status", "processor", "currency")
    ordering = ("-order_date", "-id")

    def employer_link(self, obj):
        if not getattr(obj, "employer_id", None):
            return "-"
        url = reverse("admin:board_employer_change", args=[obj.employer_id])
        return format_html('<a href="{}">{}</a>', url, str(obj.employer))

    employer_link.short_description = "Employer"

    def amount_display(self, obj):
        amt = getattr(obj, "amount", None)
        if amt is None:
            return "-"
        try:
            d = (Decimal(int(amt)) / Decimal("100")).quantize(Decimal("0.01"))
            return f"{d}"
        except Exception:
            return str(amt)

    amount_display.short_description = "Amount"


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "kind", "value", "is_active", "start_date", "end_date", "max_uses", "uses", "created_at")
    list_display_links = ("id", "code")
    search_fields = ("code", "name")
    list_filter = ("is_active", "kind")

    def get_list_display(self, request):
        base = ["id", "code", "kind", "value", "is_active", "start_date", "end_date", "max_uses", "uses", "created_at"]
        return tuple([f for f in base if _model_has_field(DiscountCode, f)])

    def get_ordering(self, request):
        # Prefer created_at if present; otherwise fall back safely
        if _model_has_field(DiscountCode, "created_at"):
            return ("-created_at", "-id")
        return ("-id",)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "site_name", "google_analytics_id", "posting_duration_days")
    list_display_links = ("id", "site_name")
    search_fields = ("site_name", "google_analytics_id")
    ordering = ("-id",)
    fieldsets = (
        ("Site", {"fields": ("site_name", "contact_email", "posting_duration_days")}),
        ("Homepage hero", {"fields": ("hero_image", "hero_title", "hero_subtitle")}),
        ("Branding", {"fields": ("branding_logo", "branding_favicon", "branding_primary_color", "branding_secondary_color")}),
        ("Social links", {
            "fields": ("facebook_url", "instagram_url", "linkedin_url", "twitter_url", "reddit_url"),
            "description": "Add full profile URLs here. The footer buttons appear automatically when a URL is present.",
        }),
        ("Analytics and SEO", {"fields": ("google_analytics_id", "seo_meta_title", "seo_meta_description")}),
        ("Map and marketing", {"fields": ("mapbox_token", "side_banner_html", "bottom_banner_html"), "classes": ("collapse",)}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "name", "subject", "is_enabled", "created_at")
    list_display_links = ("id", "key", "name")
    search_fields = ("key", "name", "subject")
    list_filter = ("is_enabled",)
    ordering = ("key", "id")


@admin.register(WidgetTemplate)
class WidgetTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    list_display_links = ("id", "name", "slug")
    search_fields = ("name", "slug")
    ordering = ("slug", "id")


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "q", "location", "active", "created_at")
    list_display_links = ("id", "email")
    search_fields = ("email", "q", "location")
    list_filter = ("active",)
    ordering = ("-created_at", "-id")


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "gateway_name", "currency", "is_active", "use_stripe", "use_paypal", "updated_at")
    list_display_links = ("id", "gateway_name")
    list_filter = ("is_active", "use_stripe", "use_paypal")
    search_fields = ("gateway_name", "currency")
    ordering = ("-is_active", "-updated_at", "-id")


@admin.register(SocialPostingConfig)
class SocialPostingConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "enabled", "facebook_page_id", "instagram_business_id", "reddit_subreddit", "created_at")
    list_display_links = ("id", "facebook_page_id", "instagram_business_id")
    list_filter = ("enabled",)
    ordering = ("-created_at", "-id")


@admin.register(WebhookConfig)
class WebhookConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "enabled", "url", "created_at")
    list_display_links = ("id", "url")
    list_filter = ("enabled",)
    ordering = ("-created_at", "-id")


# ---------------------------
# User admin (master Users list)
# ---------------------------

User = get_user_model()

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("-date_joined", "-id")
    list_display = DjangoUserAdmin.list_display + ("date_joined",)
    list_filter = DjangoUserAdmin.list_filter
