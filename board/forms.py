from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import JobSeeker, JOB_TYPE_CHOICES, REGISTRATION_STATUS_CHOICES


# ---------- Shared choice sets ----------
YES_NO_CHOICES = [("", "— Select —"), ("yes", "Yes"), ("no", "No")]
JOB_TYPE_WITH_BLANK = [("", "— Select —")] + JOB_TYPE_CHOICES
REG_STATUS_WITH_BLANK = [("", "— Select —")] + REGISTRATION_STATUS_CHOICES


# ---------- Login form with approval checks for BOTH roles ----------
class LoginForm(AuthenticationForm):
    """
    Disallow login for Employers or Job Seekers whose profile is not yet approved.
    """
    def confirm_login_allowed(self, user):
        emp = getattr(user, "employer", None)
        if emp is not None and not emp.is_approved:
            raise ValidationError(
                "Your employer account is pending admin approval. You’ll be able to log in once approved.",
                code="inactive",
            )
        js = getattr(user, "jobseeker", None)
        if js is not None and not js.is_approved:
            raise ValidationError(
                "Your job seeker account is pending admin approval. You’ll be able to log in once approved.",
                code="inactive",
            )
        # If neither role exists, or role exists and is approved → allow.
        return super().confirm_login_allowed(user)


# ---------- Employer Sign-up ----------
class EmployerSignUpForm(forms.Form):
    contact_name = forms.CharField(label="Contact name", max_length=160)
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)
    company_name = forms.CharField(label="Company name", max_length=160, required=False)
    contact_phone = forms.CharField(label="Phone", max_length=40, required=False)  # no "(optional)" in label
    website = forms.URLField(label="Website", required=False)                      # no "(optional)" in label
    location = forms.CharField(label="Location", max_length=160)
    logo = forms.ImageField(label="Logo", required=False)
    description = forms.CharField(label="About the company", widget=forms.Textarea, required=False)

    def clean_email(self):
        email = (self.cleaned_data["email"] or "").lower().strip()
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email


# ---------- Job Seeker Sign-up ----------
class JobSeekerSignUpForm(forms.ModelForm):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)

    registration_status = forms.ChoiceField(
        label="Are you a Registered professional in Canada?",
        choices=REG_STATUS_WITH_BLANK,
        required=True,
    )
    opportunity_type = forms.ChoiceField(
        label="What type of opportunity are you interested in?",
        choices=JOB_TYPE_WITH_BLANK,
        required=True,
    )
    open_to_relocation = forms.ChoiceField(
        label="Are you open to relocating?",
        choices=YES_NO_CHOICES,
        required=True,
    )
    need_sponsorship = forms.ChoiceField(
        label="Do you require sponsorship to work in Canada?",
        choices=YES_NO_CHOICES,
        required=True,
    )
    seeking_immigration = forms.ChoiceField(
        label="Are you seeking immigration to Canada?",
        choices=YES_NO_CHOICES,
        required=True,
    )

    resume = forms.FileField(label="Resume", required=False)

    class Meta:
        model = JobSeeker
        fields = [
            "first_name",
            "last_name",
            "position_desired",  # placed right after last name
            "email",
            "password",
            "registration_status",
            "opportunity_type",
            "current_location",
            "open_to_relocation",
            "relocation_where",
            "need_sponsorship",
            "seeking_immigration",
            "resume",
        ]
        widgets = {
            "relocation_where": forms.TextInput(attrs={"placeholder": "If yes, where?"}),
            "current_location": forms.TextInput(attrs={"placeholder": "City / Province"}),
            "position_desired": forms.TextInput(attrs={"placeholder": "e.g., Physiotherapist"}),
        }
        labels = {
            "current_location": "Where are you currently located?",
            "relocation_where": "If yes, where?",
        }

    def clean(self):
        data = super().clean()
        for name in [
            "registration_status",
            "opportunity_type",
            "open_to_relocation",
            "need_sponsorship",
            "seeking_immigration",
        ]:
            if data.get(name, "") == "":
                self.add_error(name, "Please select an option.")
        if data.get("open_to_relocation") == "yes" and not (data.get("relocation_where") or "").strip():
            self.add_error("relocation_where", "Please tell us where you’re open to relocating.")
        return data

    @staticmethod
    def to_bool(value: str) -> bool:
        return str(value or "").strip().lower() in ("1", "true", "yes", "y")

    def apply_select_bools(self, js: JobSeeker):
        js.open_to_relocation = self.to_bool(self.cleaned_data.get("open_to_relocation"))
        js.need_sponsorship = self.to_bool(self.cleaned_data.get("need_sponsorship"))
        js.seeking_immigration = self.to_bool(self.cleaned_data.get("seeking_immigration"))
