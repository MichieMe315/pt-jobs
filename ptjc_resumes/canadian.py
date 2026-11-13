from django import forms
from django.forms import formset_factory
from django.core.exceptions import ValidationError
from django.db.models import F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from functools import wraps
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from django.contrib.auth.decorators import login_required
from .models import ResumeDraft, ResumeTemplate
from .offers import LAYOUTS, available_offers, layout_access
from .pdf import render_pdf
from .schema import normalize
from .specialties import TRACKS


class ResumeDetails(forms.Form):
    practice_track = forms.ChoiceField(choices=[(k, v[0]) for k, v in TRACKS.items()], required=False, label='Practice focus for writing prompts')
    target_role = forms.CharField(max_length=110, required=False, label='Target role (optional, printed on your résumé)', help_text='Use a job title you are applying for. Enter your actual registration separately.')
    name = forms.CharField(max_length=120)
    email = forms.EmailField(max_length=180)
    location = forms.CharField(max_length=180, label='City and province')
    phone = forms.CharField(max_length=80, required=False)
    summary = forms.CharField(max_length=1800, widget=forms.Textarea(attrs={'rows': 4}), label='Professional summary')
    specialties = forms.CharField(max_length=600, required=False, label='Clinical interests and skills')
    home_registration = forms.CharField(max_length=500, required=False, label='Canadian regulator, registration class and number (if held)')
    layout = forms.ChoiceField(choices=LAYOUTS.items())
    revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)


class Experience(forms.Form):
    role = forms.CharField(max_length=160)
    employer = forms.CharField(max_length=180, label='Employer or placement')
    location = forms.CharField(max_length=100, required=False)
    dates = forms.CharField(max_length=100)
    bullets = forms.CharField(max_length=2500, label='Responsibilities and outcomes (one per line)', widget=forms.Textarea(attrs={'rows': 4}))


class Education(forms.Form):
    degree = forms.CharField(max_length=180, label='Qualification')
    institution = forms.CharField(max_length=180)
    country = forms.CharField(max_length=100)
    completed = forms.CharField(max_length=80, required=False)


class Development(forms.Form):
    course = forms.CharField(max_length=180, label='Course or certification')
    provider = forms.CharField(max_length=180, required=False)
    completed = forms.CharField(max_length=80, required=False)


sections = [('canadian_experience', 'Clinical experience', Experience, 0), ('education', 'Education', Education, 1), ('development', 'Courses and certifications', Development, 0)]


def template():
    return get_object_or_404(ResumeTemplate, key='canadian-professional', is_enabled=True)


def draft_for(user, pk):
    return get_object_or_404(ResumeDraft.objects.select_related('template__access_product'), pk=pk, owner=user, template__key='canadian-professional', template__is_enabled=True)


def canadian_account(view):
    @login_required
    @wraps(view)
    def checked(request, *args, **kwargs):
        profile = getattr(request.user, 'jobseeker', None)
        if not profile:
            return redirect('login')
        if not profile.is_approved:
            return HttpResponse('Your job seeker account is waiting for approval.', status=403)
        if not request.user.is_active or not profile.login_active:
            return HttpResponse('This job seeker account is disabled.', status=403)
        return view(request, *args, **kwargs)
    return checked


@never_cache
@canadian_account
@require_GET
def index(request):
    selected = template()
    return render(request, 'ptjc_resumes/canadian_index.html', {
        'drafts': ResumeDraft.objects.filter(owner=request.user, template=selected), 'practice_tracks': [(k,v[0]) for k,v in TRACKS.items()],
        'resume_offers': available_offers(selected, request.user),
    })


@never_cache
@canadian_account
@require_POST
def create(request):
    selected = template()
    if ResumeDraft.objects.filter(owner=request.user, template=selected).count() >= 30:
        return HttpResponse('Delete an unused draft before creating another.', status=400)
    draft = ResumeDraft.objects.create(owner=request.user, template=selected, title='Canadian physiotherapy resume',
        data=normalize({**selected.design_defaults(), 'name': request.user.get_full_name(), 'email': request.user.email, 'practice_track': request.POST.get('practice_track') if request.POST.get('practice_track') in TRACKS else 'general'}))
    return redirect('ptjc_canadian_resumes:canadian_edit', pk=draft.pk)


@never_cache
@canadian_account
@require_http_methods(['GET', 'POST'])
def edit(request, pk):
    draft = draft_for(request.user, pk)
    if request.method == 'GET':
        from .canadian_editor import workspace
        return workspace(request, draft, public=False)
    data = normalize(draft.data)
    form = ResumeDetails(request.POST if request.method == 'POST' else None, initial={**data, 'revision': draft.revision})
    rows = [(label, formset_factory(fields, extra=2, min_num=minimum, validate_min=True, max_num=12, validate_max=True)(
        request.POST if request.method == 'POST' else None, initial=data[key], prefix=key)) for key, label, fields, minimum in sections]
    if request.method == 'POST':
        ok = form.is_valid()
        for _, group in rows:
            ok = group.is_valid() and ok
        if ok:
            values = {**data, **form.cleaned_data}
            revision = values.pop('revision')
            values.update({key: [row for row in group.cleaned_data if row] for (key, *_), (_, group) in zip(sections, rows)})
            try:
                values = normalize(values)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                saved = ResumeDraft.objects.filter(pk=draft.pk, revision=revision).update(data=values, revision=F('revision')+1, updated_at=timezone.now())
                if saved:
                    return redirect('ptjc_canadian_resumes:canadian_edit', pk=pk)
                form.add_error(None, 'This draft changed in another tab. Copy your edits and reload before saving.')
    return render(request, 'ptjc_resumes/canadian_edit.html', {
        'draft': draft, 'form': form, 'sections': rows, 'track_prompts': {key: value[1] for key, value in TRACKS.items()},
        'resume_offers': available_offers(draft.template, request.user),
        'paid': layout_access(request.user, draft.template, data['layout']),
    })


@never_cache
@canadian_account
@require_GET
def export(request, pk, preview=False):
    draft = draft_for(request.user, pk)
    data = normalize(draft.data)
    if not preview:
        if not layout_access(request.user, draft.template, data['layout']):
            return HttpResponse('Purchase this design or the all-four pack before downloading.', status=403)
        if not (data['name'] and data['email'] and data['education']):
            return HttpResponse('Save your name, contact details and education before downloading.', status=400)
    pdf = render_pdf(data, preview=preview, canadian=True)
    if not preview:
        from .offers import paid_layout_access, starter_product
        from career_mobility.starter import authorize
        if not paid_layout_access(request.user, draft.template, data['layout']) and not authorize(request.user, starter_product(request.user, draft.template, data['layout']), 1):
            return HttpResponse('No starter résumé exports remain.', status=403)
    if not preview:
        from .offers import starter_product
        from career_mobility.product_activity import record
        product = starter_product(request.user, draft.template, data['layout']) or draft.template.access_product
        if product:
            record(product, 'exported', request=request)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = ('inline' if preview else 'attachment') + '; filename="' + (slugify(data['name'])[:90] or 'canadian-resume') + '.pdf"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@never_cache
@canadian_account
@require_POST
def delete(request, pk):
    draft_for(request.user, pk).delete()
    return redirect('ptjc_canadian_resumes:canadian_index')
