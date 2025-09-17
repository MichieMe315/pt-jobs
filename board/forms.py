from __future__ import annotations

from datetime import date
from typing import Optional

from django import forms
from django.core.exceptions import ValidationError

from .models import Employer, JobSeeker, Job, PostingPackage


# -------- helpers --------
YES_NO_CHOICES = (("yes", "Yes"), ("no", "No"))

REGISTRATION_STATUS_CHOICES = (
    ("yes", "Yes"),
    ("no", "No"),
    ("canadian_new_grad", "Canadian New Grad"),
    ("completed_credentialing", "Completed Credentialing"),
    ("completed_pce", "Completed PCE"),
)

OPPORTUNITY_TYPE_CHOICES = (
    ("full_time", "Full-time"),
    ("part_time", "Part-time"),
    ("contractor", "Contractor"),
    ("resident", "Resident"),
    ("intern", "Intern"),
    ("locum", "Locum"),
)

def _coerce_yes_no_to_bool(val) -> bool:
    """Accept 'yes'/'no' strings, True/False, or truthy/falsey."""
    if isinstance(val, bool):
        return val
    s = (str(val or "")).strip().lower()
    if s in ("yes", "y", "true", "1"):
        return True
    if s in ("no", "n", "false", "0"):
        return False
    # If required=True, this will be caught separately; default False here
    return False


# ================= Employer Sign-up =================
class EmployerSignUpForm(forms.Form):
    # Account
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"})
    )

    # Profile
    contact_name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={"class": "form-control"}))
    company_name = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    contact_phone = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    website = forms.URLField(required=False, widget=forms.URLInput(attrs={"class": "form-control"}))
    location = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"class": "form-control"}))
    logo = forms.ImageField(required=False, widget=forms.ClearableFileInput(attrs={"class": "form-control"}))
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 6}),
    )


# ================= Job Seeker Sign-up =================
class JobSeekerSignUpForm(forms.Form):
    # Account
    first_name = forms.CharField(max_length=80, widget=forms.TextInput(attrs={"class": "form-control"}))
    last_name = forms.CharField(max_length=80, widget=forms.TextInput(attrs={"class": "form-control"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control", "autocomplete": "email"}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"})
    )

    # Profile
    position_desired = forms.CharField(  # text field (placed above the forced dropdown in template)
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    opportunity_type = forms.ChoiceField(  # forced dropdown
        choices=(("", "— Select —"),) + OPPORTUNITY_TYPE_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    current_location = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))

    registration_status = forms.ChoiceField(  # forced dropdown
        choices=(("", "— Select —"),) + REGISTRATION_STATUS_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    open_to_relocation = forms.ChoiceField(  # forced dropdown
        choices=(("", "— Select —"),) + YES_NO_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    relocation_where = forms.CharField(max_length=200, required=False, widget=forms.TextInput(attrs={"class": "form-control"}))

    need_sponsorship = forms.ChoiceField(  # forced dropdown
        choices=(("", "— Select —"),) + YES_NO_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    seeking_immigration = forms.ChoiceField(  # forced dropdown
        choices=(("", "— Select —"),) + YES_NO_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    resume = forms.FileField(required=False, widget=forms.ClearableFileInput(attrs={"class": "form-control"}))

    # normalize booleans
    def clean_open_to_relocation(self):
        return _coerce_yes_no_to_bool(self.cleaned_data.get("open_to_relocation"))

    def clean_need_sponsorship(self):
        return _coerce_yes_no_to_bool(self.cleaned_data.get("need_sponsorship"))

    def clean_seeking_immigration(self):
        return _coerce_yes_no_to_bool(self.cleaned_data.get("seeking_immigration"))

    def clean(self):
        cd = super().clean()
        # If they said “yes” to relocation, nudge for a location (optional)
        if cd.get("open_to_relocation") is True and not (cd.get("relocation_where") or "").strip():
            self.add_error("relocation_where", "Please tell us where you’re open to relocate.")
        return cd


# ================= Job Form (Post / Edit) =================
class JobForm(forms.ModelForm):
    # Force dropdown for relocation assistance
    relocation_assistance_provided = forms.ChoiceField(
        choices=(("", "— Select —"),) + YES_NO_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="Is relocation assistance provided?",
    )

    class Meta:
        model = Job
        fields = [
            "title",
            "description",
            "location",
            "job_type",
            "compensation_type",
            "salary_min",
            "salary_max",
            # intentionally OMITTED to simplify: "percent_split", "application_instructions",
            "application_email",
            "external_apply_url",
            "relocation_assistance_provided",
            "expiry_date",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 7, "class": "form-control"}),
            "location": forms.TextInput(attrs={"class": "form-control"}),
            "job_type": forms.Select(attrs={"class": "form-select"}),  # alignment
            "compensation_type": forms.Select(attrs={"class": "form-select"}),
            "salary_min": forms.NumberInput(attrs={"step": "1", "class": "form-control"}),
            "salary_max": forms.NumberInput(attrs={"step": "1", "class": "form-control"}),
            "application_email": forms.EmailInput(attrs={"class": "form-control"}),
            "external_apply_url": forms.URLInput(attrs={"class": "form-control"}),
            "expiry_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        }

    def __init__(self, *args, min_expiry: Optional[date] = None, max_expiry: Optional[date] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._min_expiry = min_expiry
        self._max_expiry = max_expiry

        # No helper text ("Max allowed is...") -> ensure clean UI
        self.fields["expiry_date"].help_text = ""

        # Client-side min/max for date picker
        if self._min_expiry:
            self.fields["expiry_date"].widget.attrs["min"] = self._min_expiry.isoformat()
        if self._max_expiry:
            self.fields["expiry_date"].widget.attrs["max"] = self._max_expiry.isoformat()

    # normalize relocation yes/no to bool for model
    def clean_relocation_assistance_provided(self):
        return _coerce_yes_no_to_bool(self.cleaned_data.get("relocation_assistance_provided"))

    def clean_expiry_date(self):
        dt = self.cleaned_data.get("expiry_date")
        if dt is None:
            return dt
        # Hard stop on bounds
        if self._min_expiry and dt < self._min_expiry:
            raise ValidationError(f"Expiry cannot be before {self._min_expiry.isoformat()}.")
        if self._max_expiry and dt > self._max_expiry:
            raise ValidationError(f"Expiry cannot be after {self._max_expiry.isoformat()}.")
        return dt


# Optional: Admin form for PostingPackage (unchanged fields)
class PostingPackageAdminForm(forms.ModelForm):
    class Meta:
        model = PostingPackage
        fields = [
            "name",
            "code",
            "description",
            "duration_days",
            "max_jobs",
            "price_cents",
            "allows_featured",
            "is_active",
            "order",
        ]
