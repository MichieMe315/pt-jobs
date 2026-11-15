# board/admin.py
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.mail import send_mail
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
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
    from django.core.mail import EmailMultiAlternatives
    from django.utils.html import strip_tags
    from .notification_mail import email_frame
    msg = EmailMultiAlternatives(subject, strip_tags(body), _default_from_email(), [to_email])
    msg.attach_alternative(email_frame(subject, body), 'text/html')
    msg.send(fail_silently=True)


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


def _posting_duration_days(job=None):
    if job and job.posting_date and job.expiry_date:
        days = (job.expiry_date - job.posting_date).days
        if days > 0:
            return days
    settings = SiteSettings.objects.first()
    days = getattr(settings, 'posting_duration_days', 30) if settings else 30
    return int(days) if days and int(days) > 0 else 30


def _set_duplicate_expiry(job, today, duration_days=None):
    job.expiry_date = today + timedelta(days=duration_days or _posting_duration_days())


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



class ProfileApprovalMixin:
    change_form_template='admin/board/account_change_form.html'
    def get_urls(self):
        from django.urls import path
        return [path('<path:object_id>/approve-profile/',self.admin_site.admin_view(self.approve_profile),name=self.opts.app_label+'_'+self.opts.model_name+'_approve_profile')]+super().get_urls()
    def approve_profile(self,request,object_id):
        from django.core.exceptions import PermissionDenied
        from django.http import HttpResponseNotAllowed,Http404,HttpResponseRedirect
        from django.db import transaction
        if request.method!='POST':return HttpResponseNotAllowed(['POST'])
        obj=self.get_object(request,object_id)
        if obj is None:raise Http404
        if not self.has_change_permission(request,obj):raise PermissionDenied
        with transaction.atomic():
            obj=self.model.objects.select_for_update().get(pk=obj.pk)
            if not obj.is_approved:
                obj.is_approved=True;obj.login_active=True;obj.approved_at=timezone.now()
                obj.save(update_fields=['is_approved','login_active','approved_at'])
                sender=_send_employer_approved_email if self.model is Employer else _send_jobseeker_approved_email
                transaction.on_commit(lambda:sender(obj))
                self.log_change(request,obj,'Approved profile')
        self.message_user(request,'Profile approved.',level=messages.SUCCESS)
        if request.POST.get('return_to')=='review':
            kind='employers' if self.model is Employer else 'candidates'
            return HttpResponseRedirect(reverse('admin:profile_review_queue')+'?kind='+kind)
        return HttpResponseRedirect(reverse('admin:'+self.opts.app_label+'_'+self.opts.model_name+'_change',args=[obj.pk]))
    def changeform_view(self,request,object_id=None,form_url='',extra_context=None):
        extra_context=dict(extra_context or {})
        obj=self.get_object(request,object_id) if object_id else None
        if obj and self.has_change_permission(request,obj):
            extra_context['profile_approve_url']=reverse('admin:'+self.opts.app_label+'_'+self.opts.model_name+'_approve_profile',args=[obj.pk])
            extra_context['profile_needs_approval']=not obj.is_approved
        return super().changeform_view(request,object_id,form_url,extra_context)
    def save_form(self,request,form,change):
        obj=super().save_form(request,form,change)
        if '_saveapprove' in request.POST:obj.is_approved=True
        return obj

class RecordSearchMixin:
    """Extend normal admin search with exact numeric record IDs."""
    list_per_page = 50
    show_full_result_count = False
    actions_on_bottom = False
    search_help_text = 'Search by name, email or location. Use #123 for an exact record ID.'

    def get_search_results(self, request, queryset, search_term):
        raw = (search_term or '').strip()
        numeric = raw.lstrip('#')
        if raw.startswith('#') and numeric.isascii() and numeric.isdigit():
            return (queryset.filter(pk=int(numeric)) if len(numeric)<19 else queryset.none()), False
        results, duplicates = super().get_search_results(request, queryset, search_term)
        if raw.isascii() and raw.isdigit() and len(raw)<19:
            results = results | queryset.filter(pk=int(raw))
        return results, duplicates


from .marketing.admin_filters import EmployerProvinceFilter,EmployerCommunityFilter,EmployerHiringFilter
from .marketing.bulk_actions import mark_rural,mark_remote,mark_small_city,mark_clinics,mark_hospitals,save_audience

from .admin_data import RecordsDataAdmin, EmployerResource, JobSeekerResource, JobResource

class ApprovalStatusFilter(admin.SimpleListFilter):
    title = "approval status"
    parameter_name = "approval_status"

    status_options = (("pending", "Pending"), ("approved", "Approved"))

    def lookups(self, request, model_admin):
        return self.status_options

    def queryset(self, request, queryset):
        if self.value() in ("pending", "approved"):
            return queryset.filter(is_approved=self.value() == "approved")
        return queryset


def status_tabs(request, parameter, choices):
    current = request.GET.get(parameter, "")
    query = request.GET.copy()
    query.pop("p", None)
    tabs = []
    for value, label in (("", "All"), *choices):
        if value:
            query[parameter] = value
        else:
            query.pop(parameter, None)
        tabs.append({"label": label, "url": "?" + query.urlencode(), "current": value == current})
    return tabs


class ApprovalListMixin:
    @admin.display(description="Approval status", ordering="is_approved")
    def approval_status(self, obj):
        return "Approved" if obj.is_approved else "Pending"

    def get_list_display(self, request):
        columns = super().get_list_display(request)
        if "approval_status" not in columns:
            return (*columns[:1], "approval_status", *columns[1:])
        return columns

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context={
            **(extra_context or {}),
            "posting_tabs": status_tabs(request, "approval_status", ApprovalStatusFilter.status_options),
            "status_label": "Approval status",
        })


@admin.register(Employer)
class EmployerAdmin(ApprovalListMixin, ProfileApprovalMixin, RecordSearchMixin, RecordsDataAdmin):
    resource_classes = [EmployerResource]
    extra_columns = ("name", "phone", "website", "approved_at")
    list_select_related = ('user',)

    inlines = [PurchasedPackageInline]
    actions = [approve_selected_employers,mark_rural,mark_remote,mark_small_city,mark_clinics,mark_hospitals,save_audience]

    list_display = (
        "id",
        "company_name",
        "email",
        "location",
        "marketing_city",
        "marketing_province",
        "community_category",
        "active_postings",
        "last_payment",
        "updated_at",
        "credits",
        "profile_completeness",
        "approval_status",
        "login_active",
        "created_at",
    )
    list_display_links = ("id", "company_name", "email")
    search_fields = ("company_name", "name", "email", "phone", "website", "location", "user__email", "user__username", "marketing_profile__tags", "marketing_profile__city")
    list_filter = (ApprovalStatusFilter, "login_active", EmployerProvinceFilter, EmployerCommunityFilter, EmployerHiringFilter)
    # Employers needing approval/reapproval first; newest profile changes first.
    ordering = ("is_approved", "-updated_at", "-id")

    def get_queryset(self,request):
        from .marketing.contacts import annotate_employers
        return annotate_employers(super().get_queryset(request))
    @admin.display(ordering='_marketing_city',description='City / community')
    def marketing_city(self,obj):return obj._marketing_city or '—'
    @admin.display(ordering='_marketing_province',description='Province')
    def marketing_province(self,obj):return obj._marketing_province or '—'
    @admin.display(ordering='marketing_profile__settlement',description='Community category')
    def community_category(self,obj):
        profile=getattr(obj,'marketing_profile',None)
        return profile.get_settlement_display() if profile else 'Not classified'
    @admin.display(ordering='_active_jobs',description='Active jobs')
    def active_postings(self,obj):return obj._active_jobs
    @admin.display(ordering='_last_paid',description='Last payment')
    def last_payment(self,obj):return obj._last_paid

    # Buttons
    readonly_fields = ("view_employer_jobs", "view_employer_packages", "review_possible_duplicates")

    fieldsets = (
        ('Company profile', {'fields': ('company_name','location','logo','company_description')}),
        ('Contact', {'fields': (('name','email'),('phone','website'))}),
        ('Account and credits', {'fields': ('user',('is_approved','login_active'),'credits','approved_at')}),
        ('Related records', {'fields': ('view_employer_jobs','view_employer_packages','review_possible_duplicates')}),
        ('Legacy description', {'fields': ('description',), 'classes': ('collapse',)}),
    )

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        from .operations import can_view, record_url
        obj = self.get_object(request, object_id) if object_id else None
        context = dict(extra_context or {})
        groups = []
        if obj and can_view(request.user, Job):
            jobs = obj.jobs.order_by('-posting_date','-pk')[:5]
            groups.append({'title':'Recent postings','empty':'No postings yet.','url':reverse('admin:board_job_changelist')+f'?employer__id__exact={obj.pk}',
                           'rows':[{'label':j.title,'url':record_url(request,j),'detail':j.location} for j in jobs]})
        if obj and can_view(request.user, Invoice):
            invoices = Invoice.objects.filter(employer=obj).order_by('-order_date','-pk')[:5]
            groups.append({'title':'Recent invoices','empty':'No invoices yet.',
                           'rows':[{'label':f'Invoice #{i.pk}','url':record_url(request,i),'detail':i.get_status_display()} for i in invoices]})
        context['related_activity'] = groups
        if obj:
            job_admin = self.admin_site._registry.get(Job)
            if job_admin and job_admin.has_add_permission(request):
                context['profile_add_job_url'] = reverse('admin:board_job_add') + '?' + urlencode({'employer':obj.pk})
        return super().changeform_view(request,object_id,form_url,context)

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

    @admin.display(description='Profile')
    def profile_completeness(self, obj):
        missing=[]
        if not obj.logo:missing.append('logo')
        if not ((obj.company_description or '').strip() or (obj.description or '').strip()):missing.append('description')
        if not (obj.email or '').strip():missing.append('email')
        if not (obj.location or '').strip():missing.append('location')
        return 'Complete' if not missing else 'Missing ' + ', '.join(missing)

    @admin.display(description='Duplicate review')
    def review_possible_duplicates(self, obj):
        if not obj or not obj.pk:return 'Save the profile to review matching records.'
        kind='employer-email' if (obj.email or '').strip() else 'employer-name'
        value=obj.email if kind=='employer-email' else obj.company_name
        if not (value or '').strip():return 'Add an email or company name to review matches.'
        url=reverse('admin:operations_duplicates')+'?'+urlencode({'kind':kind,'q':value.strip().lower()})
        return format_html('<a class="button" href="{}">Review matching profiles</a>',url)

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
class JobSeekerAdmin(ApprovalListMixin, ProfileApprovalMixin, RecordSearchMixin, RecordsDataAdmin):
    resource_classes = [JobSeekerResource]
    extra_columns = ("updated_at", "approved_at", "opportunity_type", "open_to_relocate", "relocate_where", "seeking_immigration")
    readonly_fields = ("review_possible_duplicates",)

    fieldsets = (
        ('Contact and résumé', {'fields': (('first_name','last_name'),'email','current_location','resume')}),
        ('Job preferences', {'fields': ('position_desired','opportunity_type','open_to_relocate','relocate_where')}),
        ('Registration and work authorization', {'fields': ('registered_in_canada','require_sponsorship','seeking_immigration')}),
        ('Account and approval', {'fields': ('user','is_approved','login_active','approved_at','review_possible_duplicates')}),
    )

    list_select_related = ('user',)

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
        "approval_status",
        "login_active",
        "registered_at",
    )
    list_display_links = ("id", "email", "first_name")
    search_fields = ("email", "user__email", "user__username", "first_name", "last_name", "position_desired", "current_location")
    list_filter = ("registered_in_canada", "require_sponsorship", "open_to_relocate", "opportunity_type", ApprovalStatusFilter, "login_active")
    # Newest signups first; unapproved records win only when timestamps match.
    ordering = ("-created_at", "is_approved", "-id")

    @admin.display(description='Registered', ordering='created_at')
    def registered_at(self, obj):
        return timezone.localtime(obj.created_at).strftime('%b %d, %Y %H:%M') if obj.created_at else '—'

    @admin.display(description='Duplicate review')
    def review_possible_duplicates(self, obj):
        if not obj or not obj.pk or not (obj.email or '').strip():return 'Add an email to review matching profiles.'
        url=reverse('admin:operations_duplicates')+'?'+urlencode({'kind':'candidate-email','q':obj.email.strip().lower()})
        return format_html('<a class="button" href="{}">Review matching profiles</a>',url)

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
    if not (modeladmin.has_add_permission(request) and modeladmin.has_change_permission(request)):
        raise PermissionDenied
    if queryset.count() != 1:
        modeladmin.message_user(request, 'Select one job to open an editable copy.', level=messages.WARNING)
        return
    return redirect('admin:board_job_duplicate', queryset.first().pk)


duplicate_selected_jobs.short_description = "Duplicate selected jobs"


class JobLifecycleFilter(admin.SimpleListFilter):
    title = "posting status"
    parameter_name = "posting_status"

    status_options = (("active", "Active"), ("inactive", "Inactive / draft"), ("expired", "Expired"))

    def lookups(self, request, model_admin):
        return self.status_options

    def queryset(self, request, queryset):
        from django.db.models import Q
        today = timezone.localdate()
        if self.value() == "active":
            return queryset.filter(is_active=True).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
        if self.value() == "inactive":
            return queryset.filter(is_active=False).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
        if self.value() == "expired":
            return queryset.filter(expiry_date__lt=today)
        return queryset


@admin.register(Job)
class JobAdmin(RecordSearchMixin, RecordsDataAdmin):
    change_form_template = 'admin/board/job/change_form.html'
    fieldsets = (
        ('Posting', {'fields': ('title','employer','location','job_type','description')}),
        ('Compensation and relocation', {'fields': ('compensation_type',('compensation_min','compensation_max'),'relocation_assistance')}),
        ('Applications', {'fields': ('apply_via','apply_email','apply_url')}),
        ('International candidates', {'fields': (('international_stage','international_support'),)}),
        ('Publication', {'fields': (('posting_date','expiry_date'),('is_active','is_featured'))}),
        ('Advanced and legacy', {'fields': ('source','views_count','expiry_email_sent'), 'classes': ('collapse',)}),
    )
    resource_classes = [JobResource]
    extra_columns = ("job_type", "compensation_type", "compensation_min", "compensation_max", "created_at", "updated_at", "views_count")
    list_select_related = ('employer',)

    actions = [duplicate_selected_jobs]

    list_display = (
        "id",
        "title",
        "employer_link",
        "location",
        "posting_date",
        "expiry_date",
        "posting_status",
        "source",
    )
    list_display_links = ("id", "title")
    search_fields = ("title", "employer__company_name", "employer__name", "employer__email", "location", "description")
    list_filter = (JobLifecycleFilter, "is_active", "job_type", "compensation_type", "source", "international_stage", "international_support")
    ordering = ("-posting_date", "-id")

    def get_queryset(self, request):
        from django.db.models import Case, IntegerField, Value, When
        return super().get_queryset(request).annotate(
            _posting_status=Case(
                When(expiry_date__lt=timezone.localdate(), then=Value(2)),
                When(is_active=True, then=Value(0)),
                default=Value(1), output_field=IntegerField(),
            )
        )

    @admin.display(description="Posting status", ordering="_posting_status")
    def posting_status(self, obj):
        return ("Active", "Inactive / draft", "Expired")[obj._posting_status]

    def get_list_display(self, request):
        columns = super().get_list_display(request)
        return columns if "posting_status" in columns else (*columns[:1], "posting_status", *columns[1:])

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, extra_context={
            **(extra_context or {}),
            "posting_tabs": status_tabs(request, "posting_status", JobLifecycleFilter.status_options),
        })

    def _duplicate_source(self, request):
        source_id = request.GET.get('duplicate_from')
        if not source_id:
            return None
        try:
            source_id = int(source_id)
        except (TypeError, ValueError):
            from django.http import Http404
            raise Http404('Unknown source job')
        source = get_object_or_404(self.get_queryset(request), pk=source_id)
        if not (self.has_add_permission(request) and self.has_change_permission(request, source)):
            raise PermissionDenied
        return source

    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        initial.pop('duplicate_from', None)
        today = timezone.localdate()
        source = self._duplicate_source(request)
        if source:
            from django.forms.models import model_to_dict
            initial = model_to_dict(source, exclude=['id', 'created_at', 'updated_at'])
            initial.update(posting_date=today, expiry_date=today + timedelta(days=_posting_duration_days(source)), is_active=True, views_count=0, expiry_email_sent=False)
        else:
            initial.setdefault('posting_date', today)
            initial.setdefault('expiry_date', today + timedelta(days=_posting_duration_days()))
        return initial

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        context = dict(extra_context or {})
        obj = self.get_object(request, object_id) if object_id else None
        source = self._duplicate_source(request) if not object_id else None
        context['admin_posting_duration'] = _posting_duration_days(source or obj)
        context['can_duplicate_job'] = bool(obj and self.has_add_permission(request) and self.has_change_permission(request, obj))
        context['can_publish_saved_job'] = bool(obj and not obj.is_active and obj.employer.is_approved and obj.employer.login_active and obj.employer.user.is_active
            and self.has_change_permission(request,obj)
            and not obj.publication_requests.filter(status__in=('waiting','ready','review')).exists())
        if source:
            context['title'] = 'New copy of ' + source.title
        return super().changeform_view(request, object_id, form_url, context)

    def save_model(self, request, obj, form, change):
        source = self._duplicate_source(request) if not change else None
        if source:
            # Keep legacy application/feature fields hidden by the existing form.
            for name in self.get_exclude(request, obj=None) or ():
                if _model_has_field(Job, name):
                    setattr(obj, name, getattr(source, name))
        super().save_model(request, obj, form, change)

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
            path("<path:object_id>/publish-saved/",self.admin_site.admin_view(self.publish_saved_job),name="board_job_publish_saved"),
            path(
                "<path:object_id>/duplicate/",
                self.admin_site.admin_view(self.duplicate_job_view),
                name="board_job_duplicate",
            ),
        ]
        return custom + urls

    def publish_saved_job(self,request,object_id):
        from django.http import HttpResponseNotAllowed
        from django.db import transaction
        if request.method!='POST':
            return HttpResponseNotAllowed(['POST'])
        with transaction.atomic():
            saved=get_object_or_404(self.get_queryset(request),pk=object_id)
            if not self.has_change_permission(request,saved):
                raise PermissionDenied
            # Match checkout lock order: employer first, job second.
            employer=get_object_or_404(Employer.objects.select_for_update(),pk=saved.employer_id)
            job=get_object_or_404(Job.objects.select_for_update(),pk=object_id,employer=employer)
            if not self.has_change_permission(request,job):
                raise PermissionDenied
            if not employer.is_approved or not employer.login_active or not employer.user.is_active or job.publication_requests.filter(status__in=('waiting','ready','review')).exists():
                self.message_user(request,'Resolve the employer approval or outstanding checkout before publishing.',level=messages.ERROR)
            elif not job.is_active and not (job.title.strip() and job.description.strip()):
                self.message_user(request,'Save a job title and description before publishing.',level=messages.ERROR)
            elif not job.is_active:
                today=timezone.localdate()
                job.posting_date=today
                job.expiry_date=today+timedelta(days=_posting_duration_days(job)-1)
                job.expiry_email_sent=False
                job.is_active=True
                job.save(update_fields=['posting_date','expiry_date','expiry_email_sent','is_active'])
                self.log_change(request,job,'Published saved job from admin')
                self.message_user(request,'Job published. No employer credit was used.')
        return redirect('admin:board_job_change',job.pk)

    def duplicate_job_view(self, request, object_id):
        original = get_object_or_404(self.get_queryset(request), pk=object_id)
        if not (self.has_add_permission(request) and self.has_change_permission(request, original)):
            raise PermissionDenied
        return redirect(reverse('admin:board_job_add') + '?' + urlencode({'duplicate_from': original.pk}))


# ---------------------------
# Remaining model admins
# ---------------------------

@admin.register(Application)
class ApplicationAdmin(RecordSearchMixin, admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    fieldsets = (('Applicant and posting', {'fields': ('job','jobseeker',('name','email'))}), ('Application materials', {'fields': ('resume_selected','resume','cover_letter')}))
    list_select_related = ('job', 'jobseeker')
    date_hierarchy = "created_at"

    list_display = ("id", "job", "jobseeker", "created_at")
    list_display_links = ("id", "job")
    search_fields = ("job__title", "jobseeker__email", "jobseeker__first_name", "jobseeker__last_name")
    list_filter = ("created_at",)
    ordering = ("-created_at", "-id")


@admin.register(Resume)
class ResumeAdmin(RecordSearchMixin, admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    fieldsets = (('Résumé', {'fields': ('jobseeker','title','file')}) ,)
    list_select_related = ('jobseeker',)
    date_hierarchy = "created_at"

    list_display = ("id", "jobseeker", "title", "created_at")
    list_display_links = ("id", "jobseeker", "title")
    search_fields = ("jobseeker__email", "title")
    ordering = ("-created_at", "-id")


@admin.register(PostingPackage)
class PostingPackageAdmin(RecordSearchMixin, admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    fieldsets = (('Package', {'fields': (('name','code'),'description','is_active')}), ('Price and posting credits', {'fields': (('price_cents','credits'),('duration_days','package_expires_days'),'allows_featured')}), ('Advanced', {'fields': ('price','is_featured','priority_level','order'), 'classes': ('collapse',)}))

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
class PurchasedPackageAdmin(RecordSearchMixin, admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    fieldsets = (('Purchased package', {'fields': ('employer','package')}), ('Credits', {'fields': (('credits_granted','credits_remaining'),('expires_at','duration_days'),'source')}))
    list_select_related = ('employer', 'package')
    date_hierarchy = "purchased_at"

    def get_list_display(self, request):
        base = ["id", "employer", "package", "credits_granted", "credits_remaining", "purchased_at"]
        if _model_has_field(PurchasedPackage, "expires_at"):
            base.append("expires_at")
        if _model_has_field(PurchasedPackage, "source"):
            base.append("source")
        return tuple(base)

    list_display_links = ("id", "employer", "package")
    search_fields = ("employer__company_name", "employer__email", "package__name")
    list_filter = ("package", "purchased_at")
    ordering = ("-purchased_at", "-id")


@admin.register(Invoice)
class InvoiceAdmin(RecordSearchMixin, admin.ModelAdmin):
    change_form_template = 'admin/workspace/record_editor.html'
    list_select_related = ('employer',)
    date_hierarchy = "order_date"

    list_display = ("id", "employer_link", "amount_display", "currency", "processor", "status", "order_date", "discount_code")
    list_display_links = ("id", "employer_link")
    search_fields = ("employer__company_name", "employer__email", "processor_reference", "discount_code")
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
    change_form_template = 'admin/workspace/record_editor.html'
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
    change_form_template = 'admin/workspace/record_editor.html'
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
    change_form_template = 'admin/workspace/record_editor.html'
    fieldsets = (('Template', {'fields': (('name','key'),'is_enabled','subject','html')}) ,)
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
class JobAlertAdmin(RecordSearchMixin, admin.ModelAdmin):
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
    list_display = DjangoUserAdmin.list_display + ("is_superuser", "is_active", "date_joined")
    list_filter = DjangoUserAdmin.list_filter

# Admin-only social graphic generator. No models or migrations are added.
from .marketing.admin_views import install_marketing_admin_urls
install_marketing_admin_urls()

# Additive workspace; retain all existing model admins and actions.
from .operations import install_operations_urls
install_operations_urls()

from .marketing import admin_contacts as _marketing_contacts_admin

from . import admin_section_admin  # Register the operations models.
