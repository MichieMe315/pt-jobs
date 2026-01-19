from __future__ import annotations

from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import send_mail
from django.utils import timezone

from import_export import resources
from import_export.admin import ImportExportModelAdmin

from .models import (
    Application,
    DiscountCode,
    EmailTemplate,
    Employer,
    Invoice,
    Job,
    JobAlert,
    JobSeeker,
    PaymentGatewayConfig,
    PostingPackage,
    PurchasedPackage,
    Resume,
    SiteSettings,
    SocialPostingConfig,
    WebhookConfig,
    WidgetTemplate,
)


class SafeModelAdmin(admin.ModelAdmin):
    """
    Force newest records first (last created appears on top).
    Using -id is safe and consistent across all models.
    """
    ordering = ("-id",)


# ============================================================
# EmailTemplate send helpers (NO STUBS)
# ============================================================

def _get_default_from_email() -> str | None:
    return getattr(settings, "DEFAULT_FROM_EMAIL", None)


def _render_template(key: str, context: dict) -> tuple[str, str] | None:
    """
    Minimal token replace:
      - replaces {{ token }} occurrences in subject/html with context[str(token)] if present.
    Safe and predictable, no magic.
    """
    tpl = EmailTemplate.objects.filter(key=key, is_enabled=True).first()
    if not tpl:
        return None

    subject = tpl.subject or ""
    body = getattr(tpl, "html", "") or ""

    for k, v in context.items():
        subject = subject.replace(f"{{{{ {k} }}}}", str(v))
        body = body.replace(f"{{{{ {k} }}}}", str(v))

    return subject, body


def _send_email_template(key: str, to_email: str, context: dict) -> bool:
    """
    Sends exactly ONE template key. No fallback.
    Returns True only if:
      - template exists + enabled, AND
      - send_mail succeeds
    """
    if not to_email:
        return False

    rendered = _render_template(key, context)
    if not rendered:
        return False

    subject, body = rendered
    try:
        send_mail(
            subject,
            body,
            _get_default_from_email(),
            [to_email],
            fail_silently=False,
        )
        return True
    except Exception:
        return False


# ----------------------------
# Import/Export resources
# ----------------------------

class JobResource(resources.ModelResource):
    class Meta:
        model = Job


class EmployerResource(resources.ModelResource):
    class Meta:
        model = Employer


class JobSeekerResource(resources.ModelResource):
    class Meta:
        model = JobSeeker


class ApplicationResource(resources.ModelResource):
    class Meta:
        model = Application


class ResumeResource(resources.ModelResource):
    class Meta:
        model = Resume


class InvoiceResource(resources.ModelResource):
    class Meta:
        model = Invoice


class PurchasedPackageResource(resources.ModelResource):
    class Meta:
        model = PurchasedPackage


# ----------------------------
# Actions
# ----------------------------

@admin.action(description="Approve selected Employers")
def approve_employers(modeladmin, request, queryset):
    updated = 0
    emailed = 0
    missing_template = 0

    for emp in queryset:
        if hasattr(emp, "is_approved") and not emp.is_approved:
            emp.is_approved = True
            emp.save(update_fields=["is_approved"])
            updated += 1

            # Contract-required: approval email to employer on approval
            ok = _send_email_template(
                "employer_approved",
                getattr(emp, "email", ""),
                {"email": getattr(emp, "email", ""), "company_name": getattr(emp, "company_name", "")},
            )
            if ok:
                emailed += 1
            else:
                missing_template += 1

    if missing_template:
        messages.warning(
            request,
            f"Approved {updated} employer(s). Sent {emailed} approval email(s). "
            f"{missing_template} were NOT emailed (missing/disabled template key: employer_approved or SMTP error).",
        )
    else:
        messages.success(request, f"Approved {updated} employer(s). Sent {emailed} approval email(s).")


@admin.action(description="Approve selected Job Seekers")
def approve_jobseekers(modeladmin, request, queryset):
    updated = 0
    emailed = 0
    missing_template = 0

    for js in queryset:
        if hasattr(js, "is_approved") and not js.is_approved:
            js.is_approved = True
            js.save(update_fields=["is_approved"])
            updated += 1

            # Contract-required: approval email to job seeker on approval
            ok = _send_email_template(
                "jobseeker_approved",
                getattr(js, "email", ""),
                {
                    "email": getattr(js, "email", ""),
                    "first_name": getattr(js, "first_name", ""),
                    "last_name": getattr(js, "last_name", ""),
                },
            )
            if ok:
                emailed += 1
            else:
                missing_template += 1

    if missing_template:
        messages.warning(
            request,
            f"Approved {updated} job seeker(s). Sent {emailed} approval email(s). "
            f"{missing_template} were NOT emailed (missing/disabled template key: jobseeker_approved or SMTP error).",
        )
    else:
        messages.success(request, f"Approved {updated} job seeker(s). Sent {emailed} approval email(s).")


@admin.action(description="Deactivate selected Employers")
def deactivate_employers(modeladmin, request, queryset):
    updated = queryset.update(login_active=False)
    messages.success(request, f"Deactivated {updated} employer(s).")


@admin.action(description="Activate selected Employers")
def activate_employers(modeladmin, request, queryset):
    updated = queryset.update(login_active=True)
    messages.success(request, f"Activated {updated} employer(s).")


@admin.action(description="Deactivate selected Job Seekers")
def deactivate_jobseekers(modeladmin, request, queryset):
    updated = queryset.update(login_active=False)
    messages.success(request, f"Deactivated {updated} job seeker(s).")


@admin.action(description="Activate selected Job Seekers")
def activate_jobseekers(modeladmin, request, queryset):
    updated = queryset.update(login_active=True)
    messages.success(request, f"Activated {updated} job seeker(s).")


@admin.action(description="Deactivate selected Jobs (no deletes)")
def deactivate_jobs(modeladmin, request, queryset):
    updated = queryset.update(is_active=False)
    messages.success(request, f"Deactivated {updated} job(s).")


@admin.action(description="Activate selected Jobs")
def activate_jobs(modeladmin, request, queryset):
    updated = queryset.update(is_active=True)
    messages.success(request, f"Activated {updated} job(s).")


@admin.action(description="Enable selected Email Templates")
def enable_email_templates(modeladmin, request, queryset):
    updated = queryset.update(is_enabled=True)
    messages.success(request, f"Enabled {updated} email template(s).")


@admin.action(description="Disable selected Email Templates")
def disable_email_templates(modeladmin, request, queryset):
    updated = queryset.update(is_enabled=False)
    messages.success(request, f"Disabled {updated} email template(s).")


def _posting_duration_days_default() -> int:
    s = SiteSettings.objects.first()
    if s and getattr(s, "posting_duration_days", None):
        try:
            return int(s.posting_duration_days)
        except Exception:
            pass
    return 30


def _max_expiry_date_last_day(posting_date, duration_days: int):
    days = max(1, int(duration_days or 1))
    return posting_date + timezone.timedelta(days=days - 1)


@admin.action(description="Duplicate selected Jobs (creates inactive copies)")
def duplicate_jobs(modeladmin, request, queryset):
    """
    Admin-side duplicate:
    - Creates a new Job record with copied fields.
    - Sets is_active=False by default.
    - Sets posting_date to today and clamps expiry_date to posting_duration_days.
    """
    created = 0
    posting_date = timezone.now().date()
    duration_days = _posting_duration_days_default()
    max_expiry = _max_expiry_date_last_day(posting_date, duration_days)

    for j in queryset:
        dup = Job()
        for field in Job._meta.concrete_fields:
            if field.primary_key:
                continue
            name = field.name
            if name in ("id",):
                continue
            if name in ("posting_date", "expiry_date", "created_at", "updated_at"):
                continue
            try:
                setattr(dup, name, getattr(j, name))
            except Exception:
                continue

        dup.posting_date = posting_date
        try:
            if getattr(j, "expiry_date", None):
                dup.expiry_date = min(j.expiry_date, max_expiry)
            else:
                dup.expiry_date = max_expiry
        except Exception:
            dup.expiry_date = max_expiry

        dup.is_active = False
        dup.save()
        created += 1

    messages.success(request, f"Duplicated {created} job(s). New copies are inactive.")


# ----------------------------
# Core models
# ----------------------------

@admin.register(Job)
class JobAdmin(ImportExportModelAdmin):
    resource_class = JobResource
    actions = [duplicate_jobs, deactivate_jobs, activate_jobs]
    ordering = ("-id",)
    list_display_links = ("title",)
    list_display = (
        "id",
        "title",
        "employer",
        "location",
        "posting_date",
        "expiry_date",
        "is_active",
        "is_featured",
        "source",
    )
    list_filter = ("is_featured", "is_active", "posting_date")
    search_fields = ("title", "location", "employer__company_name")


@admin.register(JobSeeker)
class JobSeekerAdmin(ImportExportModelAdmin):
    resource_class = JobSeekerResource
    actions = [approve_jobseekers, deactivate_jobseekers, activate_jobseekers]
    ordering = ("-id",)
    list_display_links = ("last_name", "first_name")
    list_display = (
        "id",
        "first_name",
        "last_name",
        "email",
        "is_approved",
        "login_active",
        "created_at",
    )
    list_filter = ("is_approved", "login_active")
    search_fields = ("first_name", "last_name", "email")


@admin.register(Employer)
class EmployerAdmin(ImportExportModelAdmin):
    resource_class = EmployerResource
    actions = [approve_employers, deactivate_employers, activate_employers]
    ordering = ("-id",)
    list_display_links = ("company_name",)
    list_display = (
        "id",
        "company_name",
        "location",
        "credits",
        "is_approved",
        "login_active",
    )
    list_filter = ("is_approved", "login_active")
    search_fields = ("company_name", "location", "user__username")


@admin.register(Application)
class ApplicationAdmin(ImportExportModelAdmin):
    resource_class = ApplicationResource
    ordering = ("-id",)
    list_display = ("id", "job", "jobseeker", "created_at")
    list_filter = ("created_at",)
    search_fields = ("job__title", "jobseeker__email", "jobseeker__first_name", "jobseeker__last_name")


@admin.register(Resume)
class ResumeAdmin(ImportExportModelAdmin):
    resource_class = ResumeResource
    ordering = ("-id",)
    list_display = ("id", "jobseeker", "created_at")
    list_filter = ("created_at",)
    search_fields = ("jobseeker__email", "jobseeker__first_name", "jobseeker__last_name")


# ----------------------------
# Packages / billing
# ----------------------------

@admin.register(PostingPackage)
class PostingPackageAdmin(SafeModelAdmin):
    list_display = ("name", "credits", "duration_days", "price", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(PurchasedPackage)
class PurchasedPackageAdmin(ImportExportModelAdmin):
    resource_class = PurchasedPackageResource
    ordering = ("-id",)
    list_display = (
        "id",
        "employer",
        "package",
        "credits_granted",
        "credits_remaining",
        "purchased_at",
        "source",
    )
    list_filter = ("source", "purchased_at")
    search_fields = ("employer__company_name", "package__name")


@admin.register(Invoice)
class InvoiceAdmin(ImportExportModelAdmin):
    resource_class = InvoiceResource
    ordering = ("-id",)
    list_display = (
        "id",
        "employer",
        "amount",
        "currency",
        "processor",
        "status",
        "order_date",
        "processor_reference",
        "discount_code",
    )
    list_filter = ("processor", "status", "order_date")
    search_fields = ("employer__company_name", "processor_reference", "discount_code")


@admin.register(DiscountCode)
class DiscountCodeAdmin(SafeModelAdmin):
    list_display = ("code", "kind", "value", "start_date", "end_date", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code",)


# ----------------------------
# Settings + templates
# ----------------------------

@admin.register(SiteSettings)
class SiteSettingsAdmin(SafeModelAdmin):
    list_display = ("id", "site_name", "contact_email")
    search_fields = ("site_name", "contact_email")

    # ✅ Fix the “duplicate hero fields” you see in the screenshot:
    # hide the legacy home_hero_* fields so only hero_* is editable.
    exclude = (
        "home_hero_image",
        "home_hero_title",
        "home_hero_subtitle",
        "home_hero_cta_text",
        "home_hero_cta_url",
    )


@admin.register(EmailTemplate)
class EmailTemplateAdmin(SafeModelAdmin):
    actions = [enable_email_templates, disable_email_templates]
    list_display_links = ("key",)
    list_display = ("key", "name", "subject", "is_enabled")
    list_filter = ("is_enabled",)
    search_fields = ("key", "name", "subject")


@admin.register(WidgetTemplate)
class WidgetTemplateAdmin(SafeModelAdmin):
    list_display = ("id", "name", "slug", "created_at")
    search_fields = ("slug", "name")


@admin.register(JobAlert)
class JobAlertAdmin(SafeModelAdmin):
    list_display = ("id", "email", "created_at")
    list_filter = ("created_at",)
    search_fields = ("email",)


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(SafeModelAdmin):
    list_display = ("id", "gateway_name", "currency", "is_active")
    list_filter = ("gateway_name", "is_active")


@admin.register(SocialPostingConfig)
class SocialPostingConfigAdmin(SafeModelAdmin):
    list_display = ("id", "enabled", "facebook_page_id", "instagram_business_id", "reddit_subreddit")
    list_filter = ("enabled",)


@admin.register(WebhookConfig)
class WebhookConfigAdmin(SafeModelAdmin):
    list_display = ("id", "enabled", "url")
    list_filter = ("enabled",)
    search_fields = ("url",)
