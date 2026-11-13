import logging,uuid
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .models import ProductOrder
from .store_offers import quote
from .store_access import activate_order, snapshot
from .store_config import stripe_key,webhook_secret

class CheckoutUnavailable(ValueError):pass

def record_started(request,order):
    from .product_activity import record
    record(order.product, 'checkout_started', request=request, order=order)
    if hasattr(request.user,'international_pt_profile'):
        from .international_activity import record
        record(request,'checkout_started',subject=order.product.slug,event_key='checkout:'+order.stripe_session_id)

def start(request,product,code=''):
    import stripe
    from django.urls import reverse
    from .store_offers import OfferError
    from .pricing import pricing_audience
    from .shop_gallery import resource_link
    audience = pricing_audience(request.user, product)
    return_path = resource_link(product, audience) or reverse('mobility_product_detail', args=[product.slug])
    if Decimal(str(product.price_for(audience))) <= 0:
        raise OfferError('Checkout is not available until a price is set.')
    # NO KEY UPDATE serializes repeat submissions without blocking the foreign-key
    # inserts made by a concurrent payment callback for this same account.
    # User lock serializes repeat submissions for the same account. The Stripe
    # idempotency key and order lock cover provider retries and webhook races.
    with transaction.atomic():
        get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
        processing=ProductOrder.objects.filter(user=request.user,product=product,paid=False,checkout_state='processing').first()
        if processing:
            from urllib.parse import urlencode
            return processing,request.build_absolute_uri(reverse('mobility_product_success'))+'?'+urlencode({'session_id':processing.stripe_session_id})
        pending_id=request.session.get('store_pending_order')
        pending=ProductOrder.objects.filter(pk=pending_id,user=request.user,product=product,paid=False,checkout_state='pending',checkout_expires_at__gt=timezone.now()).first() if pending_id else None
        code=code.strip().upper()
        # Two tabs can carry the same old session cookie. Look up the pending
        # order under the account lock rather than relying only on that cookie.
        if pending is None:
            pending=ProductOrder.objects.filter(user=request.user,product=product,paid=False,checkout_state='pending',checkout_expires_at__gt=timezone.now(),checkout_snapshot__0__code=code).order_by('-pk').first()
        if pending and pending.checkout_snapshot and pending.checkout_snapshot[0].get('code','')==code:
            order=pending
        else:
            base,amount,offer=quote(product,request.user,code,lock=True)
            if amount == 0 and not (code and offer and base > 0):
                raise OfferError('A valid discount code is required for a zero-total order.')
            if 0 < amount < 50:raise OfferError('This discount leaves less than CAD $0.50. Please use a different offer or contact PTJC.')
            if amount and (not stripe_key() or not webhook_secret()):raise CheckoutUnavailable('Digital checkout is not configured. Your account and draft are saved; no charge was started.')
            items=snapshot(product)
            items[0]['code']=code
            items[0]['checkout_name']=product.title
            order=ProductOrder.objects.create(user=request.user,product=product,stripe_session_id=('free_' if amount == 0 else 'pending_')+uuid.uuid4().hex,list_amount_cents=base,amount_cents=amount,discount_amount_cents=base-amount,discount=offer,currency='CAD',checkout_snapshot=items,checkout_expires_at=timezone.now()+timedelta(minutes=35))
            if amount == 0:
                record_started(request, order)
                order.paid = True
                order.checkout_state = 'paid'
                order.checkout_expires_at = None
                order.save(update_fields=['paid', 'checkout_state', 'checkout_expires_at'])
                activate_order(order)
                from .international_notifications import confirm_purchase
                transaction.on_commit(lambda: confirm_purchase(order.pk, request.build_absolute_uri('/')))
                return order, None
            request.session['store_pending_order']=order.pk
        if order.amount_cents < 50:
            raise OfferError('This checkout does not meet the CAD $0.50 minimum.')
        if not stripe_key() or not webhook_secret():raise CheckoutUnavailable('Digital checkout is not configured. No charge was started.')
        # Keep the reservation if a network timeout is ambiguous; retry the same
        # order key rather than risking a second charge or discount redemption.
        try:
            session=stripe.checkout.Session.create(api_key=stripe_key(),idempotency_key=f'ptjc-store-{order.pk}',mode='payment',client_reference_id=str(request.user.pk),line_items=[{'price_data':{'currency':'cad','unit_amount':order.amount_cents,'product_data':{'name':order.checkout_snapshot[0].get('checkout_name',product.title)}},'quantity':1}],expires_at=int(order.checkout_expires_at.timestamp()),success_url=request.build_absolute_uri(reverse('mobility_product_success'))+'?session_id={CHECKOUT_SESSION_ID}',cancel_url=request.build_absolute_uri(return_path),metadata={'mobility_product_id':str(product.pk),'mobility_user_id':str(request.user.pk),'mobility_amount_cents':str(order.amount_cents)})
        except stripe.error.StripeError as exc:
            # Never expose provider response bodies or keys to customers.
            logging.getLogger(__name__).warning('Digital checkout provider request failed: %s',type(exc).__name__)
            return order, ''
        order.stripe_session_id=session.id;order.save(update_fields=['stripe_session_id'])
        record_started(request,order)
        return order,session.url
