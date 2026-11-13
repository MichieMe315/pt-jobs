"""Meter starter exports without granting permanent paid access."""
from django.contrib.auth import get_user_model
from django.db import transaction

from .models import StarterUsage
from .store_access import has_access
from .store_eligibility import account_requirement, account_type


def remaining(user, product):
    if (not product or not product.is_published or not account_type(user)
        or not product.starter_since or user.date_joined < product.starter_since
        or account_requirement(user, product)):
        return 0
    used = StarterUsage.objects.filter(user=user, product=product).values_list('used', flat=True).first() or 0
    return max(0, product.starter_quantity - used)


@transaction.atomic
def authorize(user, product, quantity, *, reuse_paid=True):
    if not product or not user.is_authenticated or type(quantity) is not int or quantity < 1:
        return False
    if reuse_paid and has_access(user, product):
        return True
    get_user_model().objects.select_for_update().get(pk=user.pk)
    if remaining(user, product) < quantity:
        return False
    usage, _ = StarterUsage.objects.get_or_create(user=user, product=product)
    usage.used += quantity
    usage.save(update_fields=['used'])

    return True

def unit(product):
    from .shop_gallery import editor_key
    if product.kind == 'bundle':
        return 'Bundle claims'
    if product.kind == 'workbook':
        return 'Workbook downloads'
    if editor_key(product) == 'appointment-card-designs':
        return 'Cards on the print sheet'
    if product.is_online_builder:
        return 'PDF exports'
    return 'Downloads or exports'
