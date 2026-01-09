from __future__ import annotations

from datetime import date
from typing import Any, Optional
import os
import re

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

from .models import (
    Employer,
    JobSeeker,
    Resume,
    Job,
    Application,
    JobAlert,
)

DEFAULT_INPUT_CLASS = "form-control"
DEFAULT_SELECT_CLASS = "form-select"
DEFAULT_TEXTAREA_CLASS = "form-control"
DEFAULT_FILE_CLASS = "form-control"


class StyledFormMixin:
    def _apply_uniform_styling(self) -> None:
        for _, field in self.fields.items():
            widget = field.widget
            existing = widget.attrs.get("class", "")

            if isinstance(widget, forms.Textarea):
                widget.attrs["class"] = f"{existing} {DEFAULT_TEXTAREA_CLASS}".strip()
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs["class"] = f"{existing} {DEFAULT_SELECT_CLASS}".strip()
            elif isinstance(widget, forms.FileInput):
                widget.attrs["class"] = f"{existing} {DEFAULT_FILE_CLASS}".strip()
            else:
                widget.attrs["class"] = f"{existing} {DEFAULT_INPUT_CLASS}".strip()


_URL_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.IGNORECASE)


def validate_no_links_or_emails(value: str) -> None:
    if not value:
        return
    if _URL_RE.search(value) or _EMAIL_RE.search(value):
        raise ValidationError("Please remove links and email addresses from this field.")


class LoginForm(AuthenticationForm, StyledFormMixin):
    def __init__(self, request=None, *args: Any, **kwargs: Any):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].label = "Email"
        self._apply_uniform_styling()


class EmployerSignUpForm(UserCreationForm, StyledFormMixin):
    email = forms.EmailField(required=True, validators=[EmailValidator()])

    name = forms.CharField(required=False)
    company_name = forms.CharField(required=True)

    company_description = forms.CharField(
        required=False,
        widget=forms.Textarea,
        validators=[validate_no_links_or_emails],
    )
    phone = forms.CharField(required=False)
    website = forms.URLField(required=False)
    location = forms.CharField(required=True)
    logo = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ("email", "password1", "password2")

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self._apply_uniform_styling()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.username = email
        user.email = email
        if commit:
            user.save()

        # IMPORTANT: avoid NULLs for optional fields if DB columns are NOT NULL.
        # Use "" instead of None for text/url fields.
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


YES_NO_CHOICES = (("yes", "Yes"), ("no", "No"))

OPPORTUNITY_CHOICES = (
    ("Full-time", "Full-time"),
    ("Part-time", "Part-time"),
    ("Contractor", "Contractor"),
    ("Casual", "Casual"),
    ("Locum", "Locum"),
    ("Temporary", "Temporary"),
)


class JobSeekerSignUpForm(UserCreationForm, StyledFormMixin):
    email = forms.EmailField(required=True, validators=[EmailValidator()])

    position_desired = forms.CharField(required=True)
    is_registered_canada = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)
    opportunity_type = forms.ChoiceField(choices=[("", "Select…")] + list(OPPORTUNITY_CHOICES), required=True)
    current_location = forms.CharField(required=True)
    open_to_relocate = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)
    relocate_where = forms.CharField(required=False)
    requires_sponsorship = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)
    seeking_immigration = forms.ChoiceField(choices=[("", "Select…")] + list(YES_NO_CHOICES), required=True)

    resume = forms.FileField(required=False)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password1", "password2")

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self._apply_uniform_styling()

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("open_to_relocate") == "no":
            cleaned["relocate_where"] = ""
        return cleaned

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        email = self.cleaned_data["email"]
        user.username = email
        user.email = email
        if commit:
            user.save()

        def _to_bool(v: str) -> bool:
            return True if v == "yes" else False

        js = JobSeeker.objects.create(
            user=user,
            email=user.email,
            first_name=self.cleaned_data.get("first_name") or "",
            last_name=self.cleaned_data.get("last_name") or "",
            position_desired=self.cleaned_data.get("position_desired") or "",
            is_registered_canada=_to_bool(self.cleaned_data.get("is_registered_canada", "no")),
            opportunity_type=self.cleaned_data.get("opportunity_type") or "",
            current_location=self.cleaned_data.get("current_location") or "",
            open_to_relocate=_to_bool(self.cleaned_data.get("open_to_relocate", "no")),
            relocate_where=self.cleaned_data.get("relocate_where") or "",
            requires_sponsorship=_to_bool(self.cleaned_data.get("requires_sponsorship", "no")),
            seeking_immigration=_to_bool(self.cleaned_data.get("seeking_immigration", "no")),
            is_approved=False,
        )

        f = self.files.get("resume") if hasattr(self, "files") and self.files else None
        if f:
            f.name = os.path.basename(f.name)
            Resume.objects.create(jobseeker=js, file=f)

        return user


class ResumeUploadForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Resume
        fields = ("file",)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["file"].label = "Upload Resume"
        self._apply_uniform_styling()

    def clean_file(self):
        f = self.cleaned_data.get("file")
        if f:
            f.name = os.path.basename(f.name)
        return f


JOB_TYPE_CHOICES = (
    ("Full-time", "Full-time"),
    ("Part-time", "Part-time"),
    ("Contractor", "Contractor"),
    ("Casual", "Casual"),
    ("Locum", "Locum"),
    ("Temporary", "Temporary"),
)

APPLY_VIA_CHOICES = (
    ("email", "Email"),
    ("url", "URL"),
)

# Values MUST match your template logic + your current model reality:
# Hourly / Salary / Other
# Labels match contract UI: Hourly / Yearly / Split
COMP_TYPE_CHOICES = (
    ("Hourly", "Hourly"),
    ("Salary", "Yearly"),
    ("Other", "Split"),
)


class JobForm(StyledFormMixin, forms.ModelForm):
    relocation_assistance = forms.TypedChoiceField(
        choices=[("", "Select…"), ("yes", "Yes"), ("no", "No")],
        required=True,
        coerce=lambda v: True if str(v).lower() in ("yes", "true", "1") else False,
        empty_value=None,
    )

    def __init__(self, *args: Any, **kwargs: Any):
        self.max_expiry_date: Optional[date] = kwargs.pop("max_expiry_date", None)
        super().__init__(*args, **kwargs)

        self.fields["job_type"].choices = [("", "Select…")] + list(JOB_TYPE_CHOICES)
        self.fields["apply_via"].choices = [("", "Select…")] + list(APPLY_VIA_CHOICES)
        self.fields["compensation_type"].choices = [("", "Select…")] + list(COMP_TYPE_CHOICES)

        for fname in ("job_type", "apply_via", "compensation_type", "relocation_assistance"):
            if fname in self.fields:
                self.fields[fname].required = True
                self.fields[fname].widget.attrs["required"] = "required"

        # Ensure initial shows yes/no for TypedChoiceField
        if self.instance and getattr(self.instance, "pk", None):
            self.initial["relocation_assistance"] = "yes" if bool(getattr(self.instance, "relocation_assistance", False)) else "no"

        self._apply_uniform_styling()

    def clean_description(self):
        desc = self.cleaned_data.get("description") or ""
        validate_no_links_or_emails(desc)
        return desc

    def clean_expiry_date(self):
        d = self.cleaned_data.get("expiry_date")
        if d and self.max_expiry_date and d > self.max_expiry_date:
            raise ValidationError("Expiry date exceeds the maximum allowed for your posting duration.")
        return d

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
            "relocation_assistance",
            "expiry_date",
        )


class JobApplicationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Application
        fields = ("cover_letter",)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.fields["cover_letter"].required = False
        self.fields["cover_letter"].widget = forms.Textarea(attrs={"rows": 6})
        self._apply_uniform_styling()


class JobAlertForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = JobAlert
        fields = ("email",)

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._apply_uniform_styling()
