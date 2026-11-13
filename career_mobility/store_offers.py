from decimal import Decimal, ROUND_HALF_UP, localcontext
from django.db.models import Q
from django.utils import timezone
from .models import StoreDiscount, ProductOrder

class OfferError(ValueError):pass

def eligible(offer,product,user,now=None):
    now=now or timezone.now()
    if not offer.is_active or (offer.starts_at and offer.starts_at>now) or (offer.ends_at and offer.ends_at<=now):return False
    if offer.products.exists() and not offer.products.filter(pk=product.pk).exists():return False
    used=ProductOrder.objects.filter(discount=offer).filter(Q(paid=True)|Q(paid=False,checkout_state='processing')|Q(paid=False,checkout_state='pending',checkout_expires_at__gt=now))
    if offer.max_uses is not None and used.count()>=offer.max_uses:return False
    if offer.max_uses_per_user is not None and used.filter(user=user).count()>=offer.max_uses_per_user:return False
    return True

def discounted_cents(offer,amount):
    with localcontext() as ctx:
        ctx.prec=28
        if offer.kind=='percent':reduction=int((Decimal(amount)*Decimal(str(offer.value))/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        else:reduction=int((Decimal(str(offer.value))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    return max(0,amount-reduction)

def quote(product,user,code='',lock=False):
    with localcontext() as ctx:
        ctx.prec=28
        amount=int(Decimal(str(product.price_cad))*100)
    candidates=StoreDiscount.objects.order_by('pk')
    if lock:candidates=candidates.select_for_update()
    if code:
        offer=candidates.filter(code__iexact=code.strip()).first()
        if not offer or not eligible(offer,product,user):raise OfferError('This discount code is not available for this product or account.')
        return amount,discounted_cents(offer,amount),offer
    best=(amount,None)
    for offer in candidates.filter(code=''):
        if eligible(offer,product,user):
            final=discounted_cents(offer,amount)
            if final<best[0]:best=(final,offer)
    return amount,best[0],best[1]
