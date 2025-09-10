from __future__ import annotations

from django import forms
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

from .models import Employer, JobSeeker, Job, REGISTRATION_CHOICES, OPPORTUNITY_CHOICES, COMP_CHOICES, JOB_TYPE_CHOICES


# ---------------- Employer signup ----------------
class EmployerSignUpForm(forms.Form):
    contact_name = forms.CharField(label="Contact name", max_length=120)
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Password", widget=forms.PasswordInput)

    company_name = forms.CharField(label="Company name", max_length=180, required=False)
    contact_phone = forms.CharField(label="Phone", max_length=50, required=False)
    website = forms.URLField(label="Website", required=False)
    location = forms.CharField(label="Location", max_length=180)
    logo = forms.ImageField(label="Logo", required=False)
    description = forms.CharField(label="Description", widget=forms.Textarea, required=False)


# ---------------- Jobseeker signup ----------------
YES_NO = (("yes", "Yes"), ("no", "No"))

class JobSeekerSignUpForm(forms.Form):
    first_name = forms.CharField(max_length=80)
    last_name = forms.CharField(max_length=80)
    position_desired = forms.CharField(max_length=180, required=False)

    email = forms.EmailField()
    current_location = forms.CharField(label="Where are you currently located?", max_length=180)

    registration_status = forms.ChoiceField(
        choices=REGISTRATION_CHOICES,
        label="Are you a Registered professional in Canada?",
    )
    opportunity_type = forms.ChoiceField(
        choices=OPPORTUNITY_CHOICES,
        label="What type of opportunity are you interested in?",
    )
    open_to_relocation = forms.ChoiceField(choices=YES_NO, label="Are you open to relocating?")
    relocation_where = forms.CharField(label="If yes, where?", max_length=180, required=False)
    need_sponsorship = forms.ChoiceField(choices=YES_NO, label="Do you require sponsorship to work in Canada?")
    seeking_immigration = forms.ChoiceField(choices=YES_NO, label="Are you seeking immigration to Canada?")

    resume = forms.FileField(required=False)
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_open_to_relocation(self):
        return self.cleaned_data["open_to_relocation"] == "yes"

    def clean_need_sponsorship(self):
        return self.cleaned_data["need_sponsorship"] == "yes"

    def clean_seeking_immigration(self):
        return self.cleaned_data["seeking_immigration"] == "yes"


# ---------------- Job form (Employer posting) ----------------
class JobForm(forms.ModelForm):
    posting_date = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"})
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
            "relocation_assistance",
            "posting_date",
            # expiry_date is computed from package duration; not in the form
            "application_email",
            "external_apply_url",
            "is_active",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "job_type": forms.Select(choices=JOB_TYPE_CHOICES),
            "compensation_type": forms.Select(choices=COMP_CHOICES),
        }

    def clean(self):
        cleaned = super().clean()
        comp = cleaned.get("compensation_type")
        smin = cleaned.get("salary_min")
        smax = cleaned.get("salary_max")
        if comp and (smin is None or smax is None):
            raise forms.ValidationError("Please provide both salary min and max.")
        if smin is not None and smax is not None and smin > smax:
            raise forms.ValidationError("Salary min cannot be greater than max.")
        return cleaned
