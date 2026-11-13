from urllib.parse import urlencode
from django import forms
from django.contrib import admin,messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q,F
from django.core.paginator import Paginator
from django.shortcuts import render,redirect
from django.urls import path,reverse
from board.models import Employer,EmployerMarketingProfile,MarketingAudience
from .contacts import annotate_employers,exportable,csv_response
from .generator import PROVINCES

class ContactFilters(forms.Form):
    q=forms.CharField(required=False,label='Company, email or community',max_length=160)
    province=forms.ChoiceField(required=False,choices=[('','All provinces / territories')]+list(PROVINCES.items()))
    community=forms.ChoiceField(required=False,choices=[('','All communities'),('rural_remote','Rural and remote')]+EmployerMarketingProfile.SETTLEMENT)
    organization=forms.ChoiceField(required=False,choices=[('','All organization types')]+EmployerMarketingProfile.TYPES)
    contact_status=forms.ChoiceField(required=False,choices=[('','All contact statuses')]+EmployerMarketingProfile.CONTACT)
    hiring=forms.ChoiceField(required=False,choices=[('','Any hiring activity'),('active','Active jobs'),('inactive','No active jobs')])
    sort=forms.ChoiceField(required=False,choices=[('company_name','Company A–Z'),('-company_name','Company Z–A'),('_marketing_city','City A–Z'),('_marketing_province','Province A–Z'),('-created_at','Newest accounts'),('-updated_at','Recently edited'),('-_last_paid','Most recent payment'),('-_active_jobs','Most active postings')])

def contacts(request):
    if not request.user.has_perm('board.view_employer'):raise PermissionDenied
    can_classify=request.user.has_perms(['board.add_employermarketingprofile','board.change_employermarketingprofile'])
    if request.method=='POST' and request.POST.get('classify') in ('preview','apply'):
        if not can_classify:raise PermissionDenied
        from .classify import classify_employers
        apply=request.POST['classify']=='apply'
        counts=classify_employers(apply=apply)
        messages.info(request, f"{'Applied' if apply else 'Preview'}: scanned {counts['scanned']} employers; {counts['matched']} with updates. City: {counts['city']}; province: {counts['province']}; organization: {counts['organization_type']}; community type: {counts['settlement']}. {counts['community_review']} still need community review.")
        return redirect('admin:marketing_contacts')
    form=ContactFilters(request.GET if request.method=='GET' else request.POST)
    qs=annotate_employers(Employer.objects.all())
    if form.is_valid():
        data=form.cleaned_data
        if data['q']:qs=qs.filter(Q(company_name__icontains=data['q'])|Q(email__icontains=data['q'])|Q(location__icontains=data['q'])|Q(marketing_profile__city__icontains=data['q'])|Q(marketing_profile__tags__icontains=data['q']))
        if data['province']:qs=qs.filter(_marketing_province=PROVINCES[data['province']])
        community=data['community']
        if community=='rural_remote':qs=qs.filter(marketing_profile__settlement__in=['rural','remote'])
        elif community=='unknown':qs=qs.filter(Q(marketing_profile__isnull=True)|Q(marketing_profile__settlement='unknown'))
        elif community:qs=qs.filter(marketing_profile__settlement=community)
        if data['organization']=='unknown':qs=qs.filter(Q(marketing_profile__isnull=True)|Q(marketing_profile__organization_type='unknown'))
        elif data['organization']:qs=qs.filter(marketing_profile__organization_type=data['organization'])
        if data['contact_status']:qs=qs.filter(_contact_status=data['contact_status'])
        if data['hiring']=='active':qs=qs.filter(_active_jobs__gt=0)
        elif data['hiring']=='inactive':qs=qs.filter(_active_jobs=0)
        order=F('_last_paid').desc(nulls_last=True) if data['sort']=='-_last_paid' else (data['sort'] or 'company_name')
        qs=qs.order_by(order,'pk')
    else:qs=qs.none()
    if request.GET.get('export')=='csv':
        if not request.user.has_perm('board.view_employermarketingprofile'):raise PermissionDenied
        if form.errors:
            from django.http import HttpResponse
            return HttpResponse('Correct the filters before exporting.',status=400)
        return csv_response(qs)
    if request.method=='POST':
        if not request.user.has_perm('board.add_marketingaudience'):raise PermissionDenied
        name=request.POST.get('audience_name','').strip()
        if form.is_valid() and name and len(name)<=150:
            from django.db import transaction
            with transaction.atomic():
                audience=MarketingAudience.objects.create(name=name,description='Saved selection of existing PTJC employers. Review contact status before exporting.')
                audience.employers.set(qs.values_list('pk',flat=True))
            messages.success(request,f'Saved {audience.employers.count()} employers. No email was sent.')
            return redirect('admin:board_marketingaudience_change',audience.pk)
        messages.error(request,'Choose valid filters and enter an audience name of 1–150 characters.')
    page=Paginator(qs,30).get_page(request.GET.get('page'))
    rows=[]
    for employer in page:
        profile=getattr(employer,'marketing_profile',None)
        if profile:url=reverse('admin:board_employermarketingprofile_change',args=[profile.pk])
        else:url=reverse('admin:board_employermarketingprofile_add')+'?'+urlencode({'employer':employer.pk})
        rows.append({'employer':employer,'profile':profile,'review_url':url,'city':employer._marketing_city,'province':employer._marketing_province,'jobs':employer._active_jobs,'paid':employer._last_paid})
    query=request.GET.copy();query.pop('page',None)
    context={**admin.site.each_context(request),'title':'Marketing contacts','can_classify':can_classify,'form':form,'rows':rows,'page_obj':page,'query':query.urlencode(),'approved_count':sum(1 for _ in exportable(qs)),'audiences':MarketingAudience.objects.order_by('-updated_at')[:8] if request.user.has_perm('board.view_marketingaudience') else [],'can_export':request.user.has_perm('board.view_employermarketingprofile'),'can_save':request.user.has_perm('board.add_marketingaudience'),'can_review':request.user.has_perm('board.change_employermarketingprofile') or request.user.has_perm('board.add_employermarketingprofile')}
    return render(request,'admin/marketing/contacts.html',context)

def install_contact_urls():
    if getattr(admin.site,'_marketing_contacts_installed',False):return
    old=admin.site.get_urls
    admin.site.get_urls=lambda:[path('marketing/contacts/',admin.site.admin_view(contacts),name='marketing_contacts')]+old()
    admin.site._marketing_contacts_installed=True
