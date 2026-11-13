from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.urls import reverse, NoReverseMatch
from .store_config import stripe_key,webhook_secret
from .store_access import workbook_product

def status(request):
    if not request.user.has_perm('career_mobility.view_productorder'):raise PermissionDenied
    key=stripe_key();error='';probe=None
    if request.method=='POST' and request.POST.get('probe'):
        if not key:error='No Stripe API key is configured.'
        else:
            try:
                import stripe
                stripe.Account.retrieve(api_key=key)
                probe='Stripe accepted the configured API key. This is a read-only connection check, not a test charge.'
            except Exception as exc:error='Stripe connection check failed ('+type(exc).__name__+'). Check your configured key and account access.'
    product=workbook_product()
    try:endpoint=reverse('mobility_stripe_webhook')
    except NoReverseMatch:
        endpoint=reverse('mobility_home')+'stripe/mobility-webhook/'
        error=error or 'The digital webhook route is unavailable.'
    try:reverse('mobility_product_checkout',args=[0])
    except NoReverseMatch:
        error=error or 'New digital purchases are disabled. The webhook can still receive payments for existing orders.'
    return render(request,'admin/career_mobility/store_status.html',dict(admin.site.each_context(request),title='Digital checkout readiness',local=request.get_host().split(':')[0] in ('localhost','127.0.0.1'),has_key=bool(key),has_webhook=bool(webhook_secret()),mode='Live' if key.startswith('sk_live_') else 'Test' if key.startswith('sk_test_') else 'Configured key' if key else 'Not configured',endpoint=request.build_absolute_uri(endpoint),workbook=product,probe=probe,error=error))
