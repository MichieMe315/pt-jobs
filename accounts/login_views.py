from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.apps import apps

class ApprovedAuthenticationForm(AuthenticationForm):
    """Friendlier message for inactive (not yet approved) users."""
    def confirm_login_allowed(self, user):
        try:
            super().confirm_login_allowed(user)
        except ValidationError as e:
            if not user.is_active:
                raise ValidationError(
                    "Your account is pending approval. Please wait for an admin to approve it.",
                    code="inactive",
                )
            raise

def _get_profile(user):
    UserProfile = apps.get_model("accounts", "UserProfile")
    return UserProfile.objects.filter(user=user).first()

class ApprovedLoginView(LoginView):
    """Uses our custom form and routes by role after login."""
    authentication_form = ApprovedAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        profile = _get_profile(user)
        if profile:
            if profile.role == "EMPLOYER":
                return reverse("employer_dashboard")
            if profile.role == "SEEKER":
                return reverse("jobseeker_dashboard")
        return reverse("home")
