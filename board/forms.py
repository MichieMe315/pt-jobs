from __future__ import annotations

import re
from typing import Optional

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model

from .models import Employer, JobSeeker, Job, Application, Resume


User = get_user_model()


# ============================================================
# Validation helpers (Contract: no links/emails in certain text)
# ============================================================

_URL_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.IGNORECASE)


def validate_no_links_or_emails(value: str) -> None:
    val = (value or "").strip()
    if not val:
        return
    if _URL_RE.search(val) or _EMAIL_RE.search(val):
        raise forms.ValidationError("Links and email addresses are not allowed in this field.")


# ============================================================
# Styling mixin (uniform formatting)
# ============================================================

class StyledFormMixin:
    """
    Adds bootstrap-ish classes uniformly across all forms:
    - Select widgets -> form-select
    - Everything else -> form-control
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for f in self.fields.values():
            w = f.widget
            css = w.attrs.get("class", "")

            if isinstance(w, (forms.Select, forms.SelectMultiple)):
                add = "form-select"
            else:
                add = "form-control"

            if add not in css.split():
                w.attrs["class"] = (css + " " + add).strip()


# ============================================================
# Login
# ============================================================

class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(label="Email", required=True)

    def clean_username(self):
        # Always treat username as email (your system uses email-as-username)
        return (self.cleaned_data.get("username") or "").strip().lower()


# ============================================================
# Employer signup (Contract: single form, exact fields used by template)
# ============================================================

class EmployerSignUpForm(StyledFormMixin, UserCreationForm):
    email = forms.EmailField(required=True)
    name = forms.CharField(required=False)
    company_name = forms.CharField(required=True)
    company_description = forms.CharField(required=False, widget=forms.Textarea)
    phone = forms.CharField(required=False)
    website = forms.URLField(required=False)
    location = forms.CharField(required=True)
    logo = forms.ImageField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "email",
            "password1",
            "password2",
            "name",
            "company_name",
            "company_description",
            "phone",
            "website",
            "location",
            "logo",
        )

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_company_description(self):
        val = self.cleaned_data.get("company_description") or ""
        validate_no_links_or_emails(val)
        return val

    def save(self, commit=True):
        # Create User
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]  # email-as-username
        if commit:
            user.save()

        # Create Employer (Contract: must start unapproved)
        Employer.objects.create(
            user=user,
            email=user.email,
            name=self.cleaned_data.get("name") or "",
            company_name=self.cleaned_data.get("company_name") or "",
            company_description=self.cleaned_data.get("company_description") or "",
            phone=self.cleaned_data.get("phone") or "",
            website=self.cleaned_data.get("website") or "",
            location=self.cleaned_data.get("location") or "",
            logo=self.cleaned_data.get("logo"),
            is_approved=False,
        )

        return user


# ============================================================
# Job Seeker signup (Contract: single form, exact order driven by template)
# ============================================================

YES_NO_CHOICES = (("yes", "Yes"), ("no", "No"))
OPPORTUNITY_CHOICES = (
    ("full_time", "Full-time"),
    ("part_time", "Part-time"),
    ("contractor", "Contractor"),
    ("casual", "Casual"),
    ("locum", "Locum"),
    ("temporary", "Temporary"),
)


class JobSeekerSignUpForm(StyledFormMixin, UserCreationForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    position_desired = forms.CharField(required=True)

    # IMPORTANT: keep these FIELD NAMES (templates reference them)
    is_registered_canada = forms.ChoiceField(
        choices=[("", "Select…")] + list(YES_NO_CHOICES),
        required=True,
        label="Are you a Registered Professional in Canada?",
    )
    opportunity_type = forms.ChoiceField(
        choices=[("", "Select…")] + list(OPPORTUNITY_CHOICES),
        required=True,
        label="What type of opportunity are you interested in?",
    )
    current_location = forms.CharField(required=True, label="Where are you currently located?")
    open_to_relocate = forms.ChoiceField(
        choices=[("", "Select…")] + list(YES_NO_CHOICES),
        required=True,
        label="Are you open to relocating?",
    )
    relocate_where = forms.CharField(required=False, label="If yes, where?")

    requires_sponsorship = forms.ChoiceField(
        choices=[("", "Select…")] + list(YES_NO_CHOICES),
        required=True,
        label="Do you require sponsorship to work in Canada?",
    )
    seeking_immigration = forms.ChoiceField(
        choices=[("", "Select…")] + list(YES_NO_CHOICES),
        required=True,
        label="Are you seeking immigration to Canada?",
    )

    resume = forms.FileField(required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
            "position_desired",
            "is_registered_canada",
            "opportunity_type",
            "current_location",
            "open_to_relocate",
            "relocate_where",
            "requires_sponsorship",
            "seeking_immigration",
            "resume",
        )

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def save(self, commit=True):
        # Create User
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]  # email-as-username
        if commit:
            user.save()

        def _yes(v: str) -> bool:
            return (v or "").strip().lower() == "yes"

        # Convert Yes/No -> bool
        registered_in_canada_bool = _yes(self.cleaned_data.get("is_registered_canada"))
        open_to_relocate_bool = _yes(self.cleaned_data.get("open_to_relocate"))
        require_sponsorship_bool = _yes(self.cleaned_data.get("requires_sponsorship"))
        seeking_immigration_bool = _yes(self.cleaned_data.get("seeking_immigration"))

        # ✅ CRITICAL FIX: map to REAL model field names (do not invent kwargs)
        jobseeker = JobSeeker.objects.create(
            user=user,
            first_name=self.cleaned_data.get("first_name") or "",
            last_name=self.cleaned_data.get("last_name") or "",
            email=user.email,
            position_desired=self.cleaned_data.get("position_desired") or "",
            registered_in_canada=registered_in_canada_bool,
            opportunity_type=self.cleaned_data.get("opportunity_type") or "",
            current_location=self.cleaned_data.get("current_location") or "",
            open_to_relocate=open_to_relocate_bool,
            require_sponsorship=require_sponsorship_bool,
            seeking_immigration=seeking_immigration_bool,
            relocate_where=self.cleaned_data.get("relocate_where") or "",
            is_approved=False,  # Contract: must start unapproved
        )

        # Resume optional at signup (Contract)
        resume_file = self.cleaned_data.get("resume")
        if resume_file:
            Resume.objects.create(jobseeker=jobseeker, file=resume_file)

        return user


# ============================================================
# Job form + applications + alerts + resume upload
# (Kept as-is from your provided file)
# ============================================================

JOB_TYPE_CHOICES = (
    ("full_time", "Full-time"),
    ("part_time", "Part-time"),
    ("contractor", "Contractor"),
    ("casual", "Casual"),
    ("locum", "Locum"),
    ("temporary", "Temporary"),
)

COMPENSATION_TYPE_CHOICES = (
    ("hourly", "Hourly"),
    ("yearly", "Yearly"),
    ("split", "Split"),
)

APPLY_VIA_CHOICES = (
    ("email", "Email"),
    ("url", "URL"),
)

YES_NO_SELECT = (("yes", "Yes"), ("no", "No"))


class JobForm(StyledFormMixin, forms.ModelForm):
    relocation_assistance = forms.ChoiceField(
        choices=[("", "Select…")] + list(YES_NO_SELECT),
        required=True,
    )

    def __init__(self, *args, max_expiry_date=None, **kwargs):
        self.max_expiry_date = max_expiry_date
        super().__init__(*args, **kwargs)

        self.fields["job_type"].choices = [("", "Select…")] + list(JOB_TYPE_CHOICES)
        self.fields["compensation_type"].choices = [("", "Select…")] + list(COMPENSATION_TYPE_CHOICES)
        self.fields["apply_via"].choices = [("", "Select…")] + list(APPLY_VIA_CHOICES)

        # Optional: clamp max expiry client-side too (server enforces in clean_expiry_date)
        if self.max_expiry_date and "expiry_date" in self.fields:
            self.fields["expiry_date"].widget.attrs["max"] = self.max_expiry_date.isoformat()

    class Meta:
        model = Job
        fields = (
            "title",
            "description",
            "job_type",
            "compensation_type",
            "compensation_min",
            "compensation_max",
            "location",
            "apply_via",
            "apply_email",
            "apply_url",
            "expiry_date",
        )

        widgets = {
            "description": forms.Textarea,
        }

    def clean_description(self):
        val = self.cleaned_data.get("description") or ""
        validate_no_links_or_emails(val)
        return val

    def clean_expiry_date(self):
        expiry = self.cleaned_data.get("expiry_date")
        if self.max_expiry_date and expiry and expiry > self.max_expiry_date:
            raise forms.ValidationError("Expiry date exceeds the maximum allowed posting duration.")
        return expiry

    def save(self, commit=True):
        inst = super().save(commit=False)
        inst.relocation_assistance = (self.cleaned_data.get("relocation_assistance") or "").lower() == "yes"
        if commit:
            inst.save()
        return inst


class JobApplicationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Application
        fields = ("cover_letter",)
        widgets = {"cover_letter": forms.Textarea}


class JobAlertForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(required=True)


class ResumeUploadForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Resume
        fields = ("file",)
