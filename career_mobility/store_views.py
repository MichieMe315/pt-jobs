from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404,HttpResponse,HttpResponseForbidden
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_http_methods,require_POST
from django.views.decorators.cache import never_cache
from .models import DigitalProduct,ProductOrder
from .store_access import workbook_product,credits,consume_workbook,has_access,entitlements
from .store_offers import quote,OfferError
from .store_checkout import start,CheckoutUnavailable

def base_for(request):return 'career_mobility/standalone.html' if hasattr(request.user,'international_pt_profile') else 'career_mobility/base_tool.html'

@login_required(login_url='mobility_international_login')
@require_POST
def checkout(request,pk):
    product=get_object_or_404(DigitalProduct,pk=pk,is_published=True)
    is_card_pack = product.slug.removeprefix('ptjc-') == 'business-card-design-files'
    from .store_eligibility import account_requirement
    items = [product]
    if product.kind == 'bundle':
        items.extend(line.product for line in product.bundle_lines.select_related('product'))
    for item in items:
        error = account_requirement(request.user, item)
        if error:
            return HttpResponseForbidden(error)
    from ptjc_resumes.offers import product_access
    if product.kind=='file' and product_access(request.user,product):
        if is_card_pack:
            return redirect('mobility_product_detail', slug=product.slug)
        return redirect('mobility_resource_library')
    # Use the signed-in account to price the order, never a submitted audience.
    from .pricing import pricing_audience
    from .shop_gallery import resource_link
    audience = pricing_audience(request.user, product)
    product.price_cad = product.price_for(audience)
    retry_url = resource_link(product, audience)
    if product.price_cad <= 0:
        return HttpResponse('Checkout is not available until a price is set.', status=409)
    if product.kind=='file' and not product.download and not (product.is_online_builder or product.has_editable_preview):return HttpResponse('This product is not ready.',status=400)
    try:
        # Check files before taking any payment, including bundle contents.
        from .store_access import snapshot
        for row in snapshot(product):
            item=DigitalProduct.objects.get(pk=row['product_id'])
            if item.kind=='file' and not (item.is_online_builder or item.has_editable_preview) and (not item.download or not item.download.storage.exists(item.download.name)):
                raise ValueError('One of the included files is not ready for download.')
        order,url=start(request,product,request.POST.get('discount_code','')[:50])
    except (OfferError,CheckoutUnavailable,ValueError) as exc:
        return render(request,'career_mobility/payment_result.html',{'result_base':base_for(request),'payment_error':('Checkout is currently unavailable. You have not been charged.' if isinstance(exc,CheckoutUnavailable) else str(exc)),'retry_product':product,'retry_url':retry_url,'checkout_setup_missing':isinstance(exc,CheckoutUnavailable)},status=400 if isinstance(exc,OfferError) else 503)
    if order.paid:return render(request,'career_mobility/payment_result.html',{'result_base':base_for(request),'order':order})
    if not url:return render(request,'career_mobility/payment_result.html',{'result_base':base_for(request),'payment_error':'Checkout could not be started. Please retry; no access has been activated.','retry_product':product,'retry_url':retry_url},status=503)
    return redirect(url)

@never_cache
@require_http_methods(['GET','POST'])
def workbook(request):
    profile = getattr(request.user, 'international_pt_profile', None)
    product = workbook_product()
    if profile is None:
        from urllib.parse import urlencode
        next_url = reverse('mobility_personalized_checklist')
        suffix = '?' + urlencode({'next': next_url})
        return render(request, 'career_mobility/workbook_intro.html', {
            'product': product if product and product.is_published else None,
            'login_url': reverse('mobility_international_login') + suffix,
            'signup_url': reverse('mobility_international_signup') + suffix,
        }, status=403 if request.method == 'POST' else 200)
    from .starter import remaining, authorize
    from .product_activity import record as track
    count=credits(request.user,product)
    starter = remaining(request.user, product)
    price=product.price_for('international') if product and product.is_published else None
    if request.method=='POST':
        from .planning_pdf import render as pdf
        def generate():
            done=set(profile.checklist_items.filter(completed=True).values_list('key',flat=True))
            return pdf(profile,done)
        data=consume_workbook(request.user,product,generate)
        if data is None and starter:
            candidate = generate()
            if authorize(request.user, product, 1, reuse_paid=False):
                data = candidate
        if data is None:return render(request,'career_mobility/workbook_access.html',{'product':product,'credits':0,'price':price,'error':'No download credits remain. Purchase another download or use an offer code.'},status=402)
        track(product, 'exported', request=request)
        from .international_activity import record
        record(request,'checklist_downloaded')
        response=HttpResponse(data,content_type='application/pdf');response['Content-Disposition']='attachment; filename="international-pt-checklist.pdf"';response['Cache-Control']='private, no-store';return response
    return render(request,'career_mobility/workbook_access.html',{'product':product,'credits':count,'starter_remaining':starter,'price':price})

@login_required
def library(request):
    qs=entitlements(request.user).select_related('product').order_by('-created_at')
    products={entry.product_id:entry.product for entry in qs}
    for order in ProductOrder.objects.filter(user=request.user,paid=True).select_related('product'):
        if order.product.kind=='file':products.setdefault(order.product_id,order.product)
    from .print_palettes import variants
    from .shop_gallery import editor_key, editor_link
    audience = 'international' if hasattr(request.user, 'international_pt_profile') else 'canadian'
    rows=[{'product':p, 'appointment_editor':editor_key(p) == 'appointment-card-designs', 'editor_url':editor_link(p, audience) if p.is_published and p.audience in (audience,'both') else '','print_palettes':bool(variants(p.download)),'credits':credits(request.user,p) if p.kind=='workbook' else None} for p in products.values()]
    from .models import ProductDraft
    from .store_eligibility import account_requirement, account_type
    role = account_type(request.user)
    drafts = [{'draft': draft, 'url': editor_link(draft.product, audience) + '&draft=' + str(draft.pk)}
              for draft in ProductDraft.objects.filter(owner=request.user, product__is_published=True).select_related('product').order_by('-updated_at')
              if not account_requirement(request.user, draft.product)]
    return render(request,'career_mobility/resource_library.html',{'resources':rows,'design_drafts':drafts,'digital_account':role,'library_base':base_for(request),'processing_orders':ProductOrder.objects.filter(user=request.user,paid=False,checkout_state='processing').select_related('product')})

@login_required
@require_POST
@transaction.atomic
def claim_starter_bundle(request, pk):
    from .models import StoreGrant
    from .starter import authorize
    from .store_access import activate_grant, snapshot
    from .store_eligibility import account_requirement
    from .product_activity import record

    product = get_object_or_404(DigitalProduct, pk=pk, kind='bundle', is_published=True)
    try:
        rows = snapshot(product)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    for item in DigitalProduct.objects.filter(pk__in=[row['product_id'] for row in rows]):
        if account_requirement(request.user, item):
            return HttpResponseForbidden('This bundle is unavailable for your account.')
    if not authorize(request.user, product, 1, reuse_paid=False):
        return HttpResponseForbidden('No starter claims remain.')
    grant = StoreGrant.objects.create(user=request.user, product=product, reason='Starter bundle claim')
    activate_grant(grant)
    record(product, 'starter_claimed', request=request)
    return redirect('mobility_resource_library')
