"""Staff approval queue with the existing profile decision and email handling."""
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from .models import Employer, JobSeeker
from .operations import can_view, queryset_for, record_url

TYPES = {'employers':(Employer,'Employers'), 'candidates':(JobSeeker,'Job seekers')}


def queue(request):
    kinds = {kind:(model,label) for kind,(model,label) in TYPES.items() if can_view(request.user,model)}
    if not kinds:
        raise PermissionDenied
    kind = request.GET.get('kind') or next(iter(kinds))
    if kind not in TYPES:
        raise Http404
    if kind not in kinds:
        raise PermissionDenied
    model,label = kinds[kind]
    selected = queryset_for(request,model).filter(is_approved=False).order_by('-updated_at','-pk')
    page=Paginator(selected,25).get_page(request.GET.get('page'))
    model_admin=admin.site._registry[model]
    rows=[]
    for item in page:
        rows.append({
            'name':str(item),'email':item.email,'location':item.location if model is Employer else item.current_location,
            'updated':item.updated_at,'record_url':record_url(request,item),
            'approve_url':reverse(f'admin:board_{model._meta.model_name}_approve_profile',args=[item.pk])
                if model_admin.has_change_permission(request,item) else '',
        })
    return render(request,'admin/workspace/review_queue.html',{
        **admin.site.each_context(request),'title':'Account review','kind':kind,'label':label,'page':page,'rows':rows,
        'tabs':[{'key':key,'label':label,'count':queryset_for(request,model).filter(is_approved=False).count()}
                for key,(model,label) in kinds.items()],
    })
