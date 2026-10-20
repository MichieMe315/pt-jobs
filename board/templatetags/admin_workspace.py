from django import template
from django.contrib import admin

register = template.Library()

@register.inclusion_tag("admin/workspace/navigation.html", takes_context=True)
def workspace_navigation(context):
    request = context["request"]
    groups = []
    definitions = [
        ("Job board", ["job", "employer", "jobseeker", "resume", "application", "jobalert", "jobalertdelivery"]),
        ("Billing & credits", ["invoice", "postingpackage", "purchasedpackage"]),
        ("Website & communication", ["sitesettings"]),
    ]
    apps = admin.site.get_app_list(request)
    models = {m["object_name"].lower(): m for app in apps if app["app_label"] == "board" for m in app["models"]}
    used = set()
    labels = {"job": "Job postings", "employer": "Employer profiles", "jobseeker": "Job seeker profiles", "jobalert": "Job alerts", "jobalertdelivery": "Alert deliveries", "postingpackage": "Posting packages", "purchasedpackage": "Purchased credits", "sitesettings": "Website settings"}
    for title, names in definitions:
        items = []
        for name in names:
            model = models.get(name)
            if model and (model.get("admin_url") or model.get("add_url")):
                url = model.get("admin_url") or model["add_url"]
                items.append({"label": labels.get(name, model["name"]), "url": url, "active": request.path.startswith(url)})
                used.add(name)
        if items:
            groups.append({"title": title, "items": items})
    for app in apps:
        items = []
        for model in app["models"]:
            if app["app_label"] == "board" and model["object_name"].lower() in used:
                continue
            url = model.get("admin_url") or model.get("add_url")
            if url:
                items.append({"label": model["name"], "url": url, "active": request.path.startswith(url)})
        if items:
            groups.append({"title": "Other controls" if app["app_label"] == "board" else app["name"], "items": items})
    return {"workspace_groups": groups, "request": request, "perms": context.get("perms"), "user": request.user}

@register.inclusion_tag('admin/workspace/activity.html', takes_context=True)
def workspace_activity(context):
    from board.models import Job, Employer
    from board.operations import can_view, quality_cards
    request = context['request']
    jobs = Job.objects.select_related('employer').order_by('-created_at', '-pk')[:8] if can_view(request.user, Job) else []
    employers = Employer.objects.order_by('-created_at', '-pk')[:6] if can_view(request.user, Employer) else []
    return {'recent_jobs': jobs, 'recent_employers': employers, 'quality_cards': quality_cards(request), 'can_view_jobs': can_view(request.user, Job), 'can_view_employers': can_view(request.user, Employer)}

@register.inclusion_tag('admin/workspace/dashboard.html', takes_context=True)
def workspace_dashboard(context):
    from datetime import timedelta
    from decimal import Decimal
    from django.db.models import Q, Sum, Count
    from django.urls import reverse
    from django.utils import timezone
    from board.models import Employer, JobSeeker, Job, Application, Invoice
    from board.operations import can_view, quality_cards, navigation
    user=context['request'].user
    today=timezone.localdate(); since=today-timedelta(days=29)
    live=Q(is_active=True)&(Q(expiry_date__gte=today)|Q(expiry_date__isnull=True))
    daily=[]; metrics=[]; secondary=[]; attention=[]
    def records(kind, suffix=''):
        return reverse('admin:operations_records',args=[kind])+suffix
    for model,label in [(Employer,'New employers'),(JobSeeker,'New job seekers')]:
        if can_view(user,model):daily.append({'label':label,'value':model.objects.filter(created_at__date=today).count()})
    if can_view(user,Job):
        daily.extend([{'label':'Active postings dated today','value':Job.objects.filter(live,posting_date=today).count()},{'label':'New inactive jobs','value':Job.objects.filter(is_active=False,created_at__date=today).count()}])
        metrics.append({'kicker':'LIVE JOB BOARD','label':'Active jobs','value':Job.objects.filter(live).count(),'url':records('jobs','?status=active')})
        secondary.append({'label':'Jobs expiring · 7 days','value':Job.objects.filter(is_active=True,expiry_date__gte=today,expiry_date__lte=today+timedelta(days=7)).count()})
        attention.append({'label':'Expired jobs still active','value':Job.objects.filter(is_active=True,expiry_date__lt=today).count(),'url':records('jobs','?status=expired')})
    if can_view(user,Employer):metrics.append({'kicker':'ACCOUNTS','label':'Approved employers','value':Employer.objects.filter(is_approved=True,login_active=True).count(),'url':records('employers','?status=approved')})
    for model,label,kind in [(Employer,'Employer approvals','employers'),(JobSeeker,'Job seeker approvals','candidates')]:
        if can_view(user,model):
            count=model.objects.filter(is_approved=False,login_active=True).count()
            item={'kicker':'NEEDS REVIEW','label':label,'value':count,'url':records(kind,'?status=pending')}
            metrics.append(item);attention.append(item)
            secondary.append({'label':('New employers' if model is Employer else 'New job seekers')+' · 30 days','value':model.objects.filter(created_at__date__gte=since).count()})
    if can_view(user,Application):
        daily.append({'label':'Applications','value':Application.objects.filter(created_at__date=today).count()})
        metrics.append({'kicker':'LAST 30 DAYS','label':'Applications','value':Application.objects.filter(created_at__date__gte=since).count(),'url':records('applications','?start='+since.isoformat())})
    if can_view(user,Invoice):
        paid=Invoice.objects.filter(status='paid',currency='CAD')
        def money(qs):return '${:,.2f}'.format(Decimal(qs.aggregate(total=Sum('amount'))['total'] or 0)/100)
        daily.append({'label':'Paid sales · CAD','value':money(paid.filter(order_date__date=today))})
        metrics.append({'kicker':'LAST 30 DAYS','label':'Revenue · CAD','value':money(paid.filter(order_date__date__gte=since)),'url':records('billing','?status=paid&start='+since.isoformat())})
        secondary.append({'label':'Failed payments · 30 days','value':Invoice.objects.filter(status='failed',order_date__date__gte=since).count()})
    attention.extend(quality_cards(context['request']))
    return {'today':today,'daily':daily,'metrics':metrics,'secondary':secondary,'attention':attention,'quick_links':navigation(user),'perms':context.get('perms'),
        'recent_jobs':Job.objects.select_related('employer').annotate(application_total=Count('applications')).order_by('-posting_date','-pk')[:8] if can_view(user,Job) else None,
        'recent_orders':Invoice.objects.select_related('employer').order_by('-order_date','-pk')[:6] if can_view(user,Invoice) else None,
        'recent_applications':Application.objects.select_related('job','job__employer','jobseeker').order_by('-created_at','-pk')[:6] if can_view(user,Application) else None}
