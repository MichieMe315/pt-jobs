import json
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.core.exceptions import ValidationError
from django.db.models import F
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from career_mobility.models import ProductOrder
from .models import ResumeDraft, ResumeTemplate
from .schema import normalize, completion_errors, PROVINCES, PATHWAYS, REGISTRATION, ASSESSMENT, PET, EXAM, SOURCES, DEFAULT_ORDER
from .pdf import render_pdf
from .offers import LAYOUTS, layout_access, available_offers

def international_only(view):
    @wraps(view)
    def guarded(request,*args,**kwargs):
        if not hasattr(request.user,'international_pt_profile'):
            return HttpResponse('An international planning account is required.',status=403)
        return view(request,*args,**kwargs)
    return login_required(guarded,login_url='mobility_international_login')

MAX_BODY=160000

def owned(user,template):
    from career_mobility.store_access import has_access
    return bool(template.access_product_id and has_access(user,template.access_product))

def get_draft(user,pk):
    return get_object_or_404(ResumeDraft.objects.select_related('template__access_product'),pk=pk,owner=user,template__is_enabled=True,template__key='international-professional')

@never_cache
@require_GET
def index(request):
    if not request.user.is_authenticated or not hasattr(request.user,'international_pt_profile'):return redirect('ptjc_resumes:start')
    template=ResumeTemplate.objects.select_related('access_product').filter(key='international-professional',is_enabled=True).first()
    return render(request,'ptjc_resumes/index.html',{'template':template,'drafts':ResumeDraft.objects.filter(owner=request.user,template=template) if template else [],'paid':owned(request.user,template) if template else False,'resume_offers':available_offers(template,request.user) if template else []})

@never_cache
@international_only
@require_POST
def create(request):
    template=get_object_or_404(ResumeTemplate,key='international-professional',is_enabled=True)
    if ResumeDraft.objects.filter(owner=request.user).count()>=30:return HttpResponse('You have 30 saved resumes. Delete an unused draft before creating another.',status=400)
    d=ResumeDraft.objects.create(owner=request.user,template=template,data=normalize({**template.design_defaults(),'email':request.user.email,'name':request.user.get_full_name(),'education_country':request.user.international_pt_profile.country_of_education,'destination':request.user.international_pt_profile.destination_province if request.user.international_pt_profile.destination_province in PROVINCES else ''}))
    return redirect('ptjc_resumes:edit',pk=d.pk)

@never_cache
@international_only
@require_GET
def edit(request,pk,step=1):
    if step<1 or step>10:raise Http404
    draft=get_draft(request.user,pk);template=draft.template;product=template.access_product
    data = normalize(draft.data)
    bootstrap={'step':step-1,'step_urls':[reverse('ptjc_resumes:edit_step',args=[draft.pk,n]) for n in range(1,11)],'data':data,'completion_errors':completion_errors(data),'title':draft.title,'revision':draft.revision,'save_url':reverse('ptjc_resumes:save',args=[draft.pk]),'preview_url':reverse('ptjc_resumes:preview',args=[draft.pk]),'download_url':reverse('ptjc_resumes:download',args=[draft.pk]),'paid':layout_access(request.user,template,normalize(draft.data)['layout']),'choices':{'destination':PROVINCES,'pathway':PATHWAYS,'canadian_registration':REGISTRATION,'assessment':ASSESSMENT,'pet':PET,'exam':EXAM},'sources':SOURCES,'order':DEFAULT_ORDER}
    from .ad_context import placement
    bootstrap['paid_layouts'] = [key for key in LAYOUTS if layout_access(request.user, template, key)]
    return render(request,'ptjc_resumes/editor.html',{'draft':draft,'product':product,'bootstrap':bootstrap,'paid':bootstrap['paid'],'resume_ad':placement(),'resume_offers':available_offers(template,request.user)})

@never_cache
@international_only
@require_POST
def save(request,pk):
    draft=get_draft(request.user,pk)
    if len(request.body)>MAX_BODY:return JsonResponse({'error':'Resume exceeds the permitted size.'},status=413)
    try:
        raw=json.loads(request.body)
        if not isinstance(raw,dict):raise ValidationError('Invalid save request.')
        title=raw.get('title','My international resume')
        rev=raw.get('revision')
        if not isinstance(title,str) or not title.strip() or len(title)>120:raise ValidationError('Give this draft a title of 1–120 characters.')
        if type(rev) is not int or rev<1:raise ValidationError('Invalid draft revision.')
        data=normalize(raw.get('data'))
    except (ValueError,UnicodeDecodeError,ValidationError) as exc:
        return JsonResponse({'error':'; '.join(exc.messages) if isinstance(exc,ValidationError) else 'Invalid JSON.'},status=400)
    changed=ResumeDraft.objects.filter(pk=draft.pk,owner=request.user,revision=rev).update(title=title.strip(),data=data,revision=F('revision')+1,updated_at=timezone.now())
    if not changed:return JsonResponse({'error':'This draft changed in another tab. Your text remains here. Copy any unsaved changes before reloading.','conflict':True},status=409)
    if draft.template.access_product:
        from career_mobility.product_activity import record
        record(draft.template.access_product, 'saved', request=request)
    return JsonResponse({'revision':rev+1,'saved_at':timezone.now().isoformat(),'completion_errors':completion_errors(data)})

@never_cache
@international_only
@require_GET
def preview(request,pk):
    draft=get_draft(request.user,pk)
    r=HttpResponse(render_pdf(normalize(draft.data),preview=True),content_type='application/pdf');r['Content-Disposition']='inline; filename="resume-preview.pdf"';r['X-Content-Type-Options']='nosniff';return r

@never_cache
@international_only
@require_GET
def download(request,pk):
    draft=get_draft(request.user,pk)
    if not layout_access(request.user,draft.template,normalize(draft.data)['layout']):return JsonResponse({'error':'This design is locked. Purchase it individually or unlock all four designs.'},status=403)
    data=normalize(draft.data);errors=completion_errors(data)
    if errors:return JsonResponse({'error':'Complete the required details first.','fields':errors},status=400)
    pdf = render_pdf(data)
    from .offers import paid_layout_access, starter_product
    from career_mobility.starter import authorize
    if not paid_layout_access(request.user, draft.template, data['layout']) and not authorize(request.user, starter_product(request.user, draft.template, data['layout']), 1):
        return JsonResponse({'error':'No starter résumé exports remain.'}, status=403)
    from .offers import starter_product
    from career_mobility.product_activity import record
    product = starter_product(request.user, draft.template, data['layout']) or draft.template.access_product
    if product:
        record(product, 'exported', request=request)
    r=HttpResponse(pdf,content_type='application/pdf');r['Content-Disposition']='attachment; filename="'+(slugify(data['name'])[:90] or 'international-applicant')+'-resume.pdf"';r['X-Content-Type-Options']='nosniff';return r

@never_cache
@international_only
@require_POST
def delete(request,pk):
    draft=get_draft(request.user,pk);draft.delete();return redirect('ptjc_resumes:index')
