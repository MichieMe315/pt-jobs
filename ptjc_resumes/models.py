import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

class ResumeTemplate(models.Model):
    key = models.SlugField(unique=True, default='international-professional')
    title = models.CharField(max_length=140, default='International physiotherapy resume')
    access_product = models.ForeignKey('career_mobility.DigitalProduct', on_delete=models.PROTECT, null=True, blank=True, help_text='The existing shop product controls price and paid access. The same purchase can include the template pack.')
    default_layout = models.CharField(max_length=30, choices=[(x,x.title()) for x in ('classic','clinical','editorial','sidebar')], default='classic')
    default_palette = models.CharField(max_length=12, choices=[(x,x.title()) for x in ('original','slate','navy','plum','grayscale')], default='original')
    is_enabled = models.BooleanField(default=False)

    def design_defaults(self):
        return {'layout': self.default_layout, 'palette': self.default_palette}

    @classmethod
    def new_draft_data(cls, key):
        template = cls.objects.filter(key=key, is_enabled=True).first()
        return template.design_defaults() if template else {}

    def clean(self):
        if self.key not in ('international-professional', 'canadian-professional'):
            raise ValidationError({'key': 'Choose the international or Canadian builder.'})

    def __str__(self):
        return self.title

class ResumeDraft(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='private_resume_drafts')
    template = models.ForeignKey(ResumeTemplate, on_delete=models.PROTECT)
    title = models.CharField(max_length=120, default='My international resume')
    data = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.title

class ResumeAdPlacement(models.Model):
    title=models.CharField(max_length=100,default='Resume builder ad')
    enabled=models.BooleanField(default=False)
    show_on_international_planner=models.BooleanField(default=False,help_text='Also show this ad on the International planner and country results.')
    mode=models.CharField(max_length=10,choices=[('html','Custom ad HTML'),('adsense','Google AdSense')],default='html')
    html=models.TextField(blank=True,help_text='Trusted administrator code only. No resume data is substituted into this field.')
    adsense_client=models.CharField(max_length=40,blank=True,help_text='ca-pub- followed by your publisher number')
    adsense_slot=models.CharField(max_length=30,blank=True)
    def clean(self):
        import re
        errors={}
        if self.enabled and self.mode=='adsense':
            if not re.fullmatch(r'ca-pub-\d+',self.adsense_client):errors['adsense_client']='Enter a valid AdSense publisher ID.'
            if not re.fullmatch(r'\d+',self.adsense_slot):errors['adsense_slot']='Enter the AdSense slot number.'
        if self.enabled and self.mode=='html' and not self.html.strip():errors['html']='Add ad code or leave this placement disabled.'
        if errors:raise ValidationError(errors)
    def __str__(self):return self.title

class BusinessCardDraft(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name='business_card_drafts')
    title=models.CharField(max_length=120,default='My business card')
    data=models.JSONField(default=dict)
    revision=models.PositiveIntegerField(default=1)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:ordering=['-updated_at']
    def __str__(self):return self.title

class ResumeLayoutOffer(models.Model):
    template = models.ForeignKey(ResumeTemplate, on_delete=models.PROTECT, related_name="layout_offers")
    layout = models.CharField(max_length=30, choices=[(x, x.title()) for x in ("classic", "clinical", "editorial", "sidebar")])
    product = models.OneToOneField("career_mobility.DigitalProduct", on_delete=models.PROTECT, related_name="resume_layout_offer")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("template", "layout"), name="ptjc_resume_template_layout")]
