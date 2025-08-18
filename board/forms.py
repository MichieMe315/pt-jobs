from django import forms
from .models import Company, Job, Application

class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'website', 'description']

class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['company','title','city','province','employment_type','remote_type','description','salary_min','salary_max','is_active']

class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['resume_text', 'cover_letter']
