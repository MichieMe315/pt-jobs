from django import template

register = template.Library()

def admin_sections(request):
    from django.apps import apps
    from django.urls import reverse
    from board.admin_workspaces import visible_workspaces
    from board.operations import can_view

    def allowed(model):
        return can_view(request.user, apps.get_model(model))

    def link(label, route, *args):
        url = reverse(route, args=args)
        return {"label": label, "url": url, "current": request.path == url or
                (route != "admin:index" and request.path.startswith(url))}

    spaces = {space["key"]: space for space in visible_workspaces(request.user)}
    sections = [link("Dashboard", "admin:index")]
    if allowed("board.Employer") or allowed("board.JobSeeker"):
        sections.append(link("Review accounts", "admin:profile_review_queue"))
    jobs = [
        link(label, f"admin:board_{model.lower()}_changelist")
        for label, model in (
            ("Job Postings", "Job"), ("Employer Profiles", "Employer"),
            ("Resumes", "Resume"), ("Job Seeker Profiles", "JobSeeker"),
            ("Applications", "Application"), ("Job Alerts", "JobAlert"),
        ) if allowed(f"board.{model}")
    ]
    if jobs:
        sections.append({"label": "Job Board", "children": jobs,
                         "current": any(job["current"] for job in jobs)})
    if allowed("board.SiteSettings"):
        sections.append(link("Appearance", "admin:board_sitesettings_changelist"))
    if allowed("board.WebsitePage"):
        sections.append(link("Content", "admin:board_websitepage_changelist"))
    if "billing" in spaces:
        sections.append(link("eCommerce", "admin:task_workspace", "billing"))
    if "shop" in spaces:
        sections.append(link("Digital products", "admin:task_workspace", "shop"))
    if allowed("ptjc_resumes.ResumeTemplate"):
        sections.append(link("Résumé builders", "admin:ptjc_resumes_resumetemplate_changelist"))
    if "posting-packages" in spaces:
        sections.append(link("Job posting packages", "admin:task_workspace", "posting-packages"))
    if any(allowed(f"board.{model}") for model in ("Invoice", "Job", "Application", "Employer", "JobSeeker", "JobAlert")):
        sections.append(link("Reports", "admin_dashboard"))
    if any(allowed(f"board.{model}") for model in ("Employer", "Job", "JobSeeker")):
        sections.append(link("Import & Export", "admin:data_tools"))
    if "listing-fields" in spaces:
        sections.append(link("Listing Fields", "admin:task_workspace", "listing-fields"))
    if allowed("board.CandidateCampaign"):
        sections.append(link("Email Marketing", "admin:board_candidatecampaign_changelist"))
    elif request.user.has_perm("board.view_employer"):
        sections.append(link("Email Marketing", "admin:marketing_contacts"))
    if "affiliates" in spaces:
        sections.append(link("Affiliates", "admin:task_workspace", "affiliates"))
    if allowed("board.EmailDeliveryLog"):
        sections.append(link("Email Logs", "admin:board_emaildeliverylog_changelist"))
    if allowed("board.EmailTemplate"):
        sections.append(link("Email Templates", "admin:board_emailtemplate_changelist"))
    if any(allowed(f"board.{model}") for model in ("SiteSettings", "PaymentGatewayConfig", "SocialPostingConfig", "WebhookConfig")):
        sections.append(link("Settings", "admin:task_workspace", "settings"))
    if "career-tools" in spaces:
        sections.append(link("Career tools", "admin:task_workspace", "career-tools"))
    if "international" in spaces:
        sections.append(link("International", "admin:task_workspace", "international"))
    accounts = []
    if request.user.has_perm("auth.view_user") or request.user.has_perm("auth.change_user"):
        accounts.append(link("Users and staff access", "admin:auth_user_changelist"))
        if request.user.is_superuser:
            account_url = accounts[-1]["url"]
            filtered = request.path == account_url and request.GET.get("is_superuser__exact") == "1"
            if filtered:
                accounts[-1]["current"] = False
            accounts.append({"label": "Superusers", "url": account_url + "?is_superuser__exact=1", "current": filtered})
    if request.user.has_perm("auth.view_group") or request.user.has_perm("auth.change_group"):
        accounts.append(link("Permission groups", "admin:auth_group_changelist"))
    if accounts:
        sections.append({"label": "Administration", "children": accounts,
                         "current": any(item.get("current") for item in accounts)})
    advanced = link("Advanced", "admin:task_advanced")
    if request.path.startswith(reverse("admin:operations")):
        advanced["current"] = True
    sections.append(advanced)
    return sections


@register.inclusion_tag("admin/workspace/navigation.html", takes_context=True)
def workspace_navigation(context):
    return {"sections": admin_sections(context["request"])}


@register.inclusion_tag("admin/workspace/task_links.html", takes_context=True)
def workspace_task_links(context):
    from board.admin_workspaces import visible_workspaces
    return {"task_spaces":list(visible_workspaces(context['request'].user))}


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
    from board.operations import can_view, quality_cards
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
        metrics.append({'kicker':'LIVE JOB BOARD','label':'Active jobs','value':Job.objects.filter(live).count(),'url':reverse('admin:board_job_changelist')+'?posting_status=active'})
        secondary.append({'label':'Jobs expiring · 7 days','value':Job.objects.filter(is_active=True,expiry_date__gte=today,expiry_date__lte=today+timedelta(days=7)).count()})
        attention.append({'label':'Expired jobs still active','value':Job.objects.filter(is_active=True,expiry_date__lt=today).count(),'url':reverse('admin:board_job_changelist')+'?posting_status=expired&is_active__exact=1'})
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
        paid_today = paid.filter(order_date__date=today)
        paid_recent = paid.filter(order_date__date__gte=since)
        def order_count(qs):
            count = qs.count()
            return f'{count} paid order' + ('' if count == 1 else 's')
        daily.append({'label':'Paid sales · CAD','value':money(paid_today),'detail':order_count(paid_today)})
        metrics.append({'kicker':'LAST 30 DAYS','label':'Revenue · CAD','value':money(paid_recent),'detail':order_count(paid_recent),'url':records('billing','?status=paid&start='+since.isoformat())})
        secondary.append({'label':'Failed payments · 30 days','value':Invoice.objects.filter(status='failed',order_date__date__gte=since).count()})
    attention.extend(quality_cards(context['request']))
    from career_mobility.models import CalculatorUsageEvent
    sections = {item['label']: item for section in admin_sections(context['request'])
                for item in section.get('children', [section])}
    quick_links = [sections[label] for label in (
        'Employer Profiles', 'Job Seeker Profiles', 'Resumes', 'Job Postings', 'Applications',
        'Job Alerts', 'eCommerce', 'Digital products', 'Résumé builders', 'International',
    ) if label in sections]
    quick_links.append({'label': 'All administration', 'url': '#admin-directory'})
    if can_view(user, CalculatorUsageEvent):
        from django.urls import NoReverseMatch
        try:
            quick_links.append({'label': 'Calculator usage', 'url': reverse('calculator_usage_report')})
        except NoReverseMatch:
            pass
    return {'today':today,'daily':daily,'metrics':metrics,'secondary':secondary,'attention':attention,'quick_links':quick_links,'perms':context.get('perms'),
        'recent_jobs':Job.objects.select_related('employer').annotate(application_total=Count('applications')).order_by('-posting_date','-pk')[:8] if can_view(user,Job) else None,
        'recent_orders':Invoice.objects.select_related('employer').order_by('-order_date','-pk')[:6] if can_view(user,Invoice) else None,
        'recent_applications':Application.objects.select_related('job','job__employer','jobseeker').order_by('-created_at','-pk')[:6] if can_view(user,Application) else None}
