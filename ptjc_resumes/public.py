"""Session-only public editing. Account ownership is required to save to a profile."""
import json,uuid
from django.core.exceptions import ValidationError
from django.http import JsonResponse,HttpResponse
from django.shortcuts import render,redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST,require_http_methods
from django.utils import timezone
from .models import ResumeTemplate,ResumeDraft
from .schema import normalize,completion_errors,PROVINCES,PATHWAYS,REGISTRATION,ASSESSMENT,PET,EXAM,SOURCES,DEFAULT_ORDER
from .views import international_only
from .ad_context import placement
KEY='public_resume_draft'

def session_draft(request):
    data=request.session.get(KEY)
    if not isinstance(data,dict):
        data={'id':uuid.uuid4().hex,'data':normalize(ResumeTemplate.new_draft_data('international-professional')),'title':'My international resume','revision':1}
        request.session[KEY]=data
    return data

@never_cache
def start(request):
    if KEY not in request.session and request.user.is_authenticated and hasattr(request.user, 'international_pt_profile'):
        existing = ResumeDraft.objects.filter(owner=request.user, template__key='international-professional', template__is_enabled=True).order_by('-updated_at').first()
        if existing:
            return redirect('ptjc_resumes:edit', pk=existing.pk)
    return step(request, step=1)

@never_cache
def step(request,step):
    if step<1 or step>10:return HttpResponse('Section not found',status=404)
    draft=session_draft(request)
    template=ResumeTemplate.objects.select_related('access_product').filter(key='international-professional',is_enabled=True).first()
    product=template.access_product if template else None
    if product and step == 1:
        from career_mobility.product_activity import record
        record(product, "opened", request=request)
    data = normalize(draft['data'])
    bootstrap={'data':data,'completion_errors':completion_errors(data),'title':draft['title'],'revision':draft['revision'],'step':step-1,'public':True,'step_urls':[reverse('ptjc_resumes:public_step',args=[n]) for n in range(1,11)],'save_url':reverse('ptjc_resumes:public_save'),'preview_url':reverse('ptjc_resumes:public_preview'),'download_url':'','claim_url':reverse('ptjc_resumes:claim'),'paid':False,'choices':{'destination':PROVINCES,'pathway':PATHWAYS,'canadian_registration':REGISTRATION,'assessment':ASSESSMENT,'pet':PET,'exam':EXAM},'sources':SOURCES,'order':DEFAULT_ORDER}
    return render(request,'ptjc_resumes/editor.html',{'draft':draft,'product':product,'bootstrap':bootstrap,'public_editor':True,'can_claim':bool(getattr(getattr(request.user, 'international_pt_profile', None), 'email_is_verified', False)),'resume_ad':placement()})

@never_cache
@require_POST
def save(request):
    if len(request.body)>160000:return JsonResponse({'error':'Draft is too large.'},status=413)
    draft=session_draft(request)
    try:
        raw=json.loads(request.body)
        if not isinstance(raw,dict) or type(raw.get('revision')) is not int:raise ValueError
        if raw['revision']!=draft['revision']:return JsonResponse({'error':'This draft changed in another tab. Copy your unsaved work before reloading.','conflict':True},status=409)
        title=raw.get('title','My international resume')
        if not isinstance(title,str) or not title.strip() or len(title)>120:raise ValueError
        data=normalize(raw.get('data'))
    except (ValueError,UnicodeError,ValidationError):return JsonResponse({'error':'Check the draft fields.'},status=400)
    draft.update(data=data,title=title.strip(),revision=draft['revision']+1);request.session[KEY]=draft
    return JsonResponse({'revision':draft['revision'],'saved_at':timezone.now().isoformat(),'completion_errors':completion_errors(data)})

@never_cache
@require_POST
def preview(request):
    from .pdf import render_pdf
    draft=session_draft(request)
    response=HttpResponse(render_pdf(normalize(draft['data']),preview=True),content_type='application/pdf');response['Cache-Control']='private, no-store';response['Content-Disposition']='inline; filename="resume-preview.pdf"';return response

@never_cache
@international_only
@require_http_methods(['GET','POST'])
def claim(request):
    if not request.user.international_pt_profile.email_is_verified:return redirect('mobility_verify_pending')
    if request.method=='GET':return render(request,'ptjc_resumes/claim.html')
    draft=request.session.get(KEY)
    if not draft:return redirect('ptjc_resumes:index')
    template=ResumeTemplate.objects.filter(key='international-professional',is_enabled=True).first()
    if not template:return HttpResponse('The resume template is not available yet.',status=503)
    if ResumeDraft.objects.filter(owner=request.user).count()>=30:return HttpResponse('Delete an unused draft before saving another.',status=400)
    from django.db import transaction
    from django.contrib.auth import get_user_model
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        # A stable public-draft identifier makes claim POST replays idempotent.
        claimed=request.session.get('claimed_public_resumes',{})
        pk=claimed.get(draft['id'])
        record=ResumeDraft.objects.filter(pk=pk,owner=request.user).first() if pk else None
        if record is None:
            record,_=ResumeDraft.objects.get_or_create(pk=uuid.UUID(draft['id']),owner=request.user,defaults={'template':template,'title':draft['title'],'data':normalize(draft['data'])})
        claimed[draft['id']]=str(record.pk);request.session['claimed_public_resumes']=dict(list(claimed.items())[-30:]);request.session.pop(KEY,None)
    return redirect('ptjc_resumes:edit',pk=record.pk)
