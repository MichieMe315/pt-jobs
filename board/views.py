# board/views.py
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST

from .forms import (
    EmployerSignUpForm,
    JobSeekerSignUpForm,
    JobForm,
    JobApplicationForm,
    JobAlertForm,
    ResumeUploadForm,
    LoginForm,
    validate_no_links_or_emails,
)
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
    PaymentGatewayConfig,
)


# ============================================================
# Email helpers
# ============================================================

def _send_email(subject: str, body: str, to_emails: list[str]) -> None:
    try:
        from django.core.mail import send_mail
        send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), to_emails, fail_silently=True)
    except Exception:
        return


def _admin_emails() -> list[str]:
    admins = getattr(settings, "ADMINS", None)
    if admins:
        return [email for _, email in admins]
    site_admin = getattr(settings, "SITE_ADMIN_EMAIL", None)
    return [site_admin] if site_admin else []


# ============================================================
# Payment gateway helpers (Stripe / PayPal)
# ============================================================

def _gateway_config() -> Optional[PaymentGatewayConfig]:
    try:
        return PaymentGatewayConfig.get_active_gateway()
    except Exception:
        return PaymentGatewayConfig.objects.filter(is_active=True).order_by("-updated_at", "-id").first()


def _gateway_context() -> dict:
    cfg = _gateway_config()
    return {
        # support both key names (your model has both)
        "stripe_publishable_key": getattr(cfg, "stripe_publishable_key", "") if cfg else "",
        "stripe_public_key": getattr(cfg, "stripe_public_key", "") if cfg else "",
        "stripe_secret_key": getattr(cfg, "stripe_secret_key", "") if cfg else "",
        "paypal_client_id": getattr(cfg, "paypal_client_id", "") if cfg else "",
        "paypal_mode": getattr(cfg, "paypal_mode", "sandbox") if cfg else "sandbox",
        "currency": getattr(cfg, "currency", "CAD") if cfg else "CAD",
    }


def _apply_discount(package: PostingPackage, code_raw: str) -> tuple[Optional[DiscountCode], Decimal, Optional[str]]:
    # Keep stable behavior using price (Decimal)
    base = Decimal(str(package.price))
    code = (code_raw or "").strip()
    if not code:
        return None, base, None

    today = timezone.now().date()
    dc = DiscountCode.objects.filter(code__iexact=code, is_active=True).first()
    if not dc:
        return None, base, "Invalid discount code."

    if getattr(dc, "start_date", None) and today < dc.start_date:
        return None, base, "This discount code is not active yet."
    if getattr(dc, "end_date", None) and today > dc.end_date:
        return None, base, "This discount code has expired."

    try:
        if dc.kind == "percent":
            pct = Decimal(str(dc.value))
            final = base * (Decimal("1.0") - (pct / Decimal("100.0")))
        else:
            # dc.value is int cents in your model; convert to dollars
            final = base - (Decimal(int(dc.value or 0)) / Decimal("100"))
    except Exception:
        return None, base, "Invalid discount configuration."

    if final < 0:
        final = Decimal("0.00")
    return dc, final.quantize(Decimal("0.01")), None


# ============================================================
# Credits / package helpers (CONTRACT-SAFE)
# ============================================================

def _available_packages_qs(employer: Employer):
    """
    Contract: credit counter shows UNEXPIRED credits only.

    IMPORTANT FIX:
    - expires_at can be NULL (legacy/dirty data). Treat NULL as "not expired"
      otherwise you get invoices + purchased packages but 0 credits.
    """
    now = timezone.now()
    return (
        PurchasedPackage.objects.filter(employer=employer, credits_remaining__gt=0)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
    )


def _available_credits(employer: Employer) -> int:
    total = _available_packages_qs(employer).aggregate(total=Sum("credits_remaining"))["total"]
    return int(total or 0)


def _sync_employer_credits(employer: Employer) -> None:
    """
    Employer.credits mirrors the package-based unexpired credits.
    """
    try:
        employer.credits = _available_credits(employer)
        employer.save(update_fields=["credits"])
    except Exception:
        return


def _consume_employer_credit(employer: Employer) -> bool:
    """
    Consume exactly ONE credit for the employer.

    Source of truth: PurchasedPackage.credits_remaining (unexpired only).
    Contract-safe: never goes negative.

    NOTE: If there are no PurchasedPackage rows but employer.credits > 0,
    we decrement employer.credits as a last-resort so you don't hard-block
    (explicit behavior; not silent).
    """
    pkg = (
        _available_packages_qs(employer)
        .order_by("expires_at", "id")
        .first()
    )
    if pkg:
        pkg.credits_remaining = max(0, int(pkg.credits_remaining or 0) - 1)
        pkg.save(update_fields=["credits_remaining"])
        _sync_employer_credits(employer)
        return True

    # Explicit last-resort path (ONLY if packages are missing)
    if employer.credits and employer.credits > 0:
        employer.credits = max(0, int(employer.credits) - 1)
        employer.save(update_fields=["credits"])
        return True

    return False


def _posting_duration_days_for_employer(_: Employer) -> int:
    s = SiteSettings.objects.first()
    if s and getattr(s, "posting_duration_days", None):
        try:
            return int(s.posting_duration_days)
        except Exception:
            pass
    return 30


def _max_expiry_date_last_day(posting_date, duration_days: int):
    days = max(1, int(duration_days or 1))
    return posting_date + timedelta(days=days - 1)


# ============================================================
# Public pages
# ============================================================

def home(request: HttpRequest) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()

    jobs = (
        Job.objects.filter(is_active=True)
        .select_related("employer")
        .order_by("-posting_date", "-id")[:3]
    )

    featured_jobs = (
        Job.objects.filter(is_active=True, is_featured=True)
        .select_related("employer")
        .order_by("-posting_date", "-id")[:6]
    )

    job_alert_form = JobAlertForm()

    return render(
        request,
        "board/home.html",
        {
            "sitesettings": sitesettings,
            "jobs": jobs,
            "featured_jobs": featured_jobs,
            "job_alert_form": job_alert_form,
        },
    )


def about(request: HttpRequest) -> HttpResponse:
    return render(request, "board/about.html", {"sitesettings": SiteSettings.objects.first()})


def contact(request: HttpRequest) -> HttpResponse:
    return render(request, "board/contact.html", {"sitesettings": SiteSettings.objects.first()})


def terms(request: HttpRequest) -> HttpResponse:
    return render(request, "board/terms.html", {"sitesettings": SiteSettings.objects.first()})


# ============================================================
# Auth
# ============================================================

def logout_view(request: HttpRequest) -> HttpResponse:
    try:
        list(messages.get_messages(request))
    except Exception:
        pass
    logout(request)
    return redirect("home")


def login_view(request: HttpRequest) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()
    form = LoginForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()

            # Contract: unapproved users cannot log in
            if hasattr(user, "employer") and not user.employer.is_approved:
                messages.error(
                    request,
                    "Your employer account is pending approval. You will receive an email when admin approves your account.",
                )
                return render(request, "board/login.html", {"sitesettings": sitesettings, "form": form})

            if hasattr(user, "jobseeker") and not user.jobseeker.is_approved:
                messages.error(
                    request,
                    "Your job seeker account is pending approval. You will receive an email when admin approves your account.",
                )
                return render(request, "board/login.html", {"sitesettings": sitesettings, "form": form})

            login(request, user)

            nxt = request.GET.get("next")
            if nxt:
                return redirect(nxt)

            if hasattr(user, "employer"):
                return redirect("employer_dashboard")
            if hasattr(user, "jobseeker"):
                return redirect("jobseeker_dashboard")
            return redirect("home")

        messages.error(request, "Please correct the errors below.")

    return render(request, "board/login.html", {"sitesettings": sitesettings, "form": form})


# ============================================================
# Job Alerts
# ============================================================

def job_alert_signup(request: HttpRequest) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()
    form = JobAlertForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        messages.success(request, "Thanks! You’re signed up for job alerts.")
        return redirect("home")
    return render(request, "board/job_alert_signup.html", {"sitesettings": sitesettings, "form": form})


# ============================================================
# Employer signup + list + detail
# ============================================================

def employer_signup(request: HttpRequest) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()
    form = EmployerSignUpForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()

        admin_emails = _admin_emails()
        if admin_emails:
            _send_email("New Employer Signup", f"A new employer signed up: {user.email}", admin_emails)

        messages.success(
            request,
            "Your account has been created. You will be notified via email when admin approves your account.",
        )
        return redirect("login")

    return render(request, "board/employer_signup.html", {"sitesettings": sitesettings, "form": form})


def employer_list(request: HttpRequest) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()

    employers = (
        Employer.objects.annotate(active_jobs=Count("jobs", filter=Q(jobs__is_active=True)))
        .filter(active_jobs__gt=0)
        .order_by("company_name", "id")
    )
    return render(request, "board/employer_list.html", {"sitesettings": sitesettings, "employers": employers})


def employer_detail(request: HttpRequest, employer_id: int) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()
    employer = get_object_or_404(Employer, id=employer_id)
    jobs = Job.objects.filter(employer=employer, is_active=True).order_by("-posting_date", "-id")
    return render(
        request,
        "board/employer_detail.html",
        {"sitesettings": sitesettings, "employer": employer, "jobs": jobs},
    )


# ============================================================
# Job Seeker signup
# ============================================================

def jobseeker_signup(request: HttpRequest) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()
    form = JobSeekerSignUpForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()

        admin_emails = _admin_emails()
        if admin_emails:
            _send_email("New Job Seeker Signup", f"A new job seeker signed up: {user.email}", admin_emails)

        messages.success(request, "Account created. Your job seeker account requires admin approval before login.")
        return redirect("login")

    return render(request, "board/jobseeker_signup.html", {"sitesettings": sitesettings, "form": form})


# ============================================================
# Jobs
# ============================================================

def job_list(request: HttpRequest) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()
    q = (request.GET.get("q") or "").strip()
    loc = (request.GET.get("location") or "").strip()

    qs = Job.objects.filter(is_active=True).select_related("employer")
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(employer__company_name__icontains=q))
    if loc:
        qs = qs.filter(location__icontains=loc)

    jobs = qs.order_by("-posting_date", "-id")
    return render(request, "board/job_list.html", {"sitesettings": sitesettings, "jobs": jobs, "q": q, "location": loc})


def job_detail(request: HttpRequest, job_id: int) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()
    job = get_object_or_404(Job.objects.select_related("employer"), id=job_id)
    job_alert_form = JobAlertForm()
    return render(
        request,
        "board/job_detail.html",
        {"sitesettings": sitesettings, "job": job, "job_alert_form": job_alert_form},
    )


@login_required
def job_create(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    employer = request.user.employer
    if not employer.is_approved:
        messages.error(request, "Your employer account is pending approval.")
        return redirect("employer_dashboard")

    posting_date = timezone.now().date()
    duration_days = _posting_duration_days_for_employer(employer)
    max_expiry = _max_expiry_date_last_day(posting_date, duration_days)

    active_package = _available_packages_qs(employer).order_by("expires_at", "id").first()
    form = JobForm(request.POST or None, max_expiry_date=max_expiry)

    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.employer = employer
        job.posting_date = posting_date

        action = (request.POST.get("action") or "publish").strip().lower()
        publish = action != "draft"
        job.is_active = bool(publish)

        if publish:
            # --- CREDIT CONSUMPTION (REQUIRED) ---
            ok = _consume_employer_credit(employer)
            if not ok:
                # Contract-safe: do not lose work; save as draft, then send to packages
                job.is_active = False
                job.save()

                request.session["pending_create_job_id"] = job.id
                messages.error(
                    request,
                    "No credits available. Your job was saved as a draft. Purchase credits to publish.",
                )
                return redirect("package_list")

        job.save()
        _sync_employer_credits(employer)

        messages.success(request, "Job created.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/job_form.html",
        {
            "form": form,
            "mode": "create",
            "active_package": active_package,
            "max_expiry_iso": max_expiry.isoformat(),
        },
    )


@login_required
def job_edit(request: HttpRequest, job_id: int) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    employer = request.user.employer
    job = get_object_or_404(Job, id=job_id, employer=employer)

    posting_date = job.posting_date or timezone.now().date()
    duration_days = _posting_duration_days_for_employer(employer)
    max_expiry = _max_expiry_date_last_day(posting_date, duration_days)

    active_package = _available_packages_qs(employer).order_by("expires_at", "id").first()
    form = JobForm(request.POST or None, instance=job, max_expiry_date=max_expiry)

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)

        action = (request.POST.get("action") or "publish").strip().lower()
        publish = action != "draft"

        was_inactive = not job.is_active
        updated.is_active = bool(publish)

        if publish and was_inactive:
            # --- CREDIT CONSUMPTION (REQUIRED) ---
            ok = _consume_employer_credit(employer)
            if not ok:
                # Keep it a draft; do not publish
                updated.is_active = False
                updated.save()
                request.session["pending_publish_job_id"] = updated.id
                messages.error(
                    request,
                    "No credits available. This job remains a draft. Purchase credits to publish.",
                )
                return redirect("package_list")

        updated.save()
        _sync_employer_credits(employer)

        messages.success(request, "Job updated.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/job_form.html",
        {
            "form": form,
            "mode": "edit",
            "job": job,
            "active_package": active_package,
            "max_expiry_iso": max_expiry.isoformat(),
        },
    )


@login_required
def job_duplicate(request: HttpRequest, job_id: int) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    employer = request.user.employer
    original = get_object_or_404(Job, id=job_id, employer=employer)

    posting_date = timezone.now().date()
    duration_days = _posting_duration_days_for_employer(employer)
    max_expiry = _max_expiry_date_last_day(posting_date, duration_days)

    active_package = _available_packages_qs(employer).order_by("expires_at", "id").first()

    initial = {
        "title": original.title,
        "description": original.description,
        "job_type": original.job_type,
        "compensation_type": original.compensation_type,
        "compensation_min": original.compensation_min,
        "compensation_max": original.compensation_max,
        "location": original.location,
        "apply_via": original.apply_via,
        "apply_email": original.apply_email,
        "apply_url": original.apply_url,
        "relocation_assistance": "yes" if bool(original.relocation_assistance) else "no",
    }

    form = JobForm(request.POST or None, initial=initial, max_expiry_date=max_expiry)

    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.employer = employer
        job.posting_date = posting_date

        action = (request.POST.get("action") or "publish").strip().lower()
        publish = action != "draft"
        job.is_active = bool(publish)

        if publish:
            # --- CREDIT CONSUMPTION (REQUIRED) ---
            ok = _consume_employer_credit(employer)
            if not ok:
                # save draft, then send to packages (your required flow)
                job.is_active = False
                job.save()

                request.session["pending_duplicate_job_id"] = job.id
                messages.error(
                    request,
                    "No credits available. Your duplicated job was saved as a draft. Purchase credits to publish.",
                )
                return redirect("package_list")

        job.save()
        _sync_employer_credits(employer)

        messages.success(request, "Job duplicated.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/job_form.html",
        {
            "form": form,
            "mode": "duplicate",
            "active_package": active_package,
            "max_expiry_iso": max_expiry.isoformat(),
            "original": original,
        },
    )


def job_apply(request: HttpRequest, job_id: int) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={reverse('job_apply', args=[job_id])}")

    if not hasattr(request.user, "jobseeker"):
        return redirect("home")

    js = request.user.jobseeker
    if not js.is_approved:
        messages.error(request, "Your job seeker account is pending approval.")
        return redirect("jobseeker_dashboard")

    job = get_object_or_404(Job.objects.select_related("employer"), id=job_id, is_active=True)
    resumes = Resume.objects.filter(jobseeker=js).order_by("-created_at", "-id")

    form = JobApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        resume_id = (request.POST.get("resume_id") or "").strip()
        resume_obj = resumes.filter(id=resume_id).first() if resume_id else None

        if resume_obj is None:
            messages.error(request, "Please select a resume to attach.")
        else:
            app = form.save(commit=False)
            app.job = job
            app.jobseeker = js
            app.resume_selected = resume_obj
            app.save()
            messages.success(request, "Application submitted.")
            return redirect("jobseeker_dashboard")

    return render(
        request,
        "board/job_apply.html",
        {
            "sitesettings": SiteSettings.objects.first(),
            "job": job,
            "form": form,
            "jobseeker": js,
            "resumes": resumes,
        },
    )


# ============================================================
# Dashboards
# ============================================================

@login_required
def employer_dashboard(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    employer = request.user.employer
    _sync_employer_credits(employer)

    jobs = Job.objects.filter(employer=employer).order_by("-posting_date", "-id")
    applications = (
        Application.objects.filter(job__employer=employer)
        .select_related("job", "jobseeker")
        .order_by("-created_at", "-id")
    )
    invoices = Invoice.objects.filter(employer=employer).order_by("-order_date", "-id")

    # Both keys are passed to avoid breaking anything:
    packages = PurchasedPackage.objects.filter(employer=employer).order_by("-purchased_at", "-id")
    purchased_packages = packages

    return render(
        request,
        "board/employer_dashboard.html",
        {
            "sitesettings": SiteSettings.objects.first(),
            "employer": employer,
            "jobs": jobs,
            "applications": applications,
            "invoices": invoices,
            "packages": packages,
            "purchased_packages": purchased_packages,  # template expects this :contentReference[oaicite:2]{index=2}
            "credits_available": _available_credits(employer),
            "available_credits": _available_credits(employer),
        },
    )


@login_required
def jobseeker_dashboard(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "jobseeker"):
        raise PermissionDenied

    js = request.user.jobseeker
    resumes = Resume.objects.filter(jobseeker=js).order_by("-created_at", "-id")
    applications = (
        Application.objects.filter(jobseeker=js)
        .select_related("job", "job__employer")
        .order_by("-created_at", "-id")
    )

    upload_form = ResumeUploadForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and upload_form.is_valid():
        r = upload_form.save(commit=False)
        r.jobseeker = js
        r.save()
        messages.success(request, "Resume uploaded.")
        return redirect("jobseeker_dashboard")

    return render(
        request,
        "board/jobseeker_dashboard.html",
        {
            "sitesettings": SiteSettings.objects.first(),
            "jobseeker": js,
            "resumes": resumes,
            "applications": applications,
            "upload_form": upload_form,
        },
    )


# ============================================================
# Profile edit forms + views
# ============================================================

YES_NO_CHOICES = (("yes", "Yes"), ("no", "No"))


class EmployerProfileEditForm(forms.ModelForm):
    company_description = forms.CharField(required=False, widget=forms.Textarea)

    class Meta:
        model = Employer
        fields = ("company_name", "company_description", "phone", "website", "location", "logo")

    def clean_company_description(self):
        val = self.cleaned_data.get("company_description") or ""
        validate_no_links_or_emails(val)
        return val


class JobSeekerProfileEditForm(forms.ModelForm):
    registered_in_canada = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)
    open_to_relocate = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)
    require_sponsorship = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)
    seeking_immigration = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)

    class Meta:
        model = JobSeeker
        fields = (
            "first_name",
            "last_name",
            "position_desired",
            "opportunity_type",
            "current_location",
            "relocate_where",
        )

    def save(self, commit=True):
        inst = super().save(commit=False)

        def _to_bool(v: str) -> bool:
            return True if (v or "").lower() == "yes" else False

        inst.registered_in_canada = _to_bool(self.cleaned_data.get("registered_in_canada", "no"))
        inst.open_to_relocate = _to_bool(self.cleaned_data.get("open_to_relocate", "no"))
        inst.require_sponsorship = _to_bool(self.cleaned_data.get("require_sponsorship", "no"))
        inst.seeking_immigration = _to_bool(self.cleaned_data.get("seeking_immigration", "no"))

        if commit:
            inst.save()
        return inst


@login_required
def employer_profile_edit(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    employer = request.user.employer
    form = EmployerProfileEditForm(request.POST or None, request.FILES or None, instance=employer)

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.is_approved = False
        updated.save()

        admin_emails = _admin_emails()
        if admin_emails:
            _send_email(
                "Employer Profile Updated (Approval Needed)",
                f"Employer updated profile: {updated.email}",
                admin_emails,
            )

        messages.success(request, "Profile updated. Your account is pending re-approval.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/employer_profile_edit.html",
        {"sitesettings": SiteSettings.objects.first(), "form": form, "employer": employer},
    )


@login_required
def jobseeker_profile_edit(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "jobseeker"):
        raise PermissionDenied

    js = request.user.jobseeker
    form = JobSeekerProfileEditForm(request.POST or None, request.FILES or None, instance=js)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("jobseeker_dashboard")

    return render(
        request,
        "board/jobseeker_profile_edit.html",
        {"sitesettings": SiteSettings.objects.first(), "form": form, "jobseeker": js},
    )


# ============================================================
# Packages + checkout
# ============================================================

def package_list(request: HttpRequest) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()
    packages = PostingPackage.objects.filter(is_active=True).order_by("-priority_level", "price", "id")
    ctx = {"sitesettings": sitesettings, "packages": packages}
    ctx.update(_gateway_context())
    return render(request, "board/package_list.html", ctx)


def buy_package(request: HttpRequest, package_id: int) -> HttpResponse:
    return redirect("checkout_select", package_id=package_id)


def checkout_select(request: HttpRequest, package_id: int) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={reverse('checkout_select', args=[package_id])}")

    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    package = get_object_or_404(PostingPackage, id=package_id, is_active=True)
    ctx = {"sitesettings": SiteSettings.objects.first(), "package": package}
    ctx.update(_gateway_context())
    return render(request, "checkout/checkout_select.html", ctx)


@login_required
def checkout_start(request: HttpRequest, package_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("checkout_select", package_id=package_id)

    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    package = get_object_or_404(PostingPackage, id=package_id, is_active=True)

    payment_method = (request.POST.get("payment_method") or "card").strip().lower()
    discount_code = (request.POST.get("discount_code") or "").strip()

    dc, final_amount, err = _apply_discount(package, discount_code)
    if err:
        messages.error(request, err)
        return redirect("checkout_select", package_id=package_id)

    if payment_method in ("card", "stripe"):
        gw = _gateway_context()
        secret = gw.get("stripe_secret_key")
        if not secret:
            messages.error(request, "Stripe is not configured.")
            return redirect("checkout_select", package_id=package_id)

        import stripe
        stripe.api_key = secret

        amount_cents = int(round(final_amount * 100))

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "cad",
                            "product_data": {"name": package.name},
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                success_url=request.build_absolute_uri(reverse("checkout_success")) + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=request.build_absolute_uri(reverse("checkout_select", args=[package.id])),
                metadata={
                    "employer_id": str(request.user.employer.id),
                    "package_id": str(package.id),
                    "discount_code": dc.code if dc else "",
                },
            )
        except Exception:
            messages.error(request, "Unable to start Stripe checkout.")
            return redirect("checkout_select", package_id=package_id)

        return redirect(session.url)

    ctx = {
        "sitesettings": SiteSettings.objects.first(),
        "package": package,
        "payment_method": payment_method,
        "discount_code": discount_code,
        "final_amount": final_amount,
    }
    ctx.update(_gateway_context())
    return render(request, "checkout/checkout.html", ctx)


@login_required
def checkout_success(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    employer = request.user.employer
    session_id = (request.GET.get("session_id") or "").strip()

    if session_id:
        gw = _gateway_context()
        secret = gw.get("stripe_secret_key")
        if not secret:
            messages.error(request, "Stripe is not configured.")
            return redirect("package_list")

        import stripe
        stripe.api_key = secret

        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except Exception:
            messages.error(request, "Unable to verify Stripe payment session.")
            return redirect("package_list")

        if getattr(session, "payment_status", None) != "paid":
            messages.error(request, "Payment not completed.")
            return redirect("package_list")

        md = getattr(session, "metadata", {}) or {}
        try:
            pkg_id = int(md.get("package_id") or 0)
        except Exception:
            pkg_id = 0

        package = get_object_or_404(PostingPackage, id=pkg_id, is_active=True)

        existing = Invoice.objects.filter(processor="stripe", processor_reference=session_id).first()
        if not existing:
            amount_cents = int(getattr(session, "amount_total", None) or (package.price_cents or 0))
            used_code = (md.get("discount_code") or "").strip() or ""

            Invoice.objects.create(
                employer=employer,
                amount=amount_cents,          # cents int
                currency="CAD",
                processor="stripe",
                status="paid",
                processor_reference=session_id,
                discount_code=used_code,
            )

            PurchasedPackage.objects.create(
                employer=employer,
                package=package,
                credits_granted=int(package.credits),
                credits_remaining=int(package.credits),
                duration_days=int(package.duration_days),
                source="stripe",
            )

        # ALWAYS resync credits after purchase
        _sync_employer_credits(employer)

        # If they came here because of a pending draft/duplicate, send them back to edit it
        pending_dup_id = request.session.pop("pending_duplicate_job_id", None)
        pending_create_id = request.session.pop("pending_create_job_id", None)
        pending_publish_id = request.session.pop("pending_publish_job_id", None)

        target_id = pending_dup_id or pending_create_id or pending_publish_id
        if target_id:
            messages.success(request, "Credits added. You can now publish your saved draft.")
            return redirect("job_edit", job_id=int(target_id))

        return render(
            request,
            "checkout/checkout_success.html",
            {"sitesettings": SiteSettings.objects.first(), "package": package},
        )

    return redirect("package_list")


@login_required
def paypal_success(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    employer = request.user.employer
    package_id = request.GET.get("package_id")
    amount = request.GET.get("amount")
    discount_code = (request.GET.get("discount_code") or "").strip() or ""

    if not package_id:
        return redirect("package_list")

    package = get_object_or_404(PostingPackage, id=int(package_id), is_active=True)

    try:
        paid_cents = int((Decimal(str(amount)) * Decimal("100")).quantize(Decimal("1")))
    except Exception:
        paid_cents = int(package.price_cents or 0)

    existing = (
        Invoice.objects.filter(processor="paypal", employer=employer, amount=paid_cents, status="paid")
        .order_by("-order_date")
        .first()
    )
    if not existing:
        Invoice.objects.create(
            employer=employer,
            amount=paid_cents,
            currency="CAD",
            processor="paypal",
            status="paid",
            processor_reference="",
            discount_code=discount_code,
        )
        PurchasedPackage.objects.create(
            employer=employer,
            package=package,
            credits_granted=int(package.credits),
            credits_remaining=int(package.credits),
            duration_days=int(package.duration_days),
            source="paypal",
        )

    _sync_employer_credits(employer)

    messages.success(request, "Purchase successful. Credits added.")
    return render(
        request,
        "checkout/checkout_success.html",
        {"sitesettings": SiteSettings.objects.first(), "package": package},
    )


@require_POST
@login_required
def stripe_create_session(request: HttpRequest, package_id: int) -> JsonResponse:
    if not hasattr(request.user, "employer"):
        return JsonResponse({"error": "Employer login required."}, status=403)

    employer = request.user.employer
    package = get_object_or_404(PostingPackage, id=package_id, is_active=True)

    gw = _gateway_context()
    secret = gw.get("stripe_secret_key")
    if not secret:
        return JsonResponse({"error": "Stripe is not configured."}, status=400)

    discount_code = (request.POST.get("discount_code") or "").strip()
    dc, final_amount, err = _apply_discount(package, discount_code)
    if err:
        return JsonResponse({"error": err}, status=400)

    import stripe
    stripe.api_key = secret

    amount_cents = int(round(final_amount * 100))

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "cad",
                        "product_data": {"name": package.name},
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=request.build_absolute_uri(reverse("checkout_success")) + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=request.build_absolute_uri(reverse("checkout_select", args=[package.id])),
            metadata={
                "employer_id": str(employer.id),
                "package_id": str(package.id),
                "discount_code": dc.code if dc else "",
            },
        )
    except Exception:
        return JsonResponse({"error": "Unable to start Stripe checkout."}, status=500)

    return JsonResponse({"id": session.id})


# ============================================================
# Invoices
# ============================================================

@login_required
def invoice_detail(request: HttpRequest, invoice_id: int) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    employer = request.user.employer
    invoice = get_object_or_404(Invoice, id=invoice_id, employer=employer)

    return render(
        request,
        "billing/invoice_detail.html",
        {
            "sitesettings": SiteSettings.objects.first(),
            "invoice": invoice,
            "employer": employer,
        },
    )


@login_required
def invoice_download(request: HttpRequest, invoice_id: int) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied
    return redirect("invoice_detail", invoice_id=invoice_id)


# ============================================================
# Admin dashboard (embedded)
# ============================================================

@login_required
@xframe_options_exempt
def admin_dashboard(request: HttpRequest) -> HttpResponse:
    if not request.user.is_staff:
        raise PermissionDenied
    return render(request, "admin/dashboard.html")
