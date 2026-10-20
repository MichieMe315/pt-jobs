from datetime import date
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from .models import InternationalProfile

COUNTRIES=['Canada','Australia','Bangladesh','Egypt','France','Ghana','Hong Kong','India','Ireland','Nepal','New Zealand','Nigeria','Pakistan','Philippines','South Africa','United Arab Emirates','United Kingdom','United States']
PROVINCES=['Alberta','British Columbia','Manitoba','New Brunswick','Newfoundland and Labrador','Northwest Territories','Nova Scotia','Nunavut','Ontario','Prince Edward Island','Quebec','Saskatchewan','Yukon']
class InternationalSignupForm(forms.Form):
 email=forms.EmailField(widget=forms.EmailInput(attrs={'autocomplete':'email'}))
 password=forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}),validators=[validate_password])
 country_of_education=forms.CharField(max_length=100,label='Country where you completed entry-to-practice PT education',widget=forms.TextInput(attrs={'placeholder':'Enter education country','autocomplete':'country-name','list':'pt-country-options','data-career-place':'country'}))
 citizenship_country=forms.CharField(max_length=100,label='Country of citizenship / passport issuer',widget=forms.TextInput(attrs={'placeholder':'Enter citizenship country','autocomplete':'country-name','list':'pt-country-options','data-career-place':'country'}))
 residence_country=forms.CharField(max_length=100,label='Country where you currently live',widget=forms.TextInput(attrs={'placeholder':'Enter country of residence','autocomplete':'country-name','list':'pt-country-options','data-career-place':'country'}))
 destination_province=forms.ChoiceField(choices=[('','Not sure yet')]+[(x,x) for x in PROVINCES],required=False)
 canadian_immigration_status=forms.ChoiceField(label='Current Canadian immigration status',choices=[('','Select status'),('none','No Canadian status'),('citizen','Canadian citizen'),('pr','Permanent resident'),('work_permit','Work permit holder'),('study_permit','Study permit holder'),('other','Other / unsure')])
 graduation_year=forms.IntegerField(min_value=1950,max_value=date.today().year+1,label='Year you graduated')
 registered_in_education_country=forms.ChoiceField(label='Licensed / eligible to practise without restrictions where educated?',choices=[('','Select'),('yes','Yes'),('no','No'),('unsure','Not sure')])
 marketing_consent=forms.BooleanField(required=False,label='Email me optional PT credentialling updates (not required to register)')
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
  InternationalProfile.objects.create(user=user,**{k:d[k] for k in ['country_of_education','citizenship_country','residence_country','destination_province','canadian_immigration_status','graduation_year','registered_in_education_country','marketing_consent']})
  return user


class InternationalProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = InternationalProfile
        fields = ("country_of_education", "citizenship_country", "residence_country", "destination_province", "canadian_immigration_status", "graduation_year", "registered_in_education_country")
        widgets = {
            "country_of_education": forms.TextInput(attrs={"list": "pt-country-options", "autocomplete": "off", "data-career-place": "country"}),
            "citizenship_country": forms.TextInput(attrs={"list": "pt-country-options", "autocomplete": "off", "data-career-place": "country"}),
            "residence_country": forms.TextInput(attrs={"list": "pt-country-options", "autocomplete": "off", "data-career-place": "country"}),
            "destination_province": forms.Select(choices=[("", "Choose a province or territory")]+[(p,p) for p in PROVINCES]),
            "canadian_immigration_status": forms.Select(choices=[("", "Choose your status"),("none","No Canadian status"),("citizen","Canadian citizen"),("pr","Permanent resident"),("work_permit","Work permit holder"),("study_permit","Study permit holder"),("other","Other / unsure")]),
            "registered_in_education_country": forms.Select(choices=[("", "Choose status"),("yes","Yes"),("no","No"),("unsure","Not sure")]),
        }
    def clean_citizenship_country(self):
        value = self.cleaned_data["citizenship_country"].strip()
        if not value:
            raise forms.ValidationError("Citizenship country is required.")
        return value
