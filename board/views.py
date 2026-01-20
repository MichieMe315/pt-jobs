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
from django.views.decorators.clickjacking import xframe_options_exempt

from .forms import (
    EmployerSignupForm,
    JobSeekerSignupForm,
    JobForm,
    PackageSelectForm,
    PaymentMethodForm,
)
from .models import (
    Employer,
    Job,
    JobSeeker,
    JobApplication,
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
    """
    Sends email using DEFAULT_FROM_EMAIL (settings) and Django backend.
    MUST NEVER block or crash a request.
    """
    try:
        from django.core.mail import EmailMessage, get_connection

        # HARD timeout so SMTP/network issues can NEVER kill a request
        connection = get_connection(timeout=5)

        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=to_emails,
            connection=connection,
        )

        # Absolutely never allow email failure to bubble up
        msg.send(fail_silently=True)

    except Exception:
        # Email must NEVER break signup / checkout / posting
        return


def _admin_emails() -> list[str]:
    """
    Admin recipient emails:
    1) SiteSettings.contact_email
    2) settings.ADMINS
    3) settings.SITE_ADMIN_EMAIL
    """
    try:
        s = SiteSettings.objects.first()
        if s and getattr(s, "contact_email", None):
            return [s.contact_email]
    except Exception:
        pass

    admins = getattr(settings, "ADMINS", None)
    if admins:
        return [email for _, email in admins]

    site_admin = getattr(settings, "SITE_ADMIN_EMAIL", None)
    if site_admin:
        return [site_admin]

    return []


# ============================================================
# Home
# ============================================================

def home(request: HttpRequest) -> HttpResponse:
    sitesettings = SiteSettings.objects.first()
    featured_jobs = Job.objects.filter(is_active=True).select_related("employer")[:10]

    return render(
        request,
        "board/home.html",
        {
            "sitesettings": sitesettings,
            "featured_jobs": featured_jobs,
        },
    )


# ============================================================
# Authentication
# ============================================================

def employer_signup(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = EmployerSignupForm(request.POST, request.FILES)
        if form.is_valid():
            employer = form.save()

            _send_email(
                subject="New employer signup pending approval",
                body="A new employer has signed up and is awaiting approval.",
                to_emails=_admin_emails(),
            )

            messages.success(
                request,
                "Signup successful. Your account is pending approval.",
            )
            return redirect("login")
    else:
        form = EmployerSignupForm()

    return render(request, "board/employer_signup.html", {"form": form})


def jobseeker_signup(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = JobSeekerSignupForm(request.POST, request.FILES)
        if form.is_valid():
            js = form.save()

            _send_email(
                subject="New job seeker signup pending approval",
                body="A new job seeker has signed up and is awaiting approval.",
                to_emails=_admin_emails(),
            )

            messages.success(
                request,
                "Signup successful. Your account is pending approval.",
            )
            return redirect("login")
    else:
        form = JobSeekerSignupForm()

    return render(request, "board/jobseeker_signup.html", {"form": form})


# ============================================================
# Jobs
# ============================================================

def job_list(request: HttpRequest) -> HttpResponse:
    jobs = (
        Job.objects.filter(is_active=True)
        .select_related("employer")
        .annotate(app_count=Count("applications"))
    )

    return render(request, "board/job_list.html", {"jobs": jobs})


def job_detail(request: HttpRequest, job_id: int) -> HttpResponse:
    job = get_object_or_404(Job, id=job_id, is_active=True)
    return render(request, "board/job_detail.html", {"job": job})


@login_required
def job_apply(request: HttpRequest, job_id: int) -> HttpResponse:
    if not hasattr(request.user, "jobseeker"):
        raise PermissionDenied

    js = request.user.jobseeker
    if not js.is_approved:
        raise PermissionDenied

    job = get_object_or_404(Job, id=job_id, is_active=True)

    if request.method == "POST":
        JobApplication.objects.create(
            job=job,
            jobseeker=js,
            resume=request.FILES.get("resume"),
            cover_letter=request.POST.get("cover_letter", ""),
        )

        _send_email(
            subject="New job application received",
            body=f"A new application has been submitted for: {job.title}",
            to_emails=[job.employer.email],
        )

        messages.success(request, "Application submitted successfully.")
        return redirect("job_detail", job_id=job.id)

    return render(request, "board/job_apply.html", {"job": job})


# ============================================================
# Packages / Payments
# ============================================================

@login_required
def select_package(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "employer"):
        raise PermissionDenied

    employer = request.user.employer
    if not employer.is_approved:
        messages.error(request, "Your account must be approved before purchasing packages.")
        return redirect("employer_dashboard")

    packages = PostingPackage.objects.all()

    return render(
        request,
        "board/package_select.html",
        {
            "packages": packages,
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

    jobs = Job.objects.filter(employer=employer)
    active_credits = PurchasedPackage.objects.filter(
        employer=employer,
        expires_at__gte=forms.DateTimeField().to_python(None),
    ).aggregate(total=Sum("credits_remaining"))["total"] or 0

    return render(
        request,
        "board/employer_dashboard.html",
        {
            "employer": employer,
            "jobs": jobs,
            "active_credits": active_credits,
        },
    )


@login_required
def jobseeker_dashboard(request: HttpRequest) -> HttpResponse:
    if not hasattr(request.user, "jobseeker"):
        raise PermissionDenied

    js = request.user.jobseeker
    applications = JobApplication.objects.filter(jobseeker=js).select_related("job")

    return render(
        request,
        "board/jobseeker_dashboard.html",
        {
            "jobseeker": js,
            "applications": applications,
        },
    )


# ============================================================
# Admin dashboard (embedded)
# ============================================================

@login_required
@xframe_options_exempt
def admin_dashboard(request: HttpRequest) -> HttpResponse:
    if not request.user.is_staff:
        raise PermissionDenied
    return render(request, "admin/dashboard.html")
