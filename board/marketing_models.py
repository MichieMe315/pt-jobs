from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

class EmployerMarketingProfile(models.Model):
    SETTLEMENT=[('unknown','Not classified'),('rural','Rural'),('remote','Remote'),('small_city','Small city / regional centre'),('urban','Urban')]
    TYPES=[('unknown','Not classified'),('clinic','Clinic'),('hospital','Hospital'),('health_authority','Health authority'),('other','Other')]
    CONTACT=[('unreviewed','Not reviewed'),('ready','Approved for outreach'),('do_not_email','Do not email'),('unsubscribed','Unsubscribed'),('bounced','Bounced')]
    employer=models.OneToOneField('board.Employer',on_delete=models.CASCADE,related_name='marketing_profile')
    city=models.CharField(max_length=100,blank=True,help_text='Optional correction for marketing organization; does not change the public employer profile.')
    province=models.CharField(max_length=2,blank=True,choices=[('AB','Alberta'),('BC','British Columbia'),('MB','Manitoba'),('NB','New Brunswick'),('NL','Newfoundland and Labrador'),('NS','Nova Scotia'),('NT','Northwest Territories'),('NU','Nunavut'),('ON','Ontario'),('PE','Prince Edward Island'),('QC','Quebec'),('SK','Saskatchewan'),('YT','Yukon')])
    settlement=models.CharField(max_length=16,choices=SETTLEMENT,default='unknown',verbose_name='Community category')
    organization_type=models.CharField(max_length=20,choices=TYPES,default='unknown')
    contact_status=models.CharField(max_length=16,choices=CONTACT,default='unreviewed')
    outreach_basis=models.TextField(blank=True,help_text='Record the consent, relationship or other basis for including this contact in outreach.')
    tags=models.CharField(max_length=250,blank=True,help_text='Comma-separated labels, for example relocation launch, northern clinics.')
    notes=models.TextField(blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name='Employer marketing contact'
        verbose_name_plural='Employer marketing contacts'
    def clean(self):
        if self.contact_status=='ready' and not self.outreach_basis.strip():raise ValidationError({'outreach_basis':'Record the outreach basis before approving this contact.'})
    def __str__(self):return str(self.employer)

class MarketingSuppression(models.Model):
    email=models.EmailField(unique=True)
    reason=models.CharField(max_length=16,choices=[('do_not_email','Do not email'),('unsubscribed','Unsubscribed'),('bounced','Bounced')])
    notes=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    def clean(self):self.email=self.email.strip().lower()
    def save(self,*args,**kwargs):self.email=self.email.strip().lower();super().save(*args,**kwargs)
    def __str__(self):return self.email

class MarketingAudience(models.Model):
    name=models.CharField(max_length=150)
    description=models.TextField(blank=True)
    employers=models.ManyToManyField('board.Employer',blank=True,related_name='marketing_audiences')
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self):return self.name

class MarketingDraft(models.Model):
    name=models.CharField(max_length=150)
    audience=models.ForeignKey(MarketingAudience,on_delete=models.PROTECT,related_name='drafts')
    subject=models.CharField(max_length=200)
    body=models.TextField(help_text='Email copy for review. Saving a draft does not send email.')
    status=models.CharField(max_length=16,choices=[('draft','Draft'),('reviewed','Reviewed'),('exported','Exported'),('archived','Archived')],default='draft')
    notes=models.TextField(blank=True)
    updated_at=models.DateTimeField(auto_now=True)
    def __str__(self):return self.name
