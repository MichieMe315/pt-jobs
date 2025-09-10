from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from django.apps import apps

User = get_user_model()

def get_profile(user):
    UserProfile = apps.get_model("accounts", "UserProfile")
    return UserProfile.objects.filter(user=user).first()

class ApprovedAuthenticationForm(AuthenticationForm):
    """
    Extends Django's AuthenticationForm to enforce is_approved=True before allowing login.
    Shows a friendly error if pending.
    """
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)  # keep default active/is_staff checks
        profile = get_profile(user)
        if not profile or not getattr(profile, "is_approved", False):
            raise ValidationError(
                "Your account is pending approval. Please wait for an admin to approve it.",
                code="inactive",
            )

class BaseSignupForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

class EmployerSignUpForm(BaseSignupForm):
    pass

class JobSeekerSignUpForm(BaseSignupForm):
    pass
