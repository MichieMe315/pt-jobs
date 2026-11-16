"""Canadian entry points for the shared résumé workspace."""
import json
import uuid

from django.core.exceptions import ValidationError
from django.db.models import F
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from . import canadian
from .ad_context import placement
from .models import ResumeDraft, ResumeTemplate
from .offers import LAYOUTS, available_offers, layout_access
from .pdf import render_pdf
from .schema import DEFAULT_ORDER, PROVINCES, normalize
from .specialties import TRACKS

KEY = 'canadian_guest_resume'
NS = 'ptjc_canadian_resumes:canadian_'


def guest(request):
    if KEY not in request.session:
        request.session[KEY] = {'id': uuid.uuid4().hex, 'title': 'My Canadian resume', 'revision': 1, 'data': normalize(ResumeTemplate.new_draft_data('canadian-professional'))}
    return request.session[KEY]


def workspace(request, draft, *, public):
    pk = [] if public else [draft.pk]
    def url(name):
        return reverse(NS + name, args=pk)

    data = normalize(draft['data'] if public else draft.data)
    profile = getattr(request.user, 'jobseeker', None)
    can_claim = bool(profile and profile.is_approved and profile.login_active and request.user.is_active)
    paid = not public and layout_access(request.user, draft.template, data['layout'])
    cfg = {
        'canadian': True, 'public': public, 'data': data,
        'revision': draft['revision'] if public else draft.revision,
        'save_url': url('guest_save' if public else 'save'),
        'preview_url': url('guest_preview' if public else 'preview'),
        'download_url': '' if public else url('download'),
        'claim_url': reverse(NS + 'claim') if public else '',
        'tracks': {k: list(v) for k, v in TRACKS.items()}, 'order': DEFAULT_ORDER,
        'sources': [], 'paid': paid,
        'registration_provinces': PROVINCES,
        'paid_layouts': [] if public else [key for key in LAYOUTS if layout_access(request.user, draft.template, key)],
    }
    template = ResumeTemplate.objects.filter(key='canadian-professional', is_enabled=True).first() if public else draft.template
    return render(request, 'ptjc_resumes/canadian_workspace.html', {
        'canadian': True, 'draft': draft, 'public_editor': public, 'bootstrap': cfg,
        'paid': paid, 'can_claim': can_claim, 'resume_ad': placement(),
        'resume_offers': [] if public else available_offers(draft.template, request.user),
    })


@never_cache
@require_GET
def start(request):
    template = ResumeTemplate.objects.select_related('access_product').filter(key='canadian-professional', is_enabled=True).first()
    if template and template.access_product:
        from career_mobility.product_activity import record
        record(template.access_product, 'opened', request=request)
    profile = getattr(request.user, 'jobseeker', None)
    if KEY not in request.session and profile and profile.is_approved and profile.login_active and request.user.is_active:
        selected = ResumeTemplate.objects.filter(key='canadian-professional', is_enabled=True).first()
        existing = ResumeDraft.objects.filter(owner=request.user, template=selected).order_by('-updated_at').first() if selected else None
        if existing:
            return redirect(NS + 'edit', pk=existing.pk)
    return workspace(request, guest(request), public=True)


def payload(request):
    raw = json.loads(request.body)
    if not isinstance(raw, dict) or type(raw.get('revision')) is not int:
        raise ValueError
    title = raw.get('title')
    if not isinstance(title, str) or not title.strip() or len(title) > 120:
        raise ValueError
    return raw['revision'], title.strip(), normalize(raw.get('data'))


def save(request, record=None):
    if len(request.body) > 160000:
        return JsonResponse({'error': 'Draft is too large.'}, status=413)
    try:
        revision, title, data = payload(request)
    except (ValueError, UnicodeError, ValidationError):
        return JsonResponse({'error': 'Check the draft fields.'}, status=400)
    now = timezone.now()
    if record is None:
        draft = guest(request)
        changed = draft['revision'] == revision
        if changed:
            draft.update(data=data, title=title, revision=revision + 1)
            request.session[KEY] = draft
    else:
        changed = ResumeDraft.objects.filter(pk=record.pk, owner=request.user, revision=revision).update(
            data=data, title=title, revision=F('revision') + 1, updated_at=now)
    if not changed:
        return JsonResponse({'error': 'This draft changed in another tab. Copy your unsaved work before reloading.'}, status=409)
    if record is not None and record.template.access_product:
        from career_mobility.product_activity import record as track_product
        track_product(record.template.access_product, 'saved', request=request)
    return JsonResponse({'revision': revision + 1, 'saved_at': now.isoformat()})


@never_cache
@require_POST
def guest_save(request):
    return save(request)


@never_cache
@canadian.canadian_account
@require_POST
def saved_save(request, pk):
    return save(request, canadian.draft_for(request.user, pk))


@never_cache
@require_POST
def guest_preview(request):
    response = HttpResponse(render_pdf(guest(request)['data'], preview=True, canadian=True), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="canadian-resume-preview.pdf"'
    return response


def save_guest_to_account(request, user):
    """Attach the browser draft to the new account before approval or login."""
    draft = request.session.get(KEY)
    if not draft:
        return None
    template = ResumeTemplate.objects.filter(key='canadian-professional', is_enabled=True).first()
    if not template:
        return None
    record, _ = ResumeDraft.objects.get_or_create(pk=uuid.UUID(draft['id']), owner=user, defaults={
        'template': template, 'title': draft['title'], 'data': normalize(draft['data']),
    })
    request.session.pop(KEY, None)
    return record


@never_cache
@canadian.canadian_account
@require_http_methods(['GET', 'POST'])
def claim(request):
    draft = request.session.get(KEY)
    if not draft:
        return redirect(NS + 'index')
    if request.method == 'GET':
        return render(request, 'ptjc_resumes/claim.html', {'canadian': True})
    pk = uuid.UUID(draft['id'])
    existing = ResumeDraft.objects.filter(pk=pk, owner=request.user).exists()
    if not existing and ResumeDraft.objects.filter(owner=request.user, template__key='canadian-professional').count() >= 30:
        return HttpResponse('Delete an unused draft before saving another.', status=400)
    record = save_guest_to_account(request, request.user)
    if record is None:
        return HttpResponse('The Canadian resume template is unavailable. Your draft is still in this browser.', status=503)
    return redirect(NS + 'edit', pk=record.pk)
