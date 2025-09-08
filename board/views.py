from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from .models import Job, PostingPackage, Employer, JobSeeker, JobAlert
from .forms import EmployerSignUpForm, JobSeekerSignUpForm


def _unique_username_from_email(email: str) -> str:
    base = email.split("@")[0][:30] or "user"
    cand = base
    i = 1
    while User.objects.filter(username=cand).exists():
        cand = f"{base}{i}"
        i += 1
    return cand


def home(request):
    latest_jobs = Job.objects.filter(is_active=True).order_by("-posting_date")[:10]
    featured_jobs = Job.objects.filter(is_active=True, featured=True).order_by("-posting_date")[:5]

    user = request.user
    can_apply = bool(
        getattr(user, "is_authenticated", False)
        and hasattr(user, "jobseeker")
        and getattr(user.jobseeker, "is_approved", False)
    )
    return render(request, "board/homepage.html", {
        "latest_jobs": latest_jobs,
        "featured_jobs": featured_jobs,
        "can_apply": can_apply,
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

    user = request.user
    can_apply = bool(
        getattr(user, "is_authenticated", False)
        and hasattr(user, "jobseeker")
        and getattr(user.jobseeker, "is_approved", False)
    )
    return render(request, "board/job_list.html", {
        "jobs": qs,
        "q": q,
        "location": location,
        "can_apply": can_apply,
    })


def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk, is_active=True)

    user = request.user
    is_auth = getattr(user, "is_authenticated", False)
    has_js = bool(is_auth and hasattr(user, "jobseeker"))
    js_approved = bool(has_js and getattr(user.jobseeker, "is_approved", False))
    can_apply = bool(is_auth and has_js and js_approved)

    return render(request, "board/job_detail.html", {
        "job": job,
        "can_apply": can_apply,
        "is_auth": is_auth,
        "has_js": has_js,
        "js_approved": js_approved,
    })


def package_list(request):
    packages = PostingPackage.objects.filter(is_active=True).order_by("order", "name")
    return render(request, "packages/package_list.html", {"packages": packages})


def checkout_start(request, code):
    pkg = get_object_or_404(PostingPackage, code=code, is_active=True)
    return render(request, "checkout/checkout_start.html", {"package": pkg})


def employer_list(request):
    employers = Employer.objects.filter(is_approved=True).order_by("company_name", "name")
    employers = [e for e in employers if e.jobs.filter(is_active=True).exists()]
    return render(request, "board/employer_list.html", {"employers": employers})


# ----------------- Signups -----------------
def employer_signup(request):
    """
    Employers require admin approval and are NOT auto-logged in.
    """
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
                is_approved=False,  # require admin approval
            )

            messages.success(request, "Employer account created. An admin will review your profile. You can log in after approval.")
            return redirect("login")
    else:
        form = EmployerSignUpForm()
    return render(request, "board/employer_signup.html", {"form": form})


def jobseeker_signup(request):
    """
    Job seekers require admin approval and are NOT auto-logged in.
    """
    if request.method == "POST":
        form = JobSeekerSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            email = form.cleaned_data["email"].lower().strip()
            password = form.cleaned_data["password"]
            username = _unique_username_from_email(email)
            user = User.objects.create_user(username=username, email=email, password=password)

            js: JobSeeker = form.save(commit=False)
            js.user = user
            js.email = email
            js.is_approved = False  # require admin approval
            form.apply_select_bools(js)
            js.save()
            if form.cleaned_data.get("resume"):
                js.resume = form.cleaned_data["resume"]
                js.save(update_fields=["resume"])

            messages.success(request, "Job seeker account created. An admin will review your profile. You can log in after approval.")
            return redirect("login")
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


# ----------------- Post-login routing & dashboards -----------------
@login_required
def post_login_redirect(request):
    user = request.user
    if hasattr(user, "employer"):
        return redirect("employer_dashboard")
    if hasattr(user, "jobseeker"):
        return redirect("jobseeker_dashboard")
    return redirect("home")


@login_required
def employer_dashboard(request):
    emp = getattr(request.user, "employer", None)
    if not emp:
        messages.error(request, "Employer account not found.")
        return redirect("home")
    return render(request, "employers/dashboard.html", {"employer": emp})


@login_required
def jobseeker_dashboard(request):
    js = getattr(request.user, "jobseeker", None)
    if not js:
        messages.error(request, "Job seeker profile not found.")
        return redirect("home")
    return render(request, "jobseekers/dashboard.html", {"jobseeker": js})
