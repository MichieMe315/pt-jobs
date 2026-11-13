from datetime import date
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password, password_validators_help_text_html
from .models import InternationalProfile

from .countries import COUNTRIES
PROVINCES=['Alberta','British Columbia','Manitoba','New Brunswick','Newfoundland and Labrador','Northwest Territories','Nova Scotia','Nunavut','Ontario','Prince Edward Island','Quebec','Saskatchewan','Yukon']
class InternationalSignupForm(forms.Form):
 email=forms.EmailField(widget=forms.EmailInput(attrs={'autocomplete':'email'}))
 password=forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}),validators=[validate_password],help_text=password_validators_help_text_html())
 country_of_education=forms.CharField(max_length=100,label='Country of physiotherapy education',widget=forms.TextInput(attrs={'placeholder':'Enter education country','autocomplete':'country-name','list':'pt-country-options','data-career-place':'country'}))
 citizenship_country=forms.CharField(max_length=100,label='Country of citizenship / passport issuer',widget=forms.TextInput(attrs={'placeholder':'Enter citizenship country','autocomplete':'country-name','list':'pt-country-options','data-career-place':'country'}))
 residence_country=forms.CharField(max_length=100,label='Country where you currently live',widget=forms.TextInput(attrs={'placeholder':'Enter country of residence','autocomplete':'country-name','list':'pt-country-options','data-career-place':'country'}))
 destination_province=forms.ChoiceField(choices=[('','Choose a destination')]+[(x,x) for x in PROVINCES],required=False)
 canadian_immigration_status=forms.ChoiceField(label='Current Canadian immigration status',choices=[('','Select status'),('none','No Canadian status'),('citizen','Canadian citizen'),('pr','Permanent resident'),('work_permit','Work permit holder'),('study_permit','Study permit holder'),('other','Other / unsure')])
 graduation_year=forms.IntegerField(min_value=1950,max_value=date.today().year+1,label='Year you graduated')
 registered_in_education_country=forms.ChoiceField(label='Professional registration in your education country',choices=[('','Select'),('yes','Yes'),('previous','Previously registered'),('no','No'),('unsure','Not sure')])
 application_history=forms.ChoiceField(required=True,label='CAPR application history',choices=[('','Choose application history'),('new','Not yet applied'),('existing','Applied before 15 October 2026'),('after','Applied on or after 15 October 2026'),('unsure','Already applied / unsure')])
 marketing_consent=forms.BooleanField(required=False,label='Email me physiotherapy registration updates')
 def clean_application_history(self):
  return self.cleaned_data.get('application_history') or 'unsure'
 def clean_country_of_education(self):
  value = " ".join(self.cleaned_data['country_of_education'].split())
  if len(value) < 2 or value.casefold() in ('other', 'unknown', 'n/a'):
   raise forms.ValidationError('Enter the full name of your education country.')
  return value
 def clean_citizenship_country(self):
  value = " ".join(self.cleaned_data['citizenship_country'].split())
  if len(value) < 2 or value.casefold() in ('other', 'unknown', 'n/a'):
   raise forms.ValidationError('Enter your citizenship country, not Other.')
  return value
 def clean_residence_country(self):
  value = " ".join(self.cleaned_data['residence_country'].split())
  if len(value) < 2 or value.casefold() in ('other', 'unknown', 'n/a'):
   raise forms.ValidationError('Enter your current country of residence.')
  return value
 def clean_email(self):
  email=self.cleaned_data['email'].strip().lower()
  if get_user_model().objects.filter(email__iexact=email).exists():raise forms.ValidationError('An account already uses this email. Please sign in.')
  return email
 def save(self):
  d=self.cleaned_data
  user=get_user_model().objects.create_user(username=d['email'],email=d['email'],password=d['password'])
  InternationalProfile.objects.create(user=user,**{k:d[k] for k in ['country_of_education','citizenship_country','residence_country','destination_province','canadian_immigration_status','graduation_year','registered_in_education_country','marketing_consent','application_history']})
  return user


class InternationalProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(label="First name", max_length=150, required=False, widget=forms.TextInput(attrs={"autocomplete":"given-name"}))
    last_name = forms.CharField(label="Last name", max_length=150, required=False, widget=forms.TextInput(attrs={"autocomplete":"family-name"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.user_id:
            self.initial.setdefault("first_name", self.instance.user.first_name)
            self.initial.setdefault("last_name", self.instance.user.last_name)
        self.order_fields(("first_name", "last_name"))

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)
        from django.db import transaction
        with transaction.atomic():
            profile = super().save()
            user = profile.user
            fields = []
            for field in ("first_name", "last_name"):
                if self.add_prefix(field) in self.data:
                    setattr(user, field, self.cleaned_data[field])
                    fields.append(field)
            if fields:
                user.save(update_fields=fields)
        return profile

    application_history = forms.ChoiceField(required=False, choices=[("new","Not yet applied"),("existing","Applied before 15 October 2026"),("after","Applied on or after 15 October 2026"),("unsure","Already applied / unsure")])
    def clean_application_history(self):
        return self.cleaned_data.get("application_history") or self.instance.application_history or "unsure"
    class Meta:
        model = InternationalProfile
        fields = ("country_of_education", "citizenship_country", "residence_country", "destination_province", "canadian_immigration_status", "graduation_year", "registered_in_education_country", "application_history")
        widgets = {
            "country_of_education": forms.TextInput(attrs={"list": "pt-country-options", "autocomplete": "off", "data-career-place": "country"}),
            "citizenship_country": forms.TextInput(attrs={"list": "pt-country-options", "autocomplete": "off", "data-career-place": "country"}),
            "residence_country": forms.TextInput(attrs={"list": "pt-country-options", "autocomplete": "off", "data-career-place": "country"}),
            "destination_province": forms.Select(choices=[("", "Choose a province or territory")]+[(p,p) for p in PROVINCES]),
            "canadian_immigration_status": forms.Select(choices=[("", "Choose your status"),("none","No Canadian status"),("citizen","Canadian citizen"),("pr","Permanent resident"),("work_permit","Work permit holder"),("study_permit","Study permit holder"),("other","Other / unsure")]),
            "registered_in_education_country": forms.Select(choices=[("", "Choose status"),("yes","Yes"),("previous","Previously registered"),("no","No"),("unsure","Not sure")]),
        }
    def clean_citizenship_country(self):
        value = self.cleaned_data["citizenship_country"].strip()
        if not value:
            raise forms.ValidationError("Citizenship country is required.")
        return value

_COUNTRY_CHOICES=[('', 'Choose a country')]+[(n,n) for n in COUNTRIES]
def _country_clean(self, field):
    from .countries import canonical
    try:return canonical(self.cleaned_data[field])
    except ValueError as exc:raise forms.ValidationError(str(exc))
for _cls in (InternationalSignupForm,InternationalProfileUpdateForm):
    for _field in ('country_of_education','citizenship_country','residence_country'):
        _cls.base_fields[_field].widget=forms.Select(choices=_COUNTRY_CHOICES)
        setattr(_cls,'clean_'+_field,lambda self,f=_field:_country_clean(self,f))
InternationalProfileUpdateForm.base_fields['destination_province']=forms.ChoiceField(choices=[('','Not chosen')]+[(p,p) for p in PROVINCES],required=False)
InternationalProfileUpdateForm.base_fields['registered_in_education_country']=forms.ChoiceField(choices=[('','Choose registration status'),('yes','Currently registered'),('previous','Previously registered'),('no','Not registered'),('unsure','Unsure')])
InternationalProfileUpdateForm.base_fields['graduation_year']=forms.IntegerField(min_value=1950,max_value=date.today().year+1,required=False)
