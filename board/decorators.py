from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages


def employer_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        profile = getattr(user, "employer_profile", None)
        if not profile:
            messages.error(request, "Employer account required.")
            return redirect("login")
        if not user.is_active or not profile.is_approved:
            messages.error(request, "Your employer account is pending admin approval.")
            return redirect("account_pending")
        return view_func(request, *args, **kwargs)
    return _wrapped


def jobseeker_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        profile = getattr(user, "jobseeker_profile", None)
        if not profile:
            messages.error(request, "Job Seeker account required.")
            return redirect("login")
        if not user.is_active or not profile.is_approved:
            messages.error(request, "Your job seeker account is pending admin approval.")
            return redirect("account_pending")
        return view_func(request, *args, **kwargs)
    return _wrapped
