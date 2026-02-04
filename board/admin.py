from datetime import timedelta

from django.conf import settings
from django.contrib import admin, messages
from django.core.mail import send_mail
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


# ------------------------------------------------------------
# Approval email helpers (admin-driven)
# ------------------------------------------------------------

def _default_from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", None) or "info@physiotherapyjobscanada.ca"


def _send_approval_email(to_email: str, subject: str, body: str) -> None:
    # fail_silently=True to avoid admin crashing if SendGrid has a transient issue
    send_mail(subject, body, _default_from_email(), [to_email], fail_silently=True)


def _render_email_template(key: str, context: dict) -> tuple[str, str] | None:
    """
    Optional: if you have EmailTemplate records, we use them.
    If not found/disabled, return None and we fall back to a safe default.
    """
    tmpl = EmailTemplate.objects.filter(key=key, is_enabled=True).first()
    if not tmpl:
        return None

    subject = tmpl.subject or ""
    body = tmpl.body or ""

    # Minimal placeholder replacement (no field renames, no magic mapping)
    # Supported tokens: {{email}}, {{company_name}}, {{first_name}}, {{last_name}}
    for k, v in context.items():
        subject = subject.replace(f"{{{{{k}}}}}", str(v))
        body = body.replace(f"{{{{{k}}}}}", str(v))

    return subject.strip(), body.strip()


# ------------------------------------------------------------
# Employer: inline purchased packages + buttons + approval actions
# ------------------------------------------------------------

class PurchasedPackageInline(admin.TabularInline):
    model = PurchasedPackage
    extra = 0
    fields = ("package", "credits_granted", "credits_remaining", "purchased_at", "expires_at", "source")
    readonly_fields = ("purchased_at",)


def approve_selected_employers(modeladmin, request, queryset):
    """
    Bulk approve (no model save hooks) + send approval emails.
    This avoids 500s if Employer.save() has side-effects while a customer is live.
    """
    updated = 0
    emailed = 0

    for employer in queryset:
        was_approved = bool(getattr(employer, "is_approved", False))
        if was_approved:
            continue

        # IMPORTANT: use update() to avoid model save hooks/signals.
        Employer.objects.filter(pk=employer.pk).update(is_approved=True)
        updated += 1

        email = getattr(employer, "email", None) or (
            employer.user.email if getattr(employer, "user_id", None) else None
        )
        if email:
            rendered = _render_email_template(
                "employer_approved",
                {
                    "email": email,
                    "company_name": getattr(employer, "company_name", ""),
                },
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


@admin.register(Employer)
class EmployerAdmin(admin.ModelAdmin):
    inlines = [PurchasedPackageInline]
    actions = [approve_selected_employers]

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

    def save_model(self, request, obj, form, change):
        """
        If admin flips is_approved from False -> True on save, email the employer.

        IMPORTANT (live safety):
        - If the ONLY field being changed is is_approved, we update via queryset.update()
          to avoid any Employer.save() side-effects that can cause admin 500s.
        """
        was_approved = False
        if change and obj.pk:
            try:
                was_approved = bool(
                    Employer.objects.filter(pk=obj.pk).values_list("is_approved", flat=True).first()
                )
            except Exception:
                was_approved = False

        only_approval_toggle = change and getattr(form, "changed_data", None) == ["is_approved"]

        if only_approval_toggle:
            Employer.objects.filter(pk=obj.pk).update(is_approved=bool(getattr(obj, "is_approved", False)))
        else:
            super().save_model(request, obj, form, change)

        now_approved = bool(getattr(obj, "is_approved", False))
        if change and (not was_approved) and now_approved:
            email = getattr(obj, "email", None) or (
                obj.user.email if getattr(obj, "user_id", None) else None
            )
            if email:
                rendered = _render_email_template(
                    "employer_approved",
                    {
                        "email": email,
                        "company_name": getattr(obj, "company_name", ""),
                    },
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
                self.message_user(request, "Approval email sent to employer.", level=messages.SUCCESS)


# ------------------------------------------------------------
# JobSeeker + approval actions
# ------------------------------------------------------------

def approve_selected_jobseekers(modeladmin, request, queryset):
    """
    Bulk approve (no model save hooks) + send approval emails.
    """
    updated = 0
    emailed = 0

    for js in queryset:
        was_approved = bool(getattr(js, "is_approved", False))
        if was_approved:
            continue

        JobSeeker.objects.filter(pk=js.pk).update(is_approved=True)
        updated += 1

        email = getattr(js, "email", None) or (js.user.email if getattr(js, "user_id", None) else None)
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


@admin.register(JobSeeker)
class JobSeekerAdmin(admin.ModelAdmin):
    actions = [approve_selected_jobseekers]

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

    def save_model(self, request, obj, form, change):
        was_approved = False
        if change and obj.pk:
            try:
                was_approved = bool(
                    JobSeeker.objects.filter(pk=obj.pk).values_list("is_approved", flat=True).first()
                )
            except Exception:
                was_approved = False

        only_approval_toggle = change and getattr(form, "changed_data", None) == ["is_approved"]

        if only_approval_toggle:
            JobSeeker.objects.filter(pk=obj.pk).update(is_approved=bool(getattr(obj, "is_approved", False)))
        else:
            super().save_model(request, obj, form, change)

        now_approved = bool(getattr(obj, "is_approved", False))
        if change and (not was_approved) and now_approved:
            email = getattr(obj, "email", None) or (obj.user.email if getattr(obj, "user_id", None) else None)
            if email:
                rendered = _render_email_template(
                    "jobseeker_approved",
                    {
                        "email": email,
                        "first_name": getattr(obj, "first_name", ""),
                        "last_name": getattr(obj, "last_name", ""),
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
                self.message_user(request, "Approval email sent to job seeker.", level=messages.SUCCESS)


# ------------------------------------------------------------
# Jobs: duplicate + expiry clamp + title clickable + employer link in job
# ------------------------------------------------------------

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
    list_display_links = ("id", "title")

    search_fields = ("title", "employer__name", "employer__company_name", "location")
    list_filter = ("is_active", "job_type", "compensation_type", "source")
    ordering = ("-posting_date", "-id")

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

    def get_exclude(self, request, obj=None):
        exclude = set(super().get_exclude(request, obj) or [])
        # Remove duplicates/unwanted legacy fields if they exist on the model
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

    def save_model(self, request, obj, form, change):
        """
        Admin safety: prevent expiry_date from being saved in the past.
        (This is separate from the contract max-date clamp which is enforced in the job form flow.)
        """
        if _model_has_field(self.model, "expiry_date") and getattr(obj, "expiry_date", None):
            today = timezone.localdate()
            if obj.expiry_date < today:
                obj.expiry_date = today

        super().save_model(request, obj, form, change)

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


# ------------------------------------------------------------
# The rest (unchanged)
# ------------------------------------------------------------

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
