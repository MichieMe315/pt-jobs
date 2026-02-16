# board/admin.py
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
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


def _send_approval_email(to_email: str, subject: str, body: str) -> None:
    # keep admin stable even if SendGrid hiccups
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

    for k, v in context.items():
        subject = subject.replace(f"{{{{{k}}}}}", str(v))
        body = body.replace(f"{{{{{k}}}}}", str(v))

    return subject.strip(), body.strip()


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
            # NOTE: matches your production admin behavior (today + duration)
            job.expiry_date = today + timedelta(days=duration_days)
        else:
            # at minimum, don't let expiry be in the past
            if getattr(job, "expiry_date", None) and job.expiry_date < today:
                job.expiry_date = today


# ---------------------------
# Inlines
# ---------------------------

class PurchasedPackageInline(admin.TabularInline):
    model = PurchasedPackage
    extra = 0
    fields = ("package", "credits_granted", "credits_remaining", "purchased_at", "expires_at", "source")
    readonly_fields = ("purchased_at",)


# ---------------------------
# Approval actions
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

        email = (getattr(employer, "email", "") or "") or (
            employer.user.email if getattr(employer, "user_id", None) else ""
        )
        if email:
            rendered = _render_email_template(
                "employer_approved",
                {"email": email, "company_name": getattr(employer, "company_name", "")},
            )
            if rendered:
                subject, body = rendered
            else:
                subject = "Your employer account is approved"
                body = (
                    "Your employer account on Physiotherapy Jobs Canada has been approved.\n\n"
                    "You can now log in and post jobs.\n\n"
                    "— Physiotherapy Jobs Canada"
                )
            _send_approval_email(email, subject, body)
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

        email = (getattr(js, "email", "") or "") or (js.user.email if getattr(js, "user_id", None) else "")
        if email:
            rendered = _render_email_template(
                "jobseeker_approved",
                {
                    "email": email,
                    "first_name": getattr(js, "first_name", ""),
                    "last_name": getattr(js, "last_name", ""),
                },
            )
            if rendered:
                subject, body = rendered
            else:
                subject = "Your job seeker account is approved"
                body = (
                    "Your job seeker account on Physiotherapy Jobs Canada has been approved.\n\n"
                    "You can now log in and apply to jobs.\n\n"
                    "— Physiotherapy Jobs Canada"
                )
            _send_approval_email(email, subject, body)
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
        "name",
        "email",
        "location",
        "credits",
        "is_approved",
        "login_active",
        "created_at",
    )
    list_display_links = ("id", "company_name")
    search_fields = ("company_name", "name", "email", "location")
    list_filter = ("is_approved", "login_active")
    ordering = ("-created_at", "-id")

    readonly_fields = ("view_employer_jobs", "view_employer_packages")

    def view_employer_jobs(self, obj):
        if not obj or not obj.pk:
            return "-"
        url = reverse("admin:board_job_changelist")
        return format_html('<a class="button" href="{}?employer__id__exact={}">View Employer Jobs</a>', url, obj.pk)

    view_employer_jobs.short_description = "Jobs"

    def view_employer_packages(self, obj):
        if not obj or not obj.pk:
            return "-"
        url = reverse("admin:board_purchasedpackage_changelist")
        return format_html('<a class="button" href="{}?employer__id__exact={}">View Employer Packages</a>', url, obj.pk)

    view_employer_packages.short_description = "Packages"


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
    list_display_links = ("id", "email")
    search_fields = ("email", "first_name", "last_name", "position_desired", "current_location")
    list_filter = ("registered_in_canada", "require_sponsorship", "is_approved", "login_active")
    ordering = ("-created_at", "-id")


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

    # ✅ THIS is the missing piece your production change_form.html expects:
    # {% url 'admin:board_job_duplicate' original.pk %}
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

        # Make a NEW row (do not overwrite original)
        original.pk = None
        original.posting_date = today
        original.is_active = False  # admin duplicate starts as draft/inactive

        if hasattr(original, "views_count"):
            original.views_count = 0

        _set_duplicate_expiry(original, today)
        original.save()

        self.message_user(request, "Job duplicated (new draft created).", level=messages.SUCCESS)

        # Send admin to the *new* job change page
        return redirect("admin:board_job_change", original.pk)


# ---------------------------
# Remaining model admins
# ---------------------------

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "jobseeker", "created_at")
    search_fields = ("job__title", "jobseeker__email", "jobseeker__first_name", "jobseeker__last_name")
    list_filter = ("created_at",)
    ordering = ("-created_at", "-id")


@admin.register(Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = ("id", "jobseeker", "title", "created_at")
    search_fields = ("jobseeker__email", "title")
    ordering = ("-created_at", "-id")


@admin.register(PostingPackage)
class PostingPackageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "code",
        "name",
        "credits",
        "duration_days",
        "price_cents",
        "is_active",
        "order",
        "package_expires_days",
    )
    search_fields = ("code", "name")
    list_filter = ("is_active", "allows_featured")
    ordering = ("order", "name", "id")


@admin.register(PurchasedPackage)
class PurchasedPackageAdmin(admin.ModelAdmin):
    list_display = ("id", "employer", "package", "credits_granted", "credits_remaining", "purchased_at", "expires_at", "source")
    search_fields = ("employer__company_name", "package__name")
    list_filter = ("package", "purchased_at")
    ordering = ("-purchased_at", "-id")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "employer", "amount", "currency", "processor", "status", "order_date", "discount_code")
    search_fields = ("employer__company_name", "processor_reference", "discount_code")
    list_filter = ("status", "processor", "currency")
    ordering = ("-order_date", "-id")


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "code",
        "kind",
        "value",
        "is_active",
        "start_date",
        "end_date",
        "max_uses",
        "uses",
        "created_at",
    )
    search_fields = ("code", "name")
    list_filter = ("is_active", "kind")
    ordering = ("-created_at", "-id")


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "site_name", "google_analytics_id", "posting_duration_days")
    search_fields = ("site_name", "google_analytics_id")
    ordering = ("-id",)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "name", "subject", "is_enabled", "created_at")
    search_fields = ("key", "name", "subject")
    list_filter = ("is_enabled",)
    ordering = ("key", "id")


@admin.register(WidgetTemplate)
class WidgetTemplateAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    search_fields = ("name", "slug")
    ordering = ("slug", "id")


@admin.register(JobAlert)
class JobAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "q", "location", "active", "created_at")
    search_fields = ("email", "q", "location")
    list_filter = ("active",)
    ordering = ("-created_at", "-id")


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "gateway_name", "currency", "is_active", "use_stripe", "use_paypal", "updated_at")
    list_filter = ("is_active", "use_stripe", "use_paypal")
    search_fields = ("gateway_name", "currency")
    ordering = ("-is_active", "-updated_at", "-id")


@admin.register(SocialPostingConfig)
class SocialPostingConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "enabled", "facebook_page_id", "instagram_business_id", "reddit_subreddit", "created_at")
    list_filter = ("enabled",)
    ordering = ("-created_at", "-id")


@admin.register(WebhookConfig)
class WebhookConfigAdmin(admin.ModelAdmin):
    list_display = ("id", "enabled", "url", "created_at")
    list_filter = ("enabled",)
    ordering = ("-created_at", "-id")


# ---------------------------
# User admin (master Users list)
# ---------------------------

User = get_user_model()

# FIX: Django already registers the User model. Unregister first to avoid AlreadyRegistered.
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("-date_joined", "-id")
    list_display = DjangoUserAdmin.list_display + ("date_joined",)
    list_filter = DjangoUserAdmin.list_filter
