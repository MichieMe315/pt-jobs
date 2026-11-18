"""Task-oriented administration over the existing permission-checked workflows."""
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.apps import apps

# (label, description, model whose permission is required, route, arguments, query)
WORKSPACES = {
 'people': ('People','Review accounts, approvals and candidate records.', [
  ('Employer approvals','Open the queue of employers waiting for approval.','board.Employer','admin:profile_review_queue',(),'?kind=employers'),
  ('Job seeker approvals','Open the queue of job seekers waiting for approval.','board.JobSeeker','admin:profile_review_queue',(),'?kind=candidates'),
  ('Employers','Search, filter and export employer records.','board.Employer','admin:operations_records',('employers',),''),
  ('Job seekers','Search, filter and export job seeker records.','board.JobSeeker','admin:operations_records',('candidates',),''),
  ('Uploaded résumés','Find candidate résumés and open the associated records.','board.Resume','admin:operations_records',('resumes',),''),
 ]),
 'jobs': ('Job postings & applications','Manage postings and see what candidates have applied for.', [
  ('Job postings','Open postings to edit, duplicate or review publication details.','board.Job','admin:operations_records',('jobs',),''),
  ('Applications','Search and export application activity.','board.Application','admin:operations_records',('applications',),''),
  ('Job alerts','Review subscriptions and alert searches.','board.JobAlert','admin:operations_records',('alerts',),''),
  ('Paid job publication','Review payment-linked job publication records.','board.Invoice','paid_postings_report',(),''),
 ]),
 'shop': ('Digital products','Manage Canadian job seeker and International storefronts.', [
  ('Canadian storefront','Manage job seeker products and shared editors.','career_mobility.DigitalProduct','admin:career_mobility_digitalproduct_catalogue',(),'?audience=canadian'),
  ('International storefront','Manage International products and shared editors.','career_mobility.DigitalProduct','admin:career_mobility_digitalproduct_catalogue',(),'?audience=international'),
  ('Online listings','Edit the titles, descriptions and visibility of online editors.','career_mobility.StorefrontStudio','admin:career_mobility_storefrontstudio_changelist',(),''),
  ('Journal editions','Edit worksheet content and design defaults.','career_mobility.JournalTemplate','admin:career_mobility_journaltemplate_changelist',(),''),
  ('Discounts and promotions','Manage product discounts and promotional codes.','career_mobility.StoreDiscount','admin:career_mobility_storediscount_changelist',(),''),
  ('Complimentary access','Grant products and bundles to an account.','career_mobility.StoreGrant','admin:career_mobility_storegrant_changelist',(),''),
  ('Duplicate products','Compare products with matching titles or attached files.','career_mobility.DigitalProduct','admin:career_mobility_digitalproduct_duplicates',(),''),
  ('Résumé products','Manage templates and their linked purchase options.','ptjc_resumes.ResumeTemplate','admin:ptjc_resumes_resumetemplate_changelist',(),''),
 ]),
 'posting-packages': ('Job posting packages','Manage employer posting packages and employer discounts.', [
  ('Job posting packages','Edit the packages employers can purchase.','board.PostingPackage','admin:board_postingpackage_changelist',(),''),
  ('Job posting discount codes','Manage discounts for employer job postings.','board.DiscountCode','admin:board_discountcode_changelist',(),''),
 ]),
 'billing': ('eCommerce','Review employer invoices, packages and balances.', [
  ('Digital orders','Review purchases and payment status.','career_mobility.ProductOrder','admin:career_mobility_productorder_changelist',(),''),
  ('Paid job publication','Review payment-linked job publication records.','board.Invoice','paid_postings_report',(),''),
  ('Invoices','Find invoices by employer, date or payment reference.','board.Invoice','admin:operations_records',('billing',),''),
  ('Purchased packages','Check employers’ remaining credits and expiry dates.','board.PurchasedPackage','admin:operations_records',('packages',),''),
  ('Digital checkout status','Check configuration for digital product payments.','career_mobility.ProductOrder','digital_checkout_status',(),''),
 ]),
 'listing-fields': ('Listing Fields','Add and order signup questions. Core account fields remain unchanged.', [
  ('Employer signup questions','Edit questions shown on employer registration.','board.SignupQuestion','admin:board_signupquestion_changelist',(),'?audience__exact=employer'),
  ('Job seeker signup questions','Edit questions shown on job seeker registration.','board.SignupQuestion','admin:board_signupquestion_changelist',(),'?audience__exact=jobseeker'),
  ('Signup answers','Review answers already submitted by applicants.','board.SignupAnswer','admin:board_signupanswer_changelist',(),''),
 ]),
 'affiliates': ('Affiliates','Review partner applications, referrals, commissions and recorded payouts.', [
  ('Program settings','Enable applications and set terms and the default commission rate.','board.AffiliateProgram','admin:board_affiliateprogram_changelist',(),''),
  ('Partner applications','Review and approve pending partners.','board.AffiliatePartner','admin:board_affiliatepartner_changelist',(),'?status__exact=pending'),
  ('Approved partners','View referral codes and partner rates.','board.AffiliatePartner','admin:board_affiliatepartner_changelist',(),'?status__exact=approved'),
  ('Referrals','Review employer accounts attributed to a partner.','board.AffiliateReferral','admin:board_affiliatereferral_changelist',(),''),
  ('Commissions and payouts','Record commissions from paid CAD invoices and reconcile external payments.','board.AffiliateCommission','admin:board_affiliatecommission_changelist',(),''),
 ]),
 'settings': ('Settings','Manage site defaults and integrations.', [
  ('Site settings','Edit posting defaults, contact information, branding and analytics.','board.SiteSettings','admin:board_sitesettings_changelist',(),''),
  ('Payment gateways','Review existing payment gateway settings.','board.PaymentGatewayConfig','admin:board_paymentgatewayconfig_changelist',(),''),
  ('Social posting','Manage social posting settings.','board.SocialPostingConfig','admin:board_socialpostingconfig_changelist',(),''),
  ('Webhooks','Manage job feed integrations.','board.WebhookConfig','admin:board_webhookconfig_changelist',(),''),
 ]),
 'career-tools': ('Career tools','Review usage of the Canadian career tools.', [
  ('Calculator usage','See how candidates use the salary calculator.','career_mobility.CalculatorUsageEvent','calculator_usage_report',(),''),
 ]),
 'international': ('International','Manage the International portal.', [
  ('International profiles','Review candidates and their registration pathway information.','career_mobility.InternationalProfile','admin:career_mobility_internationalprofile_changelist',(),''),
  ('Planner and account activity','Search planner visits, countries, signups and downloads.','career_mobility.InternationalActivity','admin:career_mobility_internationalactivity_changelist',(),''),
  ('Country sponsorships','Publish sponsor placements by country.','career_mobility.InternationalSponsor','admin:career_mobility_internationalsponsor_changelist',(),''),
  ('Résumé and planner ads','Manage the advertising placement for the editors and planner.','ptjc_resumes.ResumeAdPlacement','admin:ptjc_resumes_resumeadplacement_changelist',(),''),
  ('Country resources','Manage the resources associated with each country.','career_mobility.CountryResourceCollection','admin:career_mobility_countryresourcecollection_changelist',(),''),
  ('Source reviews','Review updates before publishing reference data.','career_mobility.DataSourceReview','admin:career_mobility_datasourcereview_changelist',(),''),
 ]),
 'marketing': ('Marketing & website','Manage outreach, email templates and website settings.', [
  ('Candidate campaigns','Review audiences, draft and deliver candidate email.','board.CandidateCampaign','admin:board_candidatecampaign_changelist',(),''),
  ('Employer contacts','Search employers, organize audiences and prepare outreach.','board.Employer','admin:marketing_contacts',(),''),
  ('Email templates','Edit the templates used by site notifications.','board.EmailTemplate','admin:board_emailtemplate_changelist',(),''),
  ('Website settings','Manage branding, navigation settings and other site defaults.','board.SiteSettings','admin:board_sitesettings_changelist',(),''),
  ('Marketing graphics','Open the existing graphic generator.','board.Job','admin:marketing_generator',(),''),
 ]),
}


def visible_workspaces(user):
    from .operations import can_view
    from django.urls import NoReverseMatch
    for key,(title,description,definitions) in WORKSPACES.items():
        links=[]
        for label,help_text,model_label,route,args,query in definitions:
            try:
                model=apps.get_model(model_label)
                if not can_view(user, model):
                    continue
                if route=='paid_postings_report' and not (user.has_perm('board.view_employer') and user.has_perm('board.view_invoice')):
                    continue
                url=reverse(route,args=args)+query
            except (LookupError, NoReverseMatch):
                continue
            links.append({'label':label,'description':help_text,'url':url,'navigation':not query and route=='admin:operations_records'})
        if links:
            yield {'key':key,'title':title,'description':description,'links':links,
                   'url':reverse('admin:task_workspace',args=[key])}


def workspace(request, key):
    if key not in WORKSPACES:
        raise Http404
    space=next((row for row in visible_workspaces(request.user) if row['key']==key),None)
    if not space:
        raise PermissionDenied
    if key == 'international':
        from career_mobility.models import InternationalProfile, InternationalActivity
        from .operations import can_view, queryset_for, record_url
        from django.db.models import Count, F, Q
        from django.utils import timezone
        from datetime import timedelta

        counts, signups = None, None
        if can_view(request.user, InternationalProfile):
            profiles = queryset_for(request, InternationalProfile)
            verified = Q(email_verified_at__isnull=False) & (
                Q(email_verified_address='') | Q(email_verified_address__iexact=F('user__email'))
            )
            counts = profiles.aggregate(
                total=Count('pk'), verified=Count('pk', filter=verified),
                recent=Count('pk', filter=Q(created_at__gte=timezone.now() - timedelta(days=7))),
            )
            counts['unverified'] = counts['total'] - counts['verified']
            signups = [
                {'profile': profile, 'url': record_url(request, profile)}
                for profile in profiles.select_related('user').order_by('-created_at', '-pk')[:15]
            ]
        planner = None
        if can_view(request.user, InternationalActivity):
            days = request.GET.get('days', 'all')
            if days not in ('all', '7', '30', '90'):
                days = 'all'
            activity = InternationalActivity.objects.all()
            if days != 'all':
                activity = activity.filter(created_at__gte=timezone.now() - timedelta(days=int(days)))
            totals = activity.aggregate(
                views=Count('pk', filter=Q(action='planner_viewed')),
                plans=Count('pk', filter=Q(action='planner_generated')),
                guest_plans=Count('pk', filter=Q(action='planner_generated', profile__isnull=True)),
                signups=Count('pk', filter=Q(action='account_created')),
            )
            generated = activity.filter(action='planner_generated')
            countries = []
            for label, field in (
                ('Browsing country', 'visitor_country'),
                ('Country of education', 'education_country'),
                ('Destination province or territory', 'destination_province'),
            ):
                rows = generated.order_by().values(field).annotate(
                    total=Count('pk')).order_by('-total', field)[:10]
                countries.append({'label': label, 'rows': [
                    {'location': row[field] or 'Unknown', 'total': row['total']} for row in rows]})
            planner = {
                'days': days, 'totals': totals, 'countries': countries,
                'activity_url': reverse('admin:career_mobility_internationalactivity_changelist'),
                'recent': activity.select_related('profile__user').order_by('-created_at', '-pk')[:10],
            }
        return render(request, 'admin/workspace/international_dashboard.html', {
            **admin.site.each_context(request), 'title': 'International dashboard',
            'workspace': space, 'counts': counts, 'signups': signups, 'planner': planner,
        })
    queues=[]
    if key=='people':
        from .operations import can_view, queryset_for, record_url
        from .models import Employer, JobSeeker
        for model,title,kind in ((Employer,'Employers waiting for approval','employers'),(JobSeeker,'Job seekers waiting for approval','candidates')):
            if not can_view(request.user,model):
                continue
            records=queryset_for(request,model).filter(is_approved=False).order_by('-created_at','-pk')
            queues.append({'title':title,'count':records.count(),'url':reverse('admin:profile_review_queue')+'?kind='+kind,
                'rows':[{'name':str(obj),'url':record_url(request,obj),'date':obj.created_at} for obj in records[:6]]})
    groups = []
    if key == 'shop':
        from career_mobility.models import DigitalProduct
        from career_mobility.shop_studios import storefront_products
        from career_mobility.views import shop_context
        from .operations import can_view, queryset_for

        storefronts = []
        live_by_id = {}
        search = request.GET.get('q', '').strip()[:100]
        state = request.GET.get('status', 'live')
        if state not in ('live', 'draft', 'all'):
            state = 'live'
        product_page = None
        if can_view(request.user, DigitalProduct):
            products = queryset_for(request, DigitalProduct)
            catalogue = reverse('admin:career_mobility_digitalproduct_catalogue')
            for audience, label in (('canadian', 'Canadian job seekers'), ('international', 'International candidates')):
                live = shop_context(request, audience, catalogue=True)
                rows = []
                listings = ([{'studio': live['featured_resume']}] if live['featured_resume'] else []) + live['listings']
                for listing in listings:
                    studio = listing.get('studio') or {}
                    product = listing.get('product') or studio.get('product')
                    if product:
                        live_by_id.setdefault(product.pk, []).append(label)
                    rows.append({
                        'title': product.title if product else studio['title'],
                        'edit': reverse('admin:career_mobility_digitalproduct_change', args=[product.pk]) if product else '',
                        'open': listing.get('editor_url') or studio.get('href'),
                    })
                storefronts.append({
                    'label': label,
                    'live': len(rows),
                    'rows': rows,
                    'preview': reverse('mobility_shop' if audience == 'canadian' else 'mobility_international_shop'),
                    'drafts': storefront_products(products, audience).filter(is_published=False).count(),
                    'url': f'{catalogue}?audience={audience}',
                })
            from django.core.paginator import Paginator
            from django.db.models import Q
            results = products.order_by('storefront_order', 'title', 'pk')
            if search:
                results = results.filter(Q(title__icontains=search) | Q(slug__icontains=search) | Q(category__icontains=search))
            if state == 'live':
                results = results.filter(pk__in=live_by_id)
            elif state == 'draft':
                results = results.filter(is_published=False)
            product_page = Paginator(results, 25).get_page(request.GET.get('page'))
            for product in product_page:
                product.live_in = live_by_id.get(product.pk, [])
        actions = {link['label']: link for link in space['links']}
        product_admin = admin.site.get_model_admin(DigitalProduct)
        from urllib.parse import urlencode
        filter_query = urlencode({'q': search, 'status': state})
        for title, labels in (
            ('Product settings', ('Online listings', 'Journal editions')),
            ('Discounts and access', ('Discounts and promotions', 'Complimentary access')),
            ('Maintenance', ('Duplicate products',)),
        ):
            links = [actions[label] for label in labels if label in actions]
            if links:
                groups.append({'title': title, 'links': links})
        return render(request, 'admin/workspace/digital_products.html', {
            **admin.site.each_context(request), 'title': space['title'],
            'storefronts': storefronts, 'groups': groups, 'resumes': actions.get('Résumé products'),
            'product_page': product_page, 'search': search, 'state': state, 'filter_query': filter_query,
            'can_add_product': product_admin.has_add_permission(request),
            'can_reorder': product_admin.has_change_permission(request),
            'discounts': actions.get('Discounts and promotions'),
        })
    return render(request,'admin/workspace/task_workspace.html',{
        **admin.site.each_context(request),'title':space['title'],'workspace':space,'queues':queues,'groups':groups,
    })


def advanced(request):
    return render(request,'admin/workspace/advanced.html',{
        **admin.site.each_context(request),'title':'Advanced admin','app_list':admin.site.get_app_list(request),
    })


def data_tools(request):
    from .models import Employer, Job, JobSeeker
    datasets = []
    for model, label in ((Job, 'Job Postings'), (Employer, 'Employer Profiles'), (JobSeeker, 'Job Seeker Profiles')):
        model_admin = admin.site.get_model_admin(model)
        prefix = f'admin:board_{model._meta.model_name}'
        if model_admin.has_view_permission(request) or model_admin.has_import_permission(request):
            datasets.append({
                'label': label,
                'import_url': reverse(prefix + '_import') if model_admin.has_import_permission(request) else '',
                'export_url': reverse(prefix + '_export') if model_admin.has_export_permission(request) else '',
            })
    if not datasets:
        raise PermissionDenied
    return render(request, 'admin/workspace/data_tools.html', {
        **admin.site.each_context(request), 'title': 'Import & Export', 'datasets': datasets,
    })
