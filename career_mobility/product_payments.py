"""Fulfill digital orders only after a signed event or server-side Stripe lookup."""
from django.db import transaction
from .models import ProductOrder
class InvalidProductCheckout(ValueError):pass

def value(obj,key,default=None):return obj.get(key,default) if isinstance(obj,dict) else getattr(obj,key,default)

@transaction.atomic
def fulfill(session,*,expected_user=None,site_base=''):
    reference=value(session,'id','')
    if not isinstance(reference,str) or not reference or len(reference)>255:raise InvalidProductCheckout('Missing payment reference')
    order=ProductOrder.objects.select_for_update(of=('self',)).select_related('product','user').get(stripe_session_id=reference)
    if expected_user is not None and order.user_id!=expected_user:raise InvalidProductCheckout('Wrong account')
    metadata=value(session,'metadata',{}) or {}
    if metadata.get('mobility_user_id') and metadata['mobility_user_id']!=str(order.user_id):raise InvalidProductCheckout('Wrong user')
    if metadata.get('mobility_product_id') and metadata['mobility_product_id']!=str(order.product_id):raise InvalidProductCheckout('Wrong resource')
    paid=value(session,'payment_status')
    amount=value(session,'amount_total');currency=str(value(session,'currency','')).upper();expected=order.amount_cents
    if 'mobility_amount_cents' in metadata:
        try:snapshot=int(metadata['mobility_amount_cents'])
        except (ValueError,TypeError):raise InvalidProductCheckout('Invalid amount')
        if snapshot<0 or (expected is not None and snapshot!=expected):raise InvalidProductCheckout('Price snapshot mismatch')
        expected=snapshot
    if expected is not None and (amount!=expected or currency!='CAD'):raise InvalidProductCheckout('Payment mismatch')
    if amount is not None and (type(amount) is not int or amount<0 or currency!='CAD'):raise InvalidProductCheckout('Invalid paid amount')
    if paid not in ('paid','no_payment_required'):
        if paid=='unpaid' and value(session,'status')=='complete' and not order.paid and order.checkout_state not in ('failed','expired'):
            order.checkout_state='processing';order.checkout_expires_at=None
            order.payment_intent=value(session,'payment_intent','') or ''
            order.save(update_fields=['checkout_state','checkout_expires_at','payment_intent'])
        return order
    if paid=='no_payment_required' and amount!=0:raise InvalidProductCheckout('Non-zero free checkout')
    if not order.paid:
        order.paid=True
        order.checkout_state='paid'
        if amount is not None:order.amount_cents=amount;order.currency=currency
        order.payment_intent=value(session,'payment_intent','') or ''
        order.checkout_expires_at=None
        order.save(update_fields=['paid','checkout_state','amount_cents','currency','payment_intent','checkout_expires_at'])
        from .store_access import activate_order
        activate_order(order)
        from .international_notifications import confirm_purchase
        transaction.on_commit(lambda:confirm_purchase(order.pk,site_base))
    return order
