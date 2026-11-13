"""Public examples only; never read saved drafts or private product files."""
import json
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET, require_POST
from .editable_products import JOURNALS, CALENDAR
from ptjc_resumes.cards import MAX_CARD_BODY, DESIGNS, normalize, svg
from ptjc_resumes.designs import preview as resume_preview

PRODUCTS = (
    ('exercise-tracker', 'My Physio Exercise Tracker', 'Track four prescribed exercises across a week. Includes daily checkboxes and space to record how you felt.'),
    ('appointment-notes', 'Questions for My Physiotherapist', 'Two pages for choosing questions, recording the plan and preparing for follow-up.'),
    ('practice-planner-2027', '2027 Physio Practice Planner', 'A linked year index, 12 monthly calendars and reusable sheets for priorities, hours and professional learning.'),
)
CARD_NAMES = {'clinical': 'Clinical', 'community': 'Community', 'editorial': 'Editorial', 'networking': 'International Networking'}


@require_GET
def gallery(request):
    return render(request, 'career_mobility/public_previews.html', {
        'products': PRODUCTS, 'journals': JOURNALS.items(), 'editable_calendar': CALENDAR, 'designs': CARD_NAMES.items(),
        'resumes': (('clinical','pelvic','Pelvic health'), ('classic','sports','Sports rehabilitation'), ('editorial','paediatric','Paediatrics'), ('sidebar','','Sidebar')),
    })


def sample_card(design):
    return normalize({
        'design': design, 'name': 'Morgan Ellis', 'role': 'Physiotherapy graduate' if design == 'networking' else 'Physiotherapist',
        'organization': 'Harbour Rehab · Example', 'initials': 'ME', 'phone': '613 555 0142',
        'email': 'morgan@example.com', 'website': 'example.com', 'booking': 'example.com/book',
        'address': '48 Example Avenue', 'city': 'Ottawa, ON', 'education_country': 'United Kingdom',
        'status': 'Example: not registered in Canada', 'background': 'Outpatient rehabilitation',
        'profile': 'example.com/profile',
    })



def card_svg(data, side):
    if side not in ('front', 'back'):
        raise Http404('Card side not found')
    response = HttpResponse(svg(data, side, watermark=True), content_type='image/svg+xml')
    response['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox"
    response['X-Content-Type-Options'] = 'nosniff'
    return response

@require_GET
def card_preview(request, design, side):
    if design not in DESIGNS:
        raise Http404('Card design not found')
    return card_svg(sample_card(design), side)


@never_cache
@require_GET
def try_cards(request):
    international = request.GET.get('audience') == 'international' and bool(_international_card_login(''))
    from .models import DigitalProduct
    from .product_activity import record
    product = DigitalProduct.objects.filter(slug='international-business-card-builder-access', is_published=True).first()
    if product:
        record(product, 'opened', request=request)
    design = request.GET.get('design', 'networking' if international else 'clinical')
    return render(request, 'ptjc_resumes/international_card_guest.html' if international else 'ptjc_resumes/card_editor.html', {
        'public_demo': True,
        'bootstrap': {'demo': True, 'data': sample_card(design if design in DESIGNS else 'clinical'),
                      'preview_url': reverse('mobility_try_card_svg'), 'keep_url': reverse('mobility_keep_card') + ('?audience=international' if international else '')},
    })


@never_cache
@require_POST
def try_card_svg(request):
    if len(request.body) > MAX_CARD_BODY:
        return JsonResponse({'error': 'Card details are too long.'}, status=400)
    try:
        payload = json.loads(request.body)
        card = normalize(payload.get('data') if isinstance(payload, dict) else None)
    except (ValueError, ValidationError):
        return JsonResponse({'error': 'Enter valid card details.'}, status=400)
    return card_svg(card, request.GET.get('side'))

@never_cache
@require_POST
def keep_card(request):
    if len(request.body) > MAX_CARD_BODY:
        return JsonResponse({'error':'Card details are too large.'}, status=413)
    try:
        request.session['pending_business_card'] = normalize(json.loads(request.body)['data'])
    except (KeyError, TypeError, ValueError, ValidationError):
        return JsonResponse({'error':'Check the card details.'}, status=400)
    portal = 'international' if request.GET.get('audience') == 'international' and _international_card_login('') else 'canadian'
    request.session['pending_business_card_audience'] = portal
    if _card_account(request.user):
        if not _card_eligible(request.user):
            return JsonResponse({'error': 'This product is unavailable for your account type.'}, status=403)
        url = _save_pending_card(request)
        if url is None:
            return JsonResponse({'error': 'Delete an unused card draft before saving another.'}, status=400)
        return JsonResponse({'url': url})
    return JsonResponse({'url': ''})


def _card_account(user):
    if not user.is_active:
        return None
    profile = getattr(user, 'international_pt_profile', None)
    if profile and profile.email_is_verified:
        return 'ptjc_resumes:card_edit'
    profile = getattr(user, 'jobseeker', None)
    if profile and profile.is_approved and profile.login_active:
        return 'jobseeker_cards:card_edit'
    if getattr(user, 'employer', None):
        return 'jobseeker_cards:card_edit'
    return None


def _card_eligible(user):
    from .models import DigitalProduct
    from .store_eligibility import account_requirement
    product = DigitalProduct.objects.filter(slug='international-business-card-builder-access').first()
    return not (product and product.eligible_accounts and account_requirement(user, product))


def _save_pending_card(request):
    from ptjc_resumes.models import BusinessCardDraft
    data = request.session.get('pending_business_card')
    if data is None:
        return reverse('mobility_try_cards')
    if BusinessCardDraft.objects.filter(owner=request.user).count() >= 30:
        return None
    draft = BusinessCardDraft.objects.create(owner=request.user, data=data)
    del request.session['pending_business_card']
    request.session.pop('pending_business_card_audience', None)
    return reverse(_card_account(request.user), kwargs={'pk': draft.pk})


@never_cache
def claim_card(request):
    from django.http import HttpResponseNotAllowed
    if request.method not in ('GET', 'POST'):
        return HttpResponseNotAllowed(['GET', 'POST'])
    account = _card_account(request.user)
    portal = request.session.get('pending_business_card_audience')
    path = reverse('mobility_claim_card')
    if request.method == 'POST' and account:
        if not _card_eligible(request.user):
            return HttpResponse('This product is unavailable for your account type.', status=403)
        url = _save_pending_card(request)
        if url is None:
            return HttpResponse('Delete an unused card draft before saving another.', status=400)
        return redirect(url)
    return render(request, 'ptjc_resumes/international_card_claim.html' if portal == 'international' else 'ptjc_resumes/card_claim.html', {
        'card_pending':'pending_business_card' in request.session,
        'can_save':bool(account),
        'board_login':reverse('login')+'?next='+path if portal != 'international' else '',
        'international_login':_international_card_login(path) if portal != 'canadian' else '',
    })


def _international_card_login(path):
    from django.urls import NoReverseMatch
    try:
        return reverse('mobility_international_login')+'?next='+path
    except NoReverseMatch:
        return ''
