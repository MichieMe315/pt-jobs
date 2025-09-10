from __future__ import annotations

from datetime import datetime, timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q, Sum, F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
    Job,
    PostingPackage,
    Employer,
    JobSeeker,
    JobAlert,
    PurchasedPackage,
)
from .forms import JobForm, EmployerSignUpForm, JobSeekerSignUpForm


# ----------------- Helpers -----------------
def _unique_username_from_email(email: str) -> str:
    base = email.split("@")[0][:30] or "user"
    cand = base
    i = 1
    while User.objects.filter(username=cand).exists():
        cand = f"{base}{i}"
        i += 1
    return cand


def _require_employer(request):
    if not request.user.is_authenticated or not hasattr(request.user, "employer"):
        messages.error(request, "Please log in as an employer.")
        return None
    emp = request.user.employer
    if not emp.is_approved:
        messages.warning(request, "Your employer account is pending approval.")
    return emp


def _require_jobseeker(request):
    if not request.user.is_authenticated or not hasattr(request.user, "jobseeker"):
        messages.error(request, "Please log in as a job seeker.")
        return None
    js = request.user.jobseeker
    if not js.is_approved:
        messages.warning(request, "Your job seeker account is pending approval.")
    return js


# ----------------- Public pages -----------------
def home(request):
    latest_jobs = Job.objects.filter(is_active=True).order_by("-posting_date")[:10]
    featured_jobs = Job.objects.filter(is_active=True, featured=True).order_by("-posting_date")[:5]
    return render(request, "board/homepage.html", {
        "latest_jobs": latest_jobs,
        "featured_jobs": featured_jobs,
    })


def job_list(request):
    qs = Job.objects.filter(is_active=True)
    q = (request.GET.get("q") or "").strip()
    location = (request.GET.get("location") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if location:
        qs = qs.filter(location__icontains=location)
    qs = qs.order_by("-posting_date")
    return render(request, "board/job_list.html", {"jobs": qs, "q": q, "location": location})


def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk, is_active=True)
    return render(request, "board/job_detail.html", {"job": job})


def employer_list(request):
    employers = Employer.objects.filter(is_approved=True).order_by("company_name", "name")
    employers = [e for e in employers if e.jobs.filter(is_active=True).exists()]
    return render(request, "board/employer_list.html", {"employers": employers})


def employer_public_profile(request, pk: int):
    employer = get_object_or_404(Employer, pk=pk, is_approved=True)
    open_jobs = employer.jobs.filter(is_active=True).order_by("-posting_date", "-id")
    return render(
        request,
        "board/employer_public_profile.html",
        {"employer": employer, "open_jobs": open_jobs},
    )


# ----------------- Packages / checkout (stub) -----------------
def package_list(request):
    packages = PostingPackage.objects.filter(is_active=True).order_by("order", "name")
    return render(request, "packages/package_list.html", {"packages": packages})


def checkout_start(request, code):
    pkg = get_object_or_404(PostingPackage, code=code, is_active=True)
    return render(request, "checkout/checkout_start.html", {"package": pkg})


# ----------------- Signups -----------------
def employer_signup(request):
    if request.method == "POST":
        form = EmployerSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            password = form.cleaned_data["password"]
            username = _unique_username_from_email(email)
            user = User.objects.create_user(username=username, email=email, password=password)

            Employer.objects.create(
                user=user,
                email=email,
                name=form.cleaned_data["contact_name"],
                company_name=form.cleaned_data.get("company_name", ""),
                phone=form.cleaned_data.get("contact_phone", ""),
                website=form.cleaned_data.get("website", ""),
                location=form.cleaned_data["location"],
                logo=form.cleaned_data.get("logo"),
                description=form.cleaned_data.get("description", ""),
                is_approved=False,  # admin approval required
            )

            messages.success(request, "Account created. An admin will review and approve your employer profile.")
            return redirect("home")
    else:
        form = EmployerSignUpForm()
    return render(request, "board/employer_signup.html", {"form": form})


def jobseeker_signup(request):
    if request.method == "POST":
        form = JobSeekerSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            password = form.cleaned_data["password"]
            username = _unique_username_from_email(email)
            user = User.objects.create_user(username=username, email=email, password=password)

            JobSeeker.objects.create(
                user=user,
                email=email,
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                current_location=form.cleaned_data["current_location"],
                position_desired=form.cleaned_data.get("position_desired", ""),
                registration_status=form.cleaned_data["registration_status"],
                opportunity_type=form.cleaned_data["opportunity_type"],
                open_to_relocation=form.cleaned_data["open_to_relocation"],
                relocation_where=form.cleaned_data.get("relocation_where", ""),
                need_sponsorship=form.cleaned_data["need_sponsorship"],
                seeking_immigration=form.cleaned_data["seeking_immigration"],
                resume=form.cleaned_data.get("resume"),
                is_approved=False,  # admin approval required
            )

            messages.success(request, "Account created. An admin will review and approve your job seeker profile.")
            return redirect("home")
    else:
        form = JobSeekerSignUpForm()
    return render(request, "board/jobseeker_signup.html", {"form": form})


def job_alert_signup(request):
    if request.method != "POST":
        return redirect("home")
    email = (request.POST.get("email") or "").strip()
    q = (request.POST.get("q") or "").strip()
    location = (request.POST.get("location") or "").strip()
    if not email:
        messages.error(request, "Please enter a valid email.")
        return redirect("home")
    JobAlert.objects.create(email=email, q=q, location=location)
    messages.success(request, "Job alert created. You can unsubscribe from any alert email.")
    return redirect("home")


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")


# ----------------- Post-login redirect -----------------
@login_required
def post_login_redirect(request):
    if hasattr(request.user, "employer"):
        emp = request.user.employer
        if not emp.is_approved:
            messages.warning(request, "Your employer account is pending approval.")
            return redirect("home")
        return redirect("employer_dashboard")

    if hasattr(request.user, "jobseeker"):
        js = request.user.jobseeker
        if not js.is_approved:
            messages.warning(request, "Your job seeker account is pending approval.")
            return redirect("home")
        return redirect("jobseeker_dashboard")

    return redirect("home")


# ----------------- Employer Dashboard & actions -----------------
@login_required
def employer_dashboard(request):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")

    now = timezone.now()
    active_purchases = emp.purchases.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
    credits_total_active = active_purchases.aggregate(t=Sum("credits_total"))["t"] or 0
    credits_used_active = active_purchases.aggregate(u=Sum("credits_used"))["u"] or 0
    credits_active_left = max(int(credits_total_active) - int(credits_used_active), 0)

    jobs_qs = emp.jobs.all()
    context = {
        "employer": emp,
        "credits_active_left": credits_active_left,
        "jobs": jobs_qs.order_by("-posting_date", "-id")[:25],
    }
    return render(request, "employers/dashboard.html", context)


@login_required
def post_job(request):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")

    # ensure an active credit exists
    now = timezone.now()
    purchase = (
        emp.purchases.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gte=now),
            credits_used__lt=F("credits_total"),
        )
        .order_by("purchased_at")
        .first()
    )
    if not purchase:
        messages.error(request, "You don’t have any credits available. Please purchase a posting package.")
        return redirect("employer_dashboard")

    # package duration controls expiry
    duration_days = purchase.package.duration_days

    if request.method == "POST":
        form = JobForm(request.POST, request.FILES)
        if form.is_valid():
            job = form.save(commit=False)
            job.employer = emp

            # Featured is controlled by package (form doesn't expose it)
            job.featured = False

            # Expiry = posting_date + duration_days
            job.expiry_date = job.posting_date + timedelta(days=duration_days)

            job.save()

            # consume one credit on the purchase we used
            purchase.credits_used = (purchase.credits_used or 0) + 1
            purchase.save(update_fields=["credits_used"])

            messages.success(request, "Job posted successfully.")
            return redirect("employer_dashboard")
    else:
        form = JobForm()

    return render(request, "employers/post_job.html", {"form": form, "duration_days": duration_days})


@login_required
def applications_list(request, job_id: int):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")
    job = get_object_or_404(Job, id=job_id, employer=emp)
    # Placeholder until Application model exists again:
    apps = []
    return render(request, "employers/applications_list.html", {"job": job, "applications": apps})


@login_required
def employer_profile_edit(request):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")

    class EmployerEditForm(forms.ModelForm):
        class Meta:
            model = Employer
            fields = [
                "company_name", "name", "email", "phone", "website",
                "location", "logo", "description",
            ]

    if request.method == "POST":
        form = EmployerEditForm(request.POST, request.FILES, instance=emp)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("employer_dashboard")
    else:
        form = EmployerEditForm(instance=emp)

    return render(request, "employers/profile_edit.html", {"form": form})


@login_required
def purchased_products(request):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")
    purchases = emp.purchases.all().order_by("-purchased_at")
    return render(request, "employers/purchased_products.html", {"purchases": purchases})


@login_required
def invoices_list(request):
    emp = _require_employer(request)
    if emp is None:
        return redirect("login")
    invoices = emp.invoices.all().order_by("-created_at")
    return render(request, "employers/invoices_list.html", {"invoices": invoices})


# ----------------- Jobseeker Dashboard (simple) -----------------
@login_required
def jobseeker_dashboard(request):
    js = _require_jobseeker(request)
    if js is None:
        return redirect("login")
    recent_jobs = Job.objects.filter(is_active=True).order_by("-posting_date")[:20]
    return render(request, "jobseekers/dashboard.html", {"jobseeker": js, "recent_jobs": recent_jobs})
