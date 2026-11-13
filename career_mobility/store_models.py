"""Digital shop offers and account entitlements; independent of job-posting credits."""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.functions import Lower

class StoreBundleItem(models.Model):
    bundle = models.ForeignKey('DigitalProduct', on_delete=models.CASCADE, related_name='bundle_lines')
    product = models.ForeignKey('DigitalProduct', on_delete=models.PROTECT, related_name='included_in_bundles')
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(1000)], help_text='Workbook download credits. Other products grant access once.')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['bundle','product'], name='store_bundle_product_once')]
    def clean(self):
        if self.bundle_id == self.product_id:raise ValidationError('A bundle cannot include itself.')
        if self.product_id and self.product.kind == 'bundle':raise ValidationError('Add individual products, not another bundle.')
        if self.bundle_id and self.bundle.kind != 'bundle':raise ValidationError('Set the parent product type to Bundle first.')
    def __str__(self):return f'{self.product} × {self.quantity}'

class StoreDiscount(models.Model):
    name=models.CharField(max_length=120)
    code=models.CharField(max_length=50, blank=True, help_text='Leave blank for an automatic offer. Codes are case-insensitive.')
    products=models.ManyToManyField('DigitalProduct', blank=True, help_text='Leave empty for all digital products and bundles. One offer per order; offers do not stack.')
    kind=models.CharField(max_length=12, choices=[('percent','Percentage off'),('fixed','CAD amount off')], default='percent')
    value=models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    starts_at=models.DateTimeField(null=True,blank=True)
    ends_at=models.DateTimeField(null=True,blank=True)
    max_uses=models.PositiveIntegerField(null=True,blank=True,validators=[MinValueValidator(1)])
    max_uses_per_user=models.PositiveIntegerField(null=True,blank=True,validators=[MinValueValidator(1)])
    is_active=models.BooleanField(default=True)
    class Meta:
        constraints=[models.UniqueConstraint(Lower('code'),condition=~models.Q(code=''),name='store_discount_code_ci')]
    def clean(self):
        self.code=self.code.strip().upper()
        if self.kind=='percent' and self.value is not None and self.value>100:raise ValidationError({'value':'Percentage must be at most 100.'})
        if self.starts_at and self.ends_at and self.ends_at<=self.starts_at:raise ValidationError({'ends_at':'End must be after start.'})
    def save(self,*a,**kw):self.code=self.code.strip().upper();super().save(*a,**kw)
    def __str__(self):return self.name

class StoreGrant(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    product=models.ForeignKey('DigitalProduct',on_delete=models.PROTECT)
    quantity=models.PositiveIntegerField(default=1,validators=[MinValueValidator(1),MaxValueValidator(1000)])
    reason=models.CharField(max_length=240,help_text='For example, a complimentary bundle or promotion.')
    active=models.BooleanField(default=True,help_text='Uncheck to revoke access from this grant.')
    created_at=models.DateTimeField(auto_now_add=True)
    activated_at=models.DateTimeField(null=True,blank=True,editable=False)
    def clean(self):
        if self.product_id:
            from .store_access import snapshot
            try:snapshot(self.product)
            except ValueError as exc:raise ValidationError(str(exc))
            items=[self.product]+[line.product for line in self.product.bundle_lines.select_related('product')] if self.product.kind=='bundle' else [self.product]
            if self.user_id:
                from .store_eligibility import account_requirement
                for product in items:
                    error = account_requirement(self.user, product)
                    if error:
                        raise ValidationError(error)
    def __str__(self):return f'{self.user}: {self.product}'

class StoreEntitlement(models.Model):
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    product=models.ForeignKey('DigitalProduct',on_delete=models.PROTECT)
    order=models.ForeignKey('ProductOrder',null=True,blank=True,on_delete=models.PROTECT,related_name='entitlements')
    grant=models.ForeignKey(StoreGrant,null=True,blank=True,on_delete=models.PROTECT,related_name='entitlements')
    remaining=models.PositiveIntegerField(default=1,help_text='Remaining workbook downloads; other products grant reusable access.')
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['order','product'],name='store_order_entitlement_once'),models.UniqueConstraint(fields=['grant','product'],name='store_grant_entitlement_once'),models.CheckConstraint(condition=(models.Q(order__isnull=False,grant__isnull=True)|models.Q(order__isnull=True,grant__isnull=False)),name='store_entitlement_one_origin')]
    def __str__(self):return f'{self.user}: {self.product}'
