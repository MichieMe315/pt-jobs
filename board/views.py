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
# Site / Approval / Expiry helpers
# ============================================================

def _sitesettings() -> Optional[SiteSettings]:
    return SiteSettings.objects.first()


def _enforce_approval_or_logout(request: HttpRequest) -> bool:
    """
    Contract:
      - Unapproved users cannot be logged in
      - If approval is revoked while logged in (e.g. employer profile edit),
        boot them immediately.
    Returns True if session remains valid, False if we logged them out.
    """
    user = request.user
    if not user.is_authenticated:
        return True
    if user.is_staff or user.is_superuser:
        return True

    if hasattr(user, "employer"):
        emp = user.employer
        if getattr(emp, "login_active", True) is False:
            logout(request)
            messages.error(request, "Your employer account is disabled.")
            return False
        if getattr(emp, "is_approved", False) is False:
            logout(request)
            messages.error(request, "Your employer account is pending approval.")
            return False

    if hasattr(user, "jobseeker"):
        js = user.jobseeker
        if getattr(js, "login_active", True) is False:
            logout(request)
            messages.error(request, "Your job seeker account is disabled.")
            return False
        if getattr(js, "is_approved", False) is False:
            logout(request)
            messages.error(request, "Your job seeker account is pending approval.")
            return False

    return True


def _posting_duration_days() -> int:
    ss = _sitesettings()
    if ss and getattr(ss, "posting_duration_days", None):
        try:
            return int(ss.posting_duration_days)
        except Exception:
            pass
    return 30


def _max_expiry_date(posting_date) -> object:
    # Contract: max expiry = posting_date + posting_duration_days (server-side enforced)
    days = max(1, int(_posting_duration_days() or 1))
    # inclusive end-date behavior: last day = posting_date + (days - 1)
    return posting_date + timedelta(days=days - 1)


def _clamp_expiry(posting_date, expiry_date):
    max_exp = _max_expiry_date(posting_date)
    if not expiry_date:
        return max_exp
    if expiry_date > max_exp:
        return max_exp
    return expiry_date


def _deactivate_expired_jobs() -> int:
    """
    HARD REQUIREMENT: expired jobs must stop being active.
    Safe DB update: flip is_active=False where expiry_date < today.
    """
    today = timezone.localdate()
    return Job.objects.filter(
        is_active=True,
        expiry_date__isnull=False,
        expiry_date__lt=today,
    ).update(is_active=False)


def _active_jobs_qs():
    """
    Even if some stale rows still have is_active=True,
    NEVER show expired jobs publicly.
    """
    today = timezone.localdate()
    return Job.objects.filter(is_active=True).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))


# ============================================================
# Email helpers (Admin-controlled EmailTemplate)
# ============================================================

def _default_from_email() -> str:
    return getattr(settings, "DEFAULT_FROM_EMAIL", None) or "info@physiotherapyjobscanada.ca"


def _admin_emails() -> list[str]:
    """
    CONTRACT: admin notification recipient comes from SiteSettings (admin-managed).
    Field: SiteSettings.contact_email  (Admin label: "Contact email")
    """
    ss = _sitesettings()
    if not ss:
        return []

    email = (getattr(ss, "contact_email", "") or "").strip()
    return [email] if email else []


def _render_tokens(text: str, context: dict) -> str:
    out = text or ""
    for k, v in (context or {}).items():
        out = out.replace("{{ " + str(k) + " }}", str(v))
        out = out.replace("{{" + str(k) + "}}", str(v))
    return out


def send_templated_email(key: str, to_emails: list[str], context: dict) -> bool:
    """
    Contract-safe:
      - Only sends if EmailTemplate(key) exists AND is_enabled=True AND has subject+html
      - No silent fallback body content
    """
    to_emails = [e.strip() for e in (to_emails or []) if (e or "").strip()]
    if not to_emails:
        return False

    tmpl = EmailTemplate.objects.filter(key=key, is_enabled=True).first()
    if not tmpl:
        return False

    subject_raw = (tmpl.subject or "").strip()
    html_raw = (tmpl.html or "").strip()
    if not subject_raw or not html_raw:
        return False

    subject = _render_tokens(subject_raw, context).strip()
    html_body = _render_tokens(html_raw, context).strip()
    if not subject or not html_body:
        return False

    try:
        from django.core.mail import EmailMultiAlternatives
        msg = EmailMultiAlternatives(subject, "", _default_from_email(), to_emails)
        msg.attach_alternative(html_body, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception:
        return False


# ============================================================
# Payment gateway helpers (Stripe / PayPal)
# ============================================================

def _gateway_config() -> Optional[PaymentGatewayConfig]:
    try:
        return PaymentGatewayConfig.get_active_gateway()
    except Exception:
        return PaymentGatewayConfig.objects.filter(is_active=True).order_by("-updated_at", "-id").first()


def _stripe_enabled(cfg: Optional[PaymentGatewayConfig]) -> bool:
    if not cfg:
        return False
    pub = (getattr(cfg, "stripe_public_key", "") or getattr(cfg, "stripe_publishable_key", "") or "").strip()
    sec = (getattr(cfg, "stripe_secret_key", "") or "").strip()
    return bool(getattr(cfg, "use_stripe", False) and pub and sec)


def _paypal_enabled(cfg: Optional[PaymentGatewayConfig]) -> bool:
    if not cfg:
        return False
    cid = (getattr(cfg, "paypal_client_id", "") or "").strip()
    csec = (getattr(cfg, "paypal_client_secret", "") or getattr(cfg, "paypal_secret", "") or "").strip()
    return bool(getattr(cfg, "use_paypal", False) and cid and csec)


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
        "use_stripe": _stripe_enabled(cfg),
        "use_paypal": _paypal_enabled(cfg),
    }


def _apply_discount(package: PostingPackage, code_raw: str) -> tuple[Optional[DiscountCode], Decimal, Optional[str]]:
    # Keep stable behavior using Decimal price
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
    expires_at can be NULL -> treat NULL as not expired.
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
    try:
        employer.credits = _available_credits(employer)
        employer.save(update_fields=["credits"])
    except Exception:
        return


def _consume_employer_credit(employer: Employer) -> bool:
    """
    Credit is consumed ONLY when a job is published (not draft, not duplicate).
    """
    pkg = _available_packages_qs(employer).order_by("expires_at", "id").first()
    if pkg:
        pkg.credits_remaining = max(0, int(pkg.credits_remaining or 0) - 1)
        pkg.save(update_fields=["credits_remaining"])
        _sync_employer_credits(employer)
        return True

    # explicit last-resort path (ONLY if packages are missing)
    if employer.credits and employer.credits > 0:
        employer.credits = max(0, int(employer.credits) - 1)
        employer.save(update_fields=["credits"])
        return True

    return False


# ============================================================
# Public pages
# ============================================================

def home(request: HttpRequest) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    jobs = (
        _active_jobs_qs()
        .select_related("employer")
        .order_by("-posting_date", "-id")[:3]
    )
    featured_jobs = (
        _active_jobs_qs()
        .filter(is_featured=True)
        .select_related("employer")
        .order_by("-posting_date", "-id")[:6]
    )
    job_alert_form = JobAlertForm()

    return render(
        request,
        "board/home.html",
        {
            "sitesettings": ss,
            "jobs": jobs,
            "featured_jobs": featured_jobs,
            "job_alert_form": job_alert_form,
        },
    )


def about(request: HttpRequest) -> HttpResponse:
    return render(request, "board/about.html", {"sitesettings": _sitesettings()})


def contact(request: HttpRequest) -> HttpResponse:
    return render(request, "board/contact.html", {"sitesettings": _sitesettings()})


def terms(request: HttpRequest) -> HttpResponse:
    return render(request, "board/terms.html", {"sitesettings": _sitesettings()})


# ============================================================
# Auth
# ============================================================

def logout_view(request: HttpRequest) -> HttpResponse:
    # Logout must never crash. Do NOT touch employer/jobseeker objects here.
    try:
        logout(request)
    except Exception:
        pass
    return redirect("home")


def login_view(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
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
                return render(request, "board/login.html", {"sitesettings": ss, "form": form})

            if hasattr(user, "jobseeker") and not user.jobseeker.is_approved:
                messages.error(
                    request,
                    "Your job seeker account is pending approval. You will receive an email when admin approves your account.",
                )
                return render(request, "board/login.html", {"sitesettings": ss, "form": form})

            login(request, user)

            # safety: if approval revoked between credential check and session
            if not getattr(request.user.employer, "is_approved", True):
                pass

            nxt = request.GET.get("next")
            if nxt:
                return redirect(nxt)

            if hasattr(user, "employer"):
                return redirect("employer_dashboard")
            if hasattr(user, "jobseeker"):
                return redirect("jobseeker_dashboard")
            return redirect("home")

        messages.error(request, "Please correct the errors below.")

    return render(request, "board/login.html", {"sitesettings": ss, "form": form})


# ============================================================
# Job Alerts
# ============================================================

def job_alert_signup(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    form = JobAlertForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        # form.save() may exist in your form; if not, just keep success message
        try:
            form.save()
        except Exception:
            pass
        messages.success(request, "Thanks! You’re signed up for job alerts.")
        return redirect("home")
    return render(request, "board/job_alert_signup.html", {"sitesettings": ss, "form": form})


# ============================================================
# Employer signup + list + detail
# ============================================================

def employer_signup(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    form = EmployerSignUpForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()

        # Admin notification + optional welcome (admin-controlled templates)
        admin_emails = _admin_emails()
        send_templated_email("admin_new_employer", admin_emails, {"email": user.email})
        send_templated_email("employer_welcome", [user.email], {"email": user.email, "login_url": reverse("login")})


        messages.success(
            request,
            "Your account has been created. You will be notified via email when admin approves your account.",
        )
        return redirect("login")

    return render(request, "board/employer_signup.html", {"sitesettings": ss, "form": form})


def employer_list(request: HttpRequest) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    employers = (
        Employer.objects.annotate(active_jobs=Count("jobs", filter=Q(jobs__is_active=True)))
        .filter(active_jobs__gt=0)
        .order_by("company_name", "id")
    )
    return render(request, "board/employer_list.html", {"sitesettings": ss, "employers": employers})


def employer_detail(request: HttpRequest, employer_id: int) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    employer = get_object_or_404(Employer, id=employer_id)
    jobs = _active_jobs_qs().filter(employer=employer).order_by("-posting_date", "-id")

    return render(
        request,
        "board/employer_detail.html",
        {"sitesettings": ss, "employer": employer, "jobs": jobs},
    )


# ============================================================
# Job Seeker signup
# ============================================================

def jobseeker_signup(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    form = JobSeekerSignUpForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()

        admin_emails = _admin_emails()
        send_templated_email("admin_new_jobseeker", admin_emails, {"email": user.email})
        send_templated_email("jobseeker_welcome", [user.email], {"email": user.email, "login_url": reverse("login")})

        messages.success(request, "Account created. Your job seeker account requires admin approval before login.")
        return redirect("login")

    return render(request, "board/jobseeker_signup.html", {"sitesettings": ss, "form": form})


# ============================================================
# Jobs
# ============================================================

def job_list(request: HttpRequest) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    q = (request.GET.get("q") or "").strip()
    loc = (request.GET.get("location") or "").strip()
    job_type = (request.GET.get("job_type") or "").strip()

    qs = _active_jobs_qs().select_related("employer")

    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(employer__company_name__icontains=q))
    if loc:
        qs = qs.filter(location__icontains=loc)
    if job_type:
        qs = qs.filter(job_type=job_type)

    jobs = qs.order_by("-posting_date", "-id")
    return render(
        request,
        "board/job_list.html",
        {"sitesettings": ss, "jobs": jobs, "q": q, "location": loc, "job_type": job_type},
    )


def job_detail(request: HttpRequest, job_id: int) -> HttpResponse:
    _deactivate_expired_jobs()
    ss = _sitesettings()

    # allow viewing inactive detail page if template expects it; but keep public list filtered
    job = get_object_or_404(Job.objects.select_related("employer"), id=job_id)
    job_alert_form = JobAlertForm()
    return render(
        request,
        "board/job_detail.html",
        {"sitesettings": ss, "job": job, "job_alert_form": job_alert_form},
    )


@login_required
def job_create(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = request.user.employer

    posting_date = timezone.localdate()
    max_expiry = _max_expiry_date(posting_date)

    active_package = _available_packages_qs(employer).order_by("expires_at", "id").first()
    form = JobForm(request.POST or None, max_expiry_date=max_expiry)

    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.employer = employer
        job.posting_date = posting_date

        # HARD expiry clamp server-side
        job.expiry_date = _clamp_expiry(posting_date, getattr(job, "expiry_date", None))

        action = (request.POST.get("action") or "publish").strip().lower()
        publish = action != "draft"
        job.is_active = bool(publish)

        if publish:
            ok = _consume_employer_credit(employer)
            if not ok:
                job.is_active = False
                job.save()
                request.session["pending_create_job_id"] = job.id
                messages.error(request, "No credits available. Your job was saved as a draft. Purchase credits to publish.")
                return redirect("package_list")

        job.save()
        _sync_employer_credits(employer)

        # Optional employer confirmation email (admin-controlled)
        send_templated_email(
            "job_posting_confirmation",
            [(employer.email or "").strip()],
            {"job_title": job.title, "email": employer.email, "dashboard_url": request.build_absolute_uri(reverse("employer_dashboard"))},
        )

        messages.success(request, "Job created.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/job_form.html",
        {
            "sitesettings": ss,
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

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = request.user.employer
    job = get_object_or_404(Job, id=job_id, employer=employer)

    posting_date = job.posting_date or timezone.localdate()
    max_expiry = _max_expiry_date(posting_date)

    active_package = _available_packages_qs(employer).order_by("expires_at", "id").first()
    form = JobForm(request.POST or None, instance=job, max_expiry_date=max_expiry)

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)

        # HARD expiry clamp server-side
        updated.posting_date = posting_date
        updated.expiry_date = _clamp_expiry(posting_date, getattr(updated, "expiry_date", None))

        action = (request.POST.get("action") or "publish").strip().lower()
        publish = action != "draft"

        was_inactive = not job.is_active
        updated.is_active = bool(publish)

        if publish and was_inactive:
            ok = _consume_employer_credit(employer)
            if not ok:
                updated.is_active = False
                updated.save()
                request.session["pending_publish_job_id"] = updated.id
                messages.error(request, "No credits available. This job remains a draft. Purchase credits to publish.")
                return redirect("package_list")

        updated.save()
        _sync_employer_credits(employer)

        messages.success(request, "Job updated.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/job_form.html",
        {
            "sitesettings": ss,
            "form": form,
            "mode": "edit",
            "job": job,
            "active_package": active_package,
            "max_expiry_iso": max_expiry.isoformat(),
        },
    )


@login_required
def job_duplicate(request: HttpRequest, job_id: int) -> HttpResponse:
    """
    Employer duplicate:
      - opens standard job form
      - does NOT consume credit until publish
      - expiry is recalculated + clamped
    """
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = request.user.employer
    original = get_object_or_404(Job, id=job_id, employer=employer)

    posting_date = timezone.localdate()
    max_expiry = _max_expiry_date(posting_date)

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
        "expiry_date": max_expiry,
    }

    form = JobForm(request.POST or None, initial=initial, max_expiry_date=max_expiry)

    if request.method == "POST" and form.is_valid():
        job = form.save(commit=False)
        job.employer = employer
        job.posting_date = posting_date

        # HARD expiry clamp server-side
        job.expiry_date = _clamp_expiry(posting_date, getattr(job, "expiry_date", None))

        action = (request.POST.get("action") or "publish").strip().lower()
        publish = action != "draft"
        job.is_active = bool(publish)

        if publish:
            ok = _consume_employer_credit(employer)
            if not ok:
                job.is_active = False
                job.save()
                request.session["pending_duplicate_job_id"] = job.id
                messages.error(request, "No credits available. Your duplicated job was saved as a draft. Purchase credits to publish.")
                return redirect("package_list")

        job.save()
        _sync_employer_credits(employer)

        messages.success(request, "Job duplicated.")
        return redirect("employer_dashboard")

    return render(
        request,
        "board/job_form.html",
        {
            "sitesettings": ss,
            "form": form,
            "mode": "duplicate",
            "active_package": active_package,
            "max_expiry_iso": max_expiry.isoformat(),
            "original": original,
        },
    )


def job_apply(request: HttpRequest, job_id: int) -> HttpResponse:
    _deactivate_expired_jobs()

    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={reverse('apply_to_job', args=[job_id])}")

    if not hasattr(request.user, "jobseeker"):
        return redirect("home")

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    js = request.user.jobseeker

    job = get_object_or_404(_active_jobs_qs().select_related("employer"), id=job_id)
    resumes = Resume.objects.filter(jobseeker=js).order_by("-created_at", "-id")

    form = JobApplicationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        resume_id = (request.POST.get("resume_id") or "").strip()
        resume_obj = resumes.filter(id=resume_id).first() if resume_id else None

        if resume_obj is None:
            messages.error(request, "Please select a resume to attach.")
        else:
            # prevent duplicates
            if Application.objects.filter(job=job, jobseeker=js).exists():
                messages.info(request, "You’ve already applied to this job.")
                return redirect("job_detail", job_id=job.id)

            app = form.save(commit=False)
            app.job = job
            app.jobseeker = js
            app.resume_selected = resume_obj
            app.save()

            # Employer notification email (admin-controlled)
            employer_email = (job.apply_email or job.employer.email or "").strip()
            send_templated_email(
                "application_email_to_employer",
                [employer_email] if employer_email else [],
                {
                    "job_title": job.title,
                    "employer_name": job.employer.company_name or job.employer.email,
                    "dashboard_url": request.build_absolute_uri(reverse("employer_dashboard")),
                },
            )

            # Jobseeker confirmation (admin-controlled)
            send_templated_email(
                "jobseeker_application_confirmation",
                [(js.email or request.user.email or "").strip()],
                {"job_title": job.title, "jobs_url": request.build_absolute_uri(reverse("job_list"))},
            )

            messages.success(request, "Application submitted.")
            return redirect("jobseeker_dashboard")

    return render(
        request,
        "board/job_apply.html",
        {
            "sitesettings": ss,
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
    _deactivate_expired_jobs()

    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = request.user.employer
    _sync_employer_credits(employer)

    jobs = Job.objects.filter(employer=employer).order_by("-posting_date", "-id")
    applications = (
        Application.objects.filter(job__employer=employer)
        .select_related("job", "jobseeker")
        .order_by("-created_at", "-id")
    )
    invoices = Invoice.objects.filter(employer=employer).order_by("-order_date", "-id")

    packages = PurchasedPackage.objects.filter(employer=employer).order_by("-purchased_at", "-id")
    purchased_packages = packages  # template compatibility

    return render(
        request,
        "board/employer_dashboard.html",
        {
            "sitesettings": ss,
            "employer": employer,
            "jobs": jobs,
            "applications": applications,
            "invoices": invoices,
            "packages": packages,
            "purchased_packages": purchased_packages,
            "credits_available": _available_credits(employer),
            "available_credits": _available_credits(employer),
        },
    )


@login_required
def jobseeker_dashboard(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "jobseeker"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
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
            "sitesettings": ss,
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

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    employer = request.user.employer
    form = EmployerProfileEditForm(request.POST or None, request.FILES or None, instance=employer)

    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)

        # Contract: profile edit triggers re-approval
        updated.is_approved = False
        updated.save()

        # Admin notification (admin-controlled)
        send_templated_email("admin_new_employer", _admin_emails(), {"email": updated.email})

        # Contract: login blocked until re-approved -> force logout
        logout(request)
        messages.success(request, "Profile updated. Your account is pending re-approval.")
        return redirect("login")

    return render(
        request,
        "board/employer_profile_edit.html",
        {"sitesettings": ss, "form": form, "employer": employer},
    )


@login_required
def jobseeker_profile_edit(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "jobseeker"):
        raise PermissionDenied

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    ss = _sitesettings()
    js = request.user.jobseeker
    form = JobSeekerProfileEditForm(request.POST or None, request.FILES or None, instance=js)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("jobseeker_dashboard")

    return render(
        request,
        "board/jobseeker_profile_edit.html",
        {"sitesettings": ss, "form": form, "jobseeker": js},
    )


# ============================================================
# Packages + checkout
# ============================================================

def package_list(request: HttpRequest) -> HttpResponse:
    ss = _sitesettings()
    packages = PostingPackage.objects.filter(is_active=True).order_by("-priority_level", "price", "id")
    ctx = {"sitesettings": ss, "packages": packages}
    ctx.update(_gateway_context())
    return render(request, "board/package_list.html", ctx)


def buy_package(request: HttpRequest, package_id: int) -> HttpResponse:
    return redirect("checkout_select", package_id=package_id)


def checkout_select(request: HttpRequest, package_id: int) -> HttpResponse:
    if not request.user.is_authenticated:
        return redirect(f"{reverse('login')}?next={reverse('checkout_select', args=[package_id])}")

    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    package = get_object_or_404(PostingPackage, id=package_id, is_active=True)
    ctx = {"sitesettings": _sitesettings(), "package": package}
    ctx.update(_gateway_context())
    return render(request, "checkout/checkout_select.html", ctx)


@login_required
def checkout_start(request: HttpRequest, package_id: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("checkout_select", package_id=package_id)

    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    package = get_object_or_404(PostingPackage, id=package_id, is_active=True)

    payment_method = (request.POST.get("payment_method") or "card").strip().lower()
    discount_code = (request.POST.get("discount_code") or "").strip()

    dc, final_amount, err = _apply_discount(package, discount_code)
    if err:
        messages.error(request, err)
        return redirect("checkout_select", package_id=package_id)

    gw = _gateway_context()

    if payment_method in ("card", "stripe"):
        secret = (gw.get("stripe_secret_key") or "").strip()
        if not secret or not gw.get("use_stripe"):
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

    if payment_method == "paypal":
        # Contract requirement: PayPal only if configured in admin
        if not gw.get("use_paypal"):
            messages.error(request, "PayPal is not configured.")
            return redirect("checkout_select", package_id=package_id)

    ctx = {
        "sitesettings": _sitesettings(),
        "package": package,
        "payment_method": payment_method,
        "discount_code": discount_code,
        "final_amount": final_amount,
    }
    ctx.update(gw)
    return render(request, "checkout/checkout.html", ctx)


@login_required
def checkout_success(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    employer = request.user.employer
    session_id = (request.GET.get("session_id") or "").strip()

    if not session_id:
        return redirect("package_list")

    gw = _gateway_context()
    secret = (gw.get("stripe_secret_key") or "").strip()
    if not secret or not gw.get("use_stripe"):
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

    existing = Invoice.objects.filter(
        processor="stripe",
        processor_reference=session_id
    ).first()

    if not existing:

        amount_cents = int(getattr(session, "amount_total", None) or (package.price_cents or 0))
        used_code = (md.get("discount_code") or "").strip() or ""

        Invoice.objects.create(
            employer=employer,
            amount=amount_cents,
            currency="CAD",
            processor="stripe",
            status="paid",
            processor_reference=session_id,
            discount_code=used_code
        )

        pp_kwargs = dict(
            employer=employer,
            package=package,
            credits_granted=int(package.credits),
            credits_remaining=int(package.credits),
            source="stripe",
        )

        try:
            if any(f.name == "duration_days" for f in PurchasedPackage._meta.get_fields()):
                pp_kwargs["duration_days"] = int(package.duration_days)
        except Exception:
            pass

        PurchasedPackage.objects.create(**pp_kwargs)

    _sync_employer_credits(employer)

    send_templated_email(
        "order_confirmation",
        [(employer.email or request.user.email or "").strip()],
        {"email": (employer.email or request.user.email or "").strip(), "package_name": package.name},
    )

    return render(
        request,
        "checkout/checkout_success.html",
        {"sitesettings": _sitesettings(), "package": package},
    )


@login_required
def paypal_success(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        return redirect("package_list")

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    # NOTE: PayPal success remains “soft” (your integration may confirm server-side elsewhere).
    messages.success(request, "Purchase successful. Credits will be applied if configured.")
    return render(
        request,
        "checkout/checkout_success.html",
        {"sitesettings": _sitesettings(), "package": None},
    )


@require_POST
@login_required
def stripe_create_session(request: HttpRequest, package_id: int) -> JsonResponse:
    if not hasattr(request.user, "employer"):
        return JsonResponse({"error": "Employer login required."}, status=403)

    if not _enforce_approval_or_logout(request):
        return JsonResponse({"error": "Approval required."}, status=403)

    employer = request.user.employer
    package = get_object_or_404(PostingPackage, id=package_id, is_active=True)

    gw = _gateway_context()
    secret = (gw.get("stripe_secret_key") or "").strip()
    if not secret or not gw.get("use_stripe"):
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

    if not _enforce_approval_or_logout(request):
        return redirect("login")

    employer = request.user.employer
    invoice = get_object_or_404(Invoice, id=invoice_id, employer=employer)

    return render(
        request,
        "billing/invoice_detail.html",
        {
            "sitesettings": _sitesettings(),
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
    return render(request, "admin/dashboard.html", {"sitesettings": _sitesettings()})
