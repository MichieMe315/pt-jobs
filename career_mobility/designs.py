"""Private drafts and product usage for editable stationery."""
import json
import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import DigitalProduct, ProductDraft
from .shop_gallery import editor_key, editor_link
from .store_access import has_access
from .store_eligibility import account_requirement, account_type
from .product_activity import record


@never_cache
@login_required
@require_POST
def save(request, pk):
    from ptjc_resumes.cards import artwork

    product = get_object_or_404(DigitalProduct, pk=pk, is_published=True)
    if account_requirement(request.user, product):
        return JsonResponse({'error': 'This product is unavailable for your account.'}, status=403)
    if editor_key(product) != 'appointment-card-designs' or len(request.body) > 600000:
        return JsonResponse({'error': 'This design cannot be saved.'}, status=400)
    try:
        payload = json.loads(request.body)
        raw = payload['data']
        data = {}
        for side in ('front', 'back'):
            source = raw[side]
            cleaned = {key: source[key] for key in ('heading', 'name', 'note', 'date', 'time', 'with')}
            if any(not isinstance(v, str) or len(v) > 92 for v in cleaned.values()):
                raise ValueError
            for key in ('paper', 'ink'):
                if not re.fullmatch(r'#[0-9a-fA-F]{6}', source[key]):
                    raise ValueError
                cleaned[key] = source[key]
            cleaned['image'] = artwork(source['image'])
            cleaned['placement'] = source['placement']
            cleaned['scale'] = source['scale']
            if cleaned['placement'] not in ('left', 'center', 'right', 'top') or type(cleaned['scale']) is not int or not 20 <= cleaned['scale'] <= 45:
                raise ValueError
            data[side] = cleaned
        data['design'] = raw['design']
        if data['design'] not in ('clinical', 'community', 'editorial'):
            raise ValueError
    except (KeyError, TypeError, ValueError, ValidationError):
        return JsonResponse({'error': 'Check the design fields and logo size.'}, status=400)
    draft_id = payload.get('draft')
    if draft_id and (type(draft_id) is not int or draft_id <= 0):
        return JsonResponse({'error': 'Invalid draft.'}, status=400)
    if draft_id:
        draft = get_object_or_404(ProductDraft, pk=draft_id, owner=request.user, product=product)
        draft.data = data
        draft.save(update_fields=['data', 'updated_at'])
    else:
        with transaction.atomic():
            from django.contrib.auth import get_user_model
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if ProductDraft.objects.filter(owner=request.user, product=product).count() >= 30:
                return JsonResponse({'error': 'You have reached the saved design limit for this product.'}, status=409)
            draft = ProductDraft.objects.create(owner=request.user, product=product, data=data)
    record(product, 'saved', request=request)
    audience = 'international' if account_type(request.user) == 'international' else 'canadian'
    from .starter import remaining
    return JsonResponse({'id': draft.pk, 'canPrint': has_access(request.user, product), 'remaining': remaining(request.user, product),
                         'url': editor_link(product, audience) + '&draft=' + str(draft.pk)})


@require_POST
def activity(request, pk):
    product = get_object_or_404(DigitalProduct, pk=pk, is_published=True)
    event = request.POST.get('event')
    if event in ('editor_print', 'editor_csv'):
        from .starter import authorize, remaining
        key = editor_key(product)
        if not key or key == 'appointment-card-designs' or account_requirement(request.user, product) or not authorize(request.user, product, 1):
            return JsonResponse({'error': 'No starter exports remain. Purchase access to continue.'}, status=403)
        record(product, 'print_requested' if event == 'editor_print' else 'exported', request=request)
        return JsonResponse({'remaining': remaining(request.user, product)})
    if event not in ('edited', 'print_requested'):
        return JsonResponse({}, status=400)
    draft = request.POST.get('draft', '')
    if event == 'print_requested':
        from .starter import authorize, remaining
        copies = request.POST.get('copies', '1')
        if (account_requirement(request.user, product)
            or not request.user.is_authenticated or copies not in tuple(str(n) for n in range(1, 9))
            or not (draft.isascii() and draft.isdecimal() and len(draft) <= 18)
            or not ProductDraft.objects.filter(pk=draft, owner=request.user, product=product).exists()
            or not authorize(request.user, product, int(copies))):
            return JsonResponse({'error': 'Save the design and purchase access or select a sheet within your remaining allowance.'}, status=403)
        record(product, event, request=request)
        return JsonResponse({'remaining': remaining(request.user, product)})
    if event == 'edited':
        seen = request.session.get('ptjc_design_edits', [])
        if product.pk in seen:
            return JsonResponse({})
        request.session['ptjc_design_edits'] = [*seen[-99:], product.pk]
    record(product, event, request=request)
    return JsonResponse({})
