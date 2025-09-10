from django.shortcuts import redirect
from django.urls import resolve
from django.contrib.auth import logout
from django.apps import apps

ALLOWED_NAMES = {
    # auth
    "login", "logout", "password_reset", "password_reset_done",
    "password_reset_confirm", "password_reset_complete",
    # our pages
    "employer_signup", "jobseeker_signup", "account_pending",
    # common public pages you likely have; add more if needed:
    "home", "job_list", "job_detail", "employer_list", "package_list",
}

class ApprovalRequiredMiddleware:
    """
    If a user is authenticated but not approved (via accounts.UserProfile.approved),
    redirect them to 'account_pending' and log them out to avoid session use.
    Staff/superusers are exempt.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ignore static/media and admin automatically by checking resolver safely
        try:
            match = resolve(request.path_info)
            view_name = match.url_name
        except Exception:
            view_name = None

        if request.user.is_authenticated:
            user = request.user
            if not (user.is_staff or user.is_superuser):
                # Fetch profile
                UserProfile = apps.get_model("accounts", "UserProfile")
                profile = UserProfile.objects.filter(user=user).first()
                approved = getattr(profile, "approved", False) if profile else False

                if not approved:
                    # Allow certain safe views without logging them out repeatedly
                    if view_name in ALLOWED_NAMES or (request.path_info or "").startswith("/admin/"):
                        return self.get_response(request)
                    # Otherwise force logout and send to pending page
                    logout(request)
                    return redirect("account_pending")

        return self.get_response(request)
