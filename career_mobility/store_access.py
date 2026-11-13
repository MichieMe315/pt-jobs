from django.db import transaction
from django.db.models import Q, F, Sum
from django.utils import timezone
from .models import DigitalProduct, ProductOrder, StoreEntitlement, StoreGrant

WORKBOOK_SLUG='international-planning-workbook'
def entitlements(user,product=None):
    qs=StoreEntitlement.objects.filter(user=user).filter(Q(order__paid=True)|Q(grant__active=True))
    return qs.filter(product=product) if product is not None else qs

def has_access(user,product):
    if not getattr(user,'is_authenticated',False):return False
    return entitlements(user,product).exists() or (product.kind=='file' and ProductOrder.objects.filter(user=user,product=product,paid=True).exists())

def workbook_product():return DigitalProduct.objects.get(slug=WORKBOOK_SLUG,kind='workbook')
def credits(user,product):return entitlements(user,product).aggregate(n=Sum('remaining'))['n'] or 0

def snapshot(product):
    rows=[{'product_id':product.pk,'kind':product.kind,'quantity':1}]
    if product.kind=='bundle':
        lines=list(product.bundle_lines.select_related('product'))
        if not lines:raise ValueError('This bundle has no products yet.')
        for line in lines:
            if line.product.kind=='bundle' or line.product_id==product.pk:raise ValueError('Nested bundles are not supported.')
            rows.append({'product_id':line.product_id,'kind':line.product.kind,'quantity':line.quantity})
    return rows

@transaction.atomic
def activate_order(order):
    from .product_activity import record
    record(order.product, 'code_redeemed' if order.amount_cents == 0 else 'purchased', order=order)
    # Caller locks the order. A unique constraint also prevents duplicate grants.
    for row in order.checkout_snapshot or snapshot(order.product):
        StoreEntitlement.objects.get_or_create(user=order.user,product_id=row['product_id'],order=order,defaults={'remaining':row['quantity']})

@transaction.atomic
def activate_grant(grant):
    grant=StoreGrant.objects.select_for_update().get(pk=grant.pk)
    if grant.activated_at:return
    for row in snapshot(grant.product):
        StoreEntitlement.objects.get_or_create(user=grant.user,product_id=row['product_id'],grant=grant,defaults={'remaining':row['quantity']*grant.quantity})
    grant.activated_at=timezone.now();grant.save(update_fields=['activated_at'])

@transaction.atomic
def consume_workbook(user,product,render):
    # Generate first; a PDF failure must not consume the customer's credit.
    qs=entitlements(user,product).filter(remaining__gt=0).select_for_update(of=('self',)).order_by('pk')
    entry=qs.first()
    if entry is None:return None
    content=render()
    if not StoreEntitlement.objects.filter(pk=entry.pk,remaining__gt=0).update(remaining=F('remaining')-1):return None
    return content

def owned_ids(user):
    if not getattr(user,'is_authenticated',False):return set()
    return set(entitlements(user).values_list('product_id',flat=True)) | set(ProductOrder.objects.filter(user=user,paid=True,product__kind='file').values_list('product_id',flat=True))
