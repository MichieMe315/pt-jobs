"""Permission-aware, read-only record review alongside the existing Django admin."""
import csv
from datetime import datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode
from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Value, Sum
from django.db.models.functions import Lower, Trim, StrIndex, Substr
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import path, reverse
from django.utils import timezone
from .models import Employer, JobSeeker, Job, Application, Invoice, JobAlert, PurchasedPackage, Resume

# Keep the familiar admin record types; no user/account types are combined.
RECORDS = {
 'employers': (Employer, 'Employers', ['id','company_name','email','location','credits','is_approved','login_active','created_at'], ['company_name','name','email','phone','website','location','user__username']),
 'candidates': (JobSeeker, 'Job seekers', ['id','first_name','last_name','email','current_location','is_approved','login_active','created_at'], ['first_name','last_name','email','current_location','position_desired','user__username']),
 'jobs': (Job, 'Job postings', ['id','title','employer__company_name','location','posting_date','expiry_date','is_active'], ['title','employer__company_name','employer__email','location']),
 'applications': (Application, 'Applications', ['id','job__title','jobseeker__email','created_at'], ['job__title','job__employer__company_name','jobseeker__email','jobseeker__first_name','jobseeker__last_name']),
 'billing': (Invoice, 'Invoices', ['id','employer__company_name','amount','currency','status','processor','order_date'], ['employer__company_name','employer__email','processor_reference','discount_code']),
 'alerts': (JobAlert, 'Job alerts', ['id','email','q','location','active','created_at'], ['email','q','location']),
 'packages': (PurchasedPackage, 'Purchased packages', ['id','employer__company_name','package__name','credits_granted','credits_remaining','purchased_at','expires_at'], ['employer__company_name','employer__email','package__name','source']),
 'resumes': (Resume, 'Resumes', ['id','jobseeker__email','title','created_at'], ['jobseeker__email','jobseeker__first_name','jobseeker__last_name','title']),
}
DATES = {'jobs':'posting_date', 'billing':'order_date', 'packages':'purchased_at'}
RELATED = {'employers':('user',), 'candidates':('user',), 'jobs':('employer',), 'applications':('job','jobseeker'), 'billing':('employer',), 'packages':('employer','package'), 'resumes':('jobseeker',)}
LABELS = {'id':'ID','company_name':'Company','email':'Email','location':'Location','credits':'Credits','is_approved':'Approved','login_active':'Login enabled','created_at':'Created','first_name':'First name','last_name':'Last name','current_location':'Location','title':'Title','employer__company_name':'Employer','posting_date':'Posted','expiry_date':'Expires','is_active':'Active','job__title':'Job','jobseeker__email':'Job seeker','amount':'Amount','currency':'Currency','status':'Status','processor':'Payment method','order_date':'Order date','q':'Keywords','active':'Active','package__name':'Package','credits_granted':'Granted','credits_remaining':'Remaining','purchased_at':'Purchased','expires_at':'Credit expiry'}
PUBLIC_DOMAINS = {'gmail.com','googlemail.com','hotmail.com','hotmail.ca','outlook.com','outlook.ca','live.com','live.ca','yahoo.com','yahoo.ca','icloud.com','me.com','aol.com','msn.com','proton.me','protonmail.com','mail.com','shaw.ca','rogers.com','bell.net','sympatico.ca','telus.net','sasktel.net','videotron.ca','qq.com','163.com','example.com','example.test'}
DUPLICATES = {
 'employer-email': ('Employers · same email', Employer, 'employers', 'email'),
 'employer-name': ('Employers · same company name', Employer, 'employers', 'company_name'),
 'employer-domain': ('Employers · shared business email domain', Employer, 'employers', 'domain'),
 'job-title': ('Jobs · same employer, title and location', Job, 'jobs', 'title'),
 'candidate-email': ('Job seekers · same email', JobSeeker, 'candidates', 'email'),
 'invoice-reference': ('Invoices · repeated payment reference', Invoice, 'billing', 'processor_reference'),
}


class RecordFilters(forms.Form):
    q = forms.CharField(required=False, max_length=200, label='Search', widget=forms.TextInput(attrs={'type':'search','placeholder':'Company, email, location, reference or #ID'}))
    status = forms.ChoiceField(required=False, choices=[('','All statuses')])
    quality = forms.ChoiceField(required=False, choices=[('','All profiles'),('missing-logo','Missing logo'),('missing-description','Missing description'),('missing-email','Missing email'),('missing-location','Missing location')], label='Profile completeness')
    start = forms.DateField(required=False, label='From', widget=forms.DateInput(attrs={'type':'date'}))
    end = forms.DateField(required=False, label='To', widget=forms.DateInput(attrs={'type':'date'}))

    def __init__(self, *args, kind, **kwargs):
        super().__init__(*args, **kwargs)
        statuses = []
        if kind in ('employers','candidates'): statuses=[('pending','Pending approval'),('approved','Approved'),('disabled','Login disabled')]
        elif kind=='jobs': statuses=[('active','Active'),('inactive','Inactive / draft'),('expired','Expired')]
        elif kind=='billing': statuses=list(Invoice.STATUS_CHOICES)
        elif kind=='alerts': statuses=[('active','Active'),('inactive','Inactive')]
        elif kind=='packages': statuses=[('available','Available credits'),('expired','Expired credits'),('exhausted','No credits remaining')]
        self.fields['status'].choices=[('','All statuses')]+statuses
        if not statuses:self.fields.pop('status')
        if kind!='employers':self.fields.pop('quality')

    def clean(self):
        data=super().clean()
        if data.get('end') and data['end'].year >= 9999:
            self.add_error('end','Choose an end date before year 9999.')
        if data.get('start') and data.get('end') and data['start']>data['end']:
            self.add_error('end','Choose an end date on or after the start date.')
        return data


def can_view(user, model):
    opts=model._meta
    return user.is_active and user.is_staff and (user.has_perm(f'{opts.app_label}.view_{opts.model_name}') or user.has_perm(f'{opts.app_label}.change_{opts.model_name}'))


def queryset_for(request, model):
    model_admin=admin.site._registry.get(model)
    return model_admin.get_queryset(request) if model_admin else model.objects.all()


def record_url(request, obj):
    model_admin=admin.site._registry.get(type(obj))
    if model_admin and (model_admin.has_view_permission(request,obj) or model_admin.has_change_permission(request,obj)):
        return reverse(f'admin:{obj._meta.app_label}_{obj._meta.model_name}_change',args=[obj.pk])
    return None


def navigation(user):
    return [{'key':key,'label':label,'url':reverse('admin:operations_records',args=[key])} for key,(model,label,fields,search) in RECORDS.items() if can_view(user,model)]


def search_records(qs, query, fields):
    text=(query or '').strip()[:200]
    if not text:return qs
    raw=text.lstrip('#')
    if text.startswith('#') and raw.isascii() and raw.isdigit():
        return qs.filter(pk=int(raw)) if len(raw)<19 else qs.none()
    # All words must match; each word may occur in any searchable field.
    for term in text.split()[:12]:
        match=Q()
        for name in fields:match |= Q(**{name+'__icontains':term})
        if term.isascii() and term.isdigit() and len(term)<19:match |= Q(pk=int(term))
        qs=qs.filter(match)
    return qs


def incomplete(qs, field):
    return qs.annotate(_empty=Trim(field)).filter(Q(_empty='') | Q(**{field+'__isnull':True}))


def summary(user):
    today=timezone.localdate();cards=[]
    for model,label,query,key,status in [
        (Employer,'Employer approvals',Q(is_approved=False,login_active=True),'employers','pending'),
        (JobSeeker,'Job seeker approvals',Q(is_approved=False,login_active=True),'candidates','pending'),
        (Job,'Active jobs',Q(is_active=True)&(Q(expiry_date__gte=today)|Q(expiry_date__isnull=True)),'jobs','active'),
        (Job,'Expired jobs still active',Q(is_active=True,expiry_date__lt=today),'jobs','expired'),
    ]:
        if can_view(user,model):cards.append({'label':label,'value':model.objects.filter(query).count(),'url':reverse('admin:operations_records',args=[key])+'?status='+status,'attention':status in ('pending','expired')})
    if can_view(user,Invoice):
        amount=Invoice.objects.filter(status='paid',currency='CAD',order_date__date__gte=today-timedelta(days=29)).aggregate(total=Sum('amount'))['total'] or 0
        cards.append({'label':'Paid CAD sales · 30 days','value':f'${Decimal(amount)/100:,.2f}','url':reverse('admin:operations_records',args=['billing'])+'?'+urlencode({'status':'paid','start':(today-timedelta(days=29)).isoformat()})})
    return cards


def duplicate_choices(user):
    return [{'key':key,'label':label} for key,(label,model,kind,field) in DUPLICATES.items() if can_view(user,model)]


def quality_cards(request):
    if not can_view(request.user,Employer):return []
    qs=queryset_for(request,Employer);url=reverse('admin:operations_records',args=['employers'])
    return [
        {'label':'Missing logo','value':qs.filter(Q(logo='')|Q(logo__isnull=True)).count(),'url':url+'?quality=missing-logo'},
        {'label':'Missing description','value':qs.annotate(_a=Trim('company_description'),_b=Trim('description')).filter(Q(_a='')|Q(_a__isnull=True)).filter(Q(_b='')|Q(_b__isnull=True)).count(),'url':url+'?quality=missing-description'},
        {'label':'Missing email','value':incomplete(qs,'email').count(),'url':url+'?quality=missing-email'},
    ]


def workspace(request):
    nav=navigation(request.user)
    context={**admin.site.each_context(request),'title':'Operations','ops_nav':nav,'ops_cards':summary(request.user),'quality_cards':quality_cards(request),'duplicate_choices':duplicate_choices(request.user)}
    return render(request,'admin/operations/dashboard.html',context)


def value_at(obj, field):
    for name in field.split('__'):
        obj=getattr(obj,name,None)
        if obj is None:return ''
    return obj


def filtered_records(request, kind):
    model,label,fields,search=RECORDS[kind]
    if not can_view(request.user,model):raise PermissionDenied
    qs=queryset_for(request,model)
    if kind in RELATED:qs=qs.select_related(*RELATED[kind])
    form=RecordFilters(request.GET or None,kind=kind)
    data={}
    if form.is_bound:
        if not form.is_valid():return qs.none(),form
        data=form.cleaned_data
    qs=search_records(qs,data.get('q',''),search)
    status=data.get('status');today=timezone.localdate()
    if kind in ('employers','candidates'):
        if status=='pending':qs=qs.filter(is_approved=False,login_active=True)
        elif status=='approved':qs=qs.filter(is_approved=True,login_active=True)
        elif status=='disabled':qs=qs.filter(login_active=False)
    elif kind=='jobs':
        if status=='active':qs=qs.filter(is_active=True).filter(Q(expiry_date__isnull=True)|Q(expiry_date__gte=today))
        elif status=='inactive':qs=qs.filter(is_active=False)
        elif status=='expired':qs=qs.filter(expiry_date__lt=today)
    elif kind=='billing' and status:qs=qs.filter(status=status)
    elif kind=='alerts' and status:qs=qs.filter(active=status=='active')
    elif kind=='packages':
        if status=='available':qs=qs.filter(credits_remaining__gt=0).filter(Q(expires_at__isnull=True)|Q(expires_at__gte=timezone.now()))
        elif status=='expired':qs=qs.filter(expires_at__lt=timezone.now(),credits_remaining__gt=0)
        elif status=='exhausted':qs=qs.filter(credits_remaining=0)
    if kind=='employers':
        quality=data.get('quality')
        if quality=='missing-logo':qs=qs.filter(Q(logo='')|Q(logo__isnull=True))
        elif quality=='missing-description':qs=qs.annotate(_a=Trim('company_description'),_b=Trim('description')).filter(Q(_a='')|Q(_a__isnull=True)).filter(Q(_b='')|Q(_b__isnull=True))
        elif quality=='missing-email':qs=incomplete(qs,'email')
        elif quality=='missing-location':qs=incomplete(qs,'location')
    field=DATES.get(kind,'created_at')
    for key,op in [('start','gte'),('end','lt')]:
        value=data.get(key)
        if value:
            if field=='posting_date':qs=qs.filter(**{field+('__gte' if key=='start' else '__lte'):value})
            else:
                if key=='end':value+=timedelta(days=1)
                boundary=timezone.make_aware(datetime.combine(value,time.min))
                qs=qs.filter(**{field+'__'+op:boundary})
    return qs,form


def params(request, **updates):
    values={key:request.GET[key] for key in ('q','status','quality','start','end','sort','kind') if request.GET.get(key)}
    values.update(updates)
    return urlencode(values)


def records(request,kind):
    if kind not in RECORDS:raise Http404
    model,label,fields,search=RECORDS[kind]
    qs,form=filtered_records(request,kind)
    sort=request.GET.get('sort','-id')
    if sort not in set(fields)|{'-'+f for f in fields}:sort='-id'
    qs=qs.order_by(sort,'-pk')
    if request.GET.get('export')=='csv':
        if form.errors:return HttpResponse('Correct the filters before exporting.',status=400,content_type='text/plain')
        response=HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition']=f'attachment; filename="pt-jobs-{kind}.csv"'
        response.write('\ufeff');writer=csv.writer(response);writer.writerow(fields)
        for obj in qs.iterator(chunk_size=500):
            values=[]
            for field in fields:
                value=str(value_at(obj,field))
                if value.lstrip().startswith(('=','+','-','@')):value="'"+value
                values.append(value)
            writer.writerow(values)
        return response
    page=Paginator(qs,30).get_page(request.GET.get('page'));rows=[]
    for obj in page:
        values=[]
        for field in fields:
            value=value_at(obj,field)
            if field=='amount':value=f'{obj.currency} {Decimal(value)/100:,.2f}'
            elif isinstance(value,bool):value='Yes' if value else 'No'
            elif isinstance(value,datetime):value=timezone.localtime(value).strftime('%b %d, %Y %H:%M')
            values.append(value)
        rows.append({'values':values,'url':record_url(request,obj),'id':obj.pk})
    headings=[{'label':LABELS.get(field,field),'query':params(request,sort=('-' if sort==field else '')+field)} for field in fields]
    context={**admin.site.each_context(request),'title':label,'kind':kind,'ops_nav':navigation(request.user),'rows':rows,'headings':headings,'page_obj':page,'filter_form':form,'model_list_url':reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist'),'previous_query':params(request,page=page.previous_page_number()) if page.has_previous() else '', 'next_query':params(request,page=page.next_page_number()) if page.has_next() else ''}
    return render(request,'admin/operations/records.html',context)


def global_search(request):
    query=(request.GET.get('q') or '').strip()[:200];sections=[]
    if query:
        for key,(model,label,fields,search) in RECORDS.items():
            if not can_view(request.user,model):continue
            qs=search_records(queryset_for(request,model),query,search).order_by('-pk')
            if key in RELATED:qs=qs.select_related(*RELATED[key])
            count=qs.count()
            if not count:continue
            hits=[]
            for obj in qs[:6]:
                if key=='employers':title=obj.company_name or obj.email or f'Employer #{obj.pk}';detail=f'{obj.email or ""} · {obj.location}'
                elif key=='candidates':title=obj.full_name or obj.email or f'Job seeker #{obj.pk}';detail=f'{obj.email or ""} · {obj.current_location}'
                elif key=='jobs':title=obj.title;detail=obj.location
                else:title=str(obj);detail=f'Record #{obj.pk}'
                hits.append({'title':title,'detail':detail,'url':record_url(request,obj),'id':obj.pk})
            sections.append({'title':label,'count':count,'hits':hits,'url':reverse('admin:operations_records',args=[key])+'?'+urlencode({'q':query})})
    context={**admin.site.each_context(request),'title':'Search records','ops_nav':navigation(request.user),'query':query,'sections':sections}
    return render(request,'admin/operations/search.html',context)


def duplicate_queryset(request, key):
    label,model,kind,field=DUPLICATES[key]
    qs=queryset_for(request,model)
    if field=='domain':
        qs=qs.annotate(_email=Lower(Trim('email'))).annotate(_at=StrIndex('_email',Value('@'))).filter(_at__gt=1)
        qs=qs.annotate(_key=Substr('_email',F('_at')+1)).exclude(_key__in=PUBLIC_DOMAINS).filter(_key__contains='.')
    elif kind=='billing':qs=qs.annotate(_key=Trim(field))
    else:qs=qs.annotate(_key=Lower(Trim(field)))
    if kind=='jobs':qs=qs.annotate(_place=Lower(Trim('location')))
    return qs.exclude(_key='').exclude(_key__isnull=True)


def duplicates(request):
    choices=duplicate_choices(request.user)
    if not choices:raise PermissionDenied
    key=request.GET.get('kind') or choices[0]['key']
    if key not in DUPLICATES:raise Http404
    label,model,kind,field=DUPLICATES[key]
    if not can_view(request.user,model):raise PermissionDenied
    qs=duplicate_queryset(request,key)
    # Reference strings belong to their payment processor; never combine Stripe/PayPal.
    grouping=['_key','processor'] if kind=='billing' else ['_key','employer_id','_place'] if kind=='jobs' else ['_key']
    grouped=qs.order_by().values(*grouping).annotate(total=Count('pk')).filter(total__gt=1).order_by('-total','_key')
    query=(request.GET.get('q') or '').strip()[:200]
    if query:grouped=grouped.filter(_key__icontains=query)
    page=Paginator(grouped,15).get_page(request.GET.get('page'));groups=[]
    for group in page:
        members=qs.filter(_key=group['_key']).order_by('pk')
        if kind=='billing':members=members.filter(processor=group['processor']).select_related('employer')
        elif kind=='jobs':members=members.filter(employer_id=group['employer_id'],_place=group['_place']).select_related('employer')
        items=[]
        for obj in members[:30]:
            if kind=='employers':title=obj.company_name or obj.email or 'Unnamed employer';detail=f'{obj.email or "No email"} · {obj.location or "No location"}';state='Approved' if obj.is_approved else 'Pending approval'
            elif kind=='candidates':title=obj.full_name or obj.email or 'Unnamed job seeker';detail=f'{obj.email or "No email"} · {obj.current_location or "No location"}';state='Approved' if obj.is_approved else 'Pending approval'
            elif kind=='jobs':
                title=obj.title;detail=f'{obj.employer.company_name} · {obj.location} · Posted {obj.posting_date}';state='Expired' if obj.is_expired else 'Active' if obj.is_active else 'Inactive / draft'
            else:title=f'Invoice #{obj.pk} · {obj.amount_display} {obj.currency}';detail=str(obj.employer);state=obj.get_status_display()
            items.append({'id':obj.pk,'title':title,'detail':detail,'state':state,'url':record_url(request,obj)})
        groups.append({'key':group['_key'],'count':group['total'],'processor':group.get('processor'),'members':items,'truncated':group['total']>30})
    context={**admin.site.each_context(request),'title':'Duplicate review','ops_nav':navigation(request.user),'duplicate_choices':choices,'selected_kind':key,'groups':groups,'page_obj':page,'query':query,'previous_query':params(request,kind=key,page=page.previous_page_number()) if page.has_previous() else '', 'next_query':params(request,kind=key,page=page.next_page_number()) if page.has_next() else ''}
    return render(request,'admin/operations/duplicates.html',context)


def install_operations_urls():
    if getattr(admin.site,'_pt_operations_installed',False):return
    original=admin.site.get_urls
    def get_urls():
        return [
            path('operations/',admin.site.admin_view(workspace),name='operations'),
            path('operations/search/',admin.site.admin_view(global_search),name='operations_search'),
            path('operations/duplicates/',admin.site.admin_view(duplicates),name='operations_duplicates'),
            path('operations/<slug:kind>/',admin.site.admin_view(records),name='operations_records'),
        ]+original()
    admin.site.get_urls=get_urls
    admin.site._pt_operations_installed=True
