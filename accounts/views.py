from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect
from django.urls import reverse
from django.db import transaction
from django.apps import apps
from django.http import HttpResponseForbidden

from .forms import EmployerSignUpForm, JobSeekerSignUpForm, ApprovedAuthenticationForm

User = get_user_model()

def _get_userprofile_model():
    return apps.get_model("accounts", "UserProfile")  # expects accounts.models.UserProfile

def _get_profile(user):
    UP = _get_userprofile_model()
    return UP.objects.filter(user=user).first()

def employer_signup(request):
    if request.method == "POST":
        form = EmployerSignUpForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.is_active = True  # keep active; approval gate is profile.is_approved
                user.save()

                UP = _get_userprofile_model()
                # assume model has: user (FK), role (str), is_approved (bool)
                UP.objects.create(
                    user=user,
                    role="employer",
                    is_approved=False,
                )

            messages.success(request, "Account created. An admin must approve your profile before you can log in.")
            return redirect("account_pending")
    else:
        form = EmployerSignUpForm()
    return render(request, "accounts/employer_signup.html", {"form": form})

def jobseeker_signup(request):
    if request.method == "POST":
        form = JobSeekerSignUpForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.is_active = True
                user.save()

                UP = _get_userprofile_model()
                UP.objects.create(
                    user=user,
                    role="jobseeker",
                    is_approved=False,
                )

            messages.success(request, "Account created. An admin must approve your profile before you can log in.")
            return redirect("account_pending")
    else:
        form = JobSeekerSignUpForm()
    return render(request, "accounts/jobseeker_signup.html", {"form": form})

def account_pending(request):
    # Uses your existing templates/registration/account_pending.html
    return render(request, "registration/account_pending.html")

class ApprovedLoginView(LoginView):
    """
    Uses ApprovedAuthenticationForm to block unapproved users.
    Redirects approved users to role-specific dashboards after login.
    """
    authentication_form = ApprovedAuthenticationForm
    redirect_authenticated_user = True  # if already logged in, go to success URL

    def get_success_url(self):
        user = self.request.user
        profile = _get_profile(user)
        if profile and getattr(profile, "is_approved", False):
            if getattr(profile, "role", "") == "employer":
                return reverse("employer_dashboard")
            elif getattr(profile, "role", "") == "jobseeker":
                return reverse("jobseeker_dashboard")
        # Fallbacks
        return reverse("home")

@login_required
def employer_dashboard(request):
    profile = _get_profile(request.user)
    if not profile or not profile.is_approved or profile.role != "employer":
        return HttpResponseForbidden("Access denied.")
    # TODO: add counts/credits later
    return render(request, "accounts/employer_dashboard.html")

@login_required
def jobseeker_dashboard(request):
    profile = _get_profile(request.user)
    if not profile or not profile.is_approved or profile.role != "jobseeker":
        return HttpResponseForbidden("Access denied.")
    # TODO: add applications/recommendations later
    return render(request, "accounts/jobseeker_dashboard.html")
