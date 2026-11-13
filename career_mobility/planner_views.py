from urllib.parse import urlencode
from django.shortcuts import redirect
from django.http import JsonResponse,HttpResponseForbidden
from django.views.decorators.http import require_GET,require_POST
from django.contrib.auth.decorators import login_required
from .planning import build,from_answers
from .models import InternationalChecklistItem
FIELDS=('country_of_education','destination_province','application_history','registered_in_education_country')
def snapshot(answers):return {f:getattr(answers,f) for f in FIELDS}
def apply_pending(request,profile,*,update_answers=True):
    pending=request.session.pop('international_pending',None)
    if not pending:return
    if update_answers:
        for key,value in pending['answers'].items():setattr(profile,key,value)
        profile.save(update_fields=FIELDS)
    valid={s['key'] for s in build(profile)['steps']}
    done=set(pending.get('completed',[])) & valid
    for key in valid:InternationalChecklistItem.objects.update_or_create(profile=profile,key=key,defaults={'completed':key in done})
@require_GET
def preview(request):
    try:profile=from_answers(request.GET)
    except ValueError as exc:return JsonResponse({'error':str(exc)},status=400)
    plan=build(profile)
    from django.urls import reverse
    plan['country_url']=reverse('mobility_country',args=[plan['country']['slug']]) if plan['country'] else ''
    plan['signup']=snapshot(profile)
    return JsonResponse(plan)
@require_POST
def capture(request):
    try:answers=from_answers(request.POST)
    except ValueError as exc:return JsonResponse({'error':str(exc)},status=400)
    valid={s['key'] for s in build(answers)['steps']}
    profile=getattr(request.user,'international_pt_profile',None)
    completed=[s for s in request.POST.getlist('completed') if s in valid]
    if profile and 'completed' not in request.POST:
        completed=list(profile.checklist_items.filter(completed=True,key__in=valid).values_list('key',flat=True))
    request.session['international_pending']={'answers':snapshot(answers),'completed':completed}
    if profile:
        apply_pending(request,profile)
        return redirect('mobility_international_dashboard')
    return redirect('mobility_international_login' if request.POST.get('account_action')=='login' else 'mobility_international_signup')
@login_required
@require_POST
def save_answers(request):
    if not hasattr(request.user,'international_pt_profile'):return HttpResponseForbidden('International account required.')
    return capture(request)
