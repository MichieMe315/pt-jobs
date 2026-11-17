from ptjc_resumes.ad_context import international_placement
from django.views.decorators.http import require_POST
from decimal import Decimal
from django.contrib.auth import login
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import render,redirect,get_object_or_404
from .forms import InternationalSignupForm
from .models import InternationalProfile,PathwayRule,ReferenceCost,DigitalProduct,ProductOrder

def home(request):
    return render(request,"career_mobility/home.html")

from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse

@staff_member_required
def shop_admin(request):
    from django.db.models import Sum
    latest_products = DigitalProduct.objects.order_by('-pk')[:8]
    recent_orders = ProductOrder.objects.select_related('user', 'product').order_by('-created_at')[:8]
    from django.core.exceptions import PermissionDenied
    if not request.user.has_perms(['career_mobility.view_digitalproduct','career_mobility.view_productorder']):raise PermissionDenied
    revenue = Decimal(ProductOrder.objects.filter(paid=True).aggregate(total=Sum('amount_cents'))['total'] or 0)/100
    from django.contrib import admin
    return render(request, 'career_mobility/shop_admin.html', {**admin.site.each_context(request),'title':'Career tools and shop',
        'latest_products': latest_products, 'recent_orders': recent_orders, 'revenue_estimate': revenue,
        'published': DigitalProduct.objects.filter(is_published=True).count(),
        'drafts': DigitalProduct.objects.filter(is_published=False).count(),
        'orders': ProductOrder.objects.count(),
        'sources_pending': __import__('career_mobility.models',fromlist=['DataSourceReview']).DataSourceReview.objects.filter(status='pending').count(),
        'fees_pending': __import__('career_mobility.models',fromlist=['ProvincialLicenceFee']).ProvincialLicenceFee.objects.filter(is_published=False).count(),
        'salary_regions': __import__('career_mobility.models',fromlist=['SalaryBenchmark']).SalaryBenchmark.objects.filter(is_published=True).count(),
        'international_profiles': InternationalProfile.objects.count(),
        'saved_plans': __import__('career_mobility.models',fromlist=['SavedCareerPlan']).SavedCareerPlan.objects.count(),
        'products_missing_files': DigitalProduct.objects.filter(kind='file',download='').exclude(resumetemplate__is_enabled=True).exclude(slug='international-business-card-builder-access').count(),
        'paid_orders': ProductOrder.objects.filter(paid=True).count(),
        'orders_missing_amount': ProductOrder.objects.filter(paid=True,amount_cents__isnull=True).count(),
    })

def shop(request, audience="canadian"):
    return render(request, 'career_mobility/shop.html', shop_context(request, audience))


def shop_context(request, audience="canadian", *, catalogue=False):
    """Public catalogue, shared by future resume/template and pathway products."""
    products = DigitalProduct.objects.filter(is_published=True).order_by('storefront_order','title')
    from .shop_studios import storefront_products
    products = storefront_products(products, audience)
    from .store_eligibility import account_type, account_requirement
    role = account_type(request.user)
    employer_shop = role == 'employer' and audience == 'canadian'

    def visible(product):
        return not ((employer_shop or (role and product.eligible_accounts)) and account_requirement(request.user, product))

    owned = set()
    if request.user.is_authenticated:
        from .store_access import owned_ids
        owned = owned_ids(request.user)
    query='' if catalogue else request.GET.get('q','').strip()[:100]
    category='' if catalogue else request.GET.get('category','')[:60]
    categories=list(products.exclude(category='').order_by('category').values_list('category',flat=True).distinct())
    if query:
        from django.db.models import Q
        products=products.filter(Q(title__icontains=query)|Q(short_description__icontains=query)|Q(description__icontains=query))
    if category:products=products.filter(category=category)
    from .editable_products import JOURNALS
    from .shop_studios import for_shop, linked_studio_products, published_journal_slugs
    from .shop_gallery import resource_link
    studios = list(for_shop(audience)) if not category else []
    linked = linked_studio_products()
    available = {p.pk: p for p in products.filter(pk__in=[p.pk for p in linked.values() if p])}
    disabled = {studio['key'] for studio in for_shop(audience, include_hidden=True) if not studio['visible']}
    represented = {p.pk for key, p in linked.items() if p and key in disabled}
    listings = []
    featured_resume = None
    for studio in studios:
        linked_product = linked.get(studio['key'])
        if employer_shop and 'resume' in studio['key']:
            continue
        if linked_product and not visible(linked_product):
            continue
        if not query and not category and studio['key'] == f'{audience}-resume':
            featured_resume = studio
            # Feature the public editor; paid access stays governed by the linked product.
            if linked_product and linked_product.pk in available:
                from .pricing import pricing_audience
                featured_resume = dict(studio, product=linked_product, price=linked_product.price_for(pricing_audience(request.user, linked_product, audience)))
                represented.add(linked_product.pk)
            continue
        # A draft or out-of-audience product cannot appear via its editor fallback.
        if linked_product and (
            not linked_product.is_published or linked_product.audience not in (audience, 'both')
        ):
            continue
        if (product := available.get(linked_product.pk if linked_product else None)) and product.pk not in represented:
            studio['product'] = product
            studio['title'] = product.title
            studio['description'] = product.short_description or product.description
            represented.add(product.pk)
            if studio['key'] == 'calendar':
                studio['href'] = resource_link(product, audience) or studio['href']
            position = product.storefront_order
        else:
            if linked_product:
                continue
            if query and query.casefold() not in ' '.join((studio['title'], studio['description'], studio['key'])).casefold():
                continue
            position = studio['position']
        listings.append((position, studio['title'].casefold(), {'studio': studio}))
    listings.extend(
        (p.storefront_order, p.title.casefold(), {'product': p, 'editor_url': url})
        for p in products.exclude(pk__in=represented)
        if visible(p) and (url := reverse('mobility_international') if p.kind == 'workbook' else resource_link(p, audience))
    )
    published_journals = published_journal_slugs(audience)
    if not published_journals:
        listings = [item for item in listings if item[2].get('studio', {}).get('key') != 'printables']
    listings.sort(key=lambda item: item[:2])
    # Consolidate identical builder links; product-specific editor URLs keep their
    # product slug, so separate designs and purchase options are not merged.
    from urllib.parse import parse_qsl, urlsplit

    def launch_key(url):
        if not url:
            return None
        parsed = urlsplit(url)
        return parsed.path, tuple(sorted((key, value) for key, value in parse_qsl(parsed.query) if key != 'audience'))

    seen = {}
    unique = []
    if featured_resume:
        seen[launch_key(featured_resume['href'])] = None
    for item in listings:
        row = item[2]
        studio = row.get('studio') or {}
        product = row.get('product') or studio.get('product')
        destination = launch_key(row.get('editor_url') or studio.get('href'))
        if not destination or (product and product.kind == 'workbook'):
            unique.append(item)
            continue
        if destination not in seen:
            seen[destination] = len(unique)
            unique.append(item)
        elif (index := seen[destination]) is not None and product:
            previous = unique[index][2]
            if not (previous.get('product') or (previous.get('studio') or {}).get('product')):
                unique[index] = item
    listings = sorted(unique, key=lambda item: item[:2])

    return {
        'journals': [(key, edition) for key, edition in JOURNALS.items() if 'ptjc-' + key in published_journals], 'listings': [item[2] for item in listings],
        'shop_audience': audience, 'featured_resume': featured_resume, 'owned_ids': owned, 'query': query, 'category': category,
        'categories': categories,
        'shop_base': 'career_mobility/standalone.html' if audience=='international' else 'career_mobility/base_tool.html',
    }


def international_landing(request):
    return international(request)


def international(request):
    from .countries import COUNTRIES
    from .planning import from_answers
    from .international_activity import record, record_planner_result
    from .country_content import get_country
    from urllib.parse import urlencode
    profile=getattr(request.user,'international_pt_profile',None)
    initial={'country':request.GET.get('country',profile.country_of_education if profile else ''),'province':request.GET.get('province',profile.destination_province if profile else ''),'applied':request.GET.get('applied',{'new':'not-applied','existing':'before','after':'after','unsure':'unsure'}.get(profile.application_history,'') if profile else ''),'registration':request.GET.get('registration',profile.registered_in_education_country if profile else '')}
    error=''
    if request.GET.get('build'):
        try:
            answers=from_answers(request.GET);country=get_country(answers.country_of_education)
            record_planner_result(request, 'planner_generated', answers)
            return redirect(reverse('mobility_country',args=[country['slug']])+'?'+urlencode({k:v for k,v in initial.items() if k!='country'}))
        except ValueError as exc:error=str(exc)
    if request.method == 'GET' and not error:
        record(request, 'planner_viewed')
    return render(request,'career_mobility/international.html',{'international_ad':international_placement(),'country_options':COUNTRIES,'provinces':__import__('career_mobility.forms',fromlist=['PROVINCES']).PROVINCES,'answers':initial,'error':error})

def signup(request):
    from django.utils.http import url_has_allowed_host_and_scheme
    next_url=request.POST.get('next') or request.GET.get('next','')
    if not url_has_allowed_host_and_scheme(next_url,allowed_hosts={request.get_host()},require_https=request.is_secure()):next_url=''

    if request.user.is_authenticated:
        if hasattr(request.user, "international_pt_profile"):
            return redirect(next_url or reverse("mobility_international_dashboard"))
        from django.contrib.auth import logout
        if request.method == "POST":
            return HttpResponseForbidden("Sign out of your existing account before creating a separate international PT account.")
        return render(request, "career_mobility/signup_account_conflict.html")
    initial=dict(request.session.get("international_pending",{}).get("answers",{}))
    for key in ("country_of_education","citizenship_country","destination_province","registered_in_education_country","application_history"):
        if key in request.GET:initial[key]=request.GET[key][:100]
    form=InternationalSignupForm(request.POST or None, initial=initial)
    if request.method=="POST" and form.is_valid():
        from urllib.parse import urlsplit
        with transaction.atomic():
            user=form.save()
            if urlsplit(next_url).path == reverse('ptjc_resumes:claim'):
                from ptjc_resumes.public import save_guest_to_account
                if save_guest_to_account(request, user):
                    next_url = ''
        login(request,user)
        from .planner_views import apply_pending
        apply_pending(request,user.international_pt_profile,update_answers=False)
        from .international_activity import record
        record(request,'account_created',profile=user.international_pt_profile,event_key=f'signup:{user.pk}')
        from .international_notifications import new_account_mail
        new_account_mail(request,user.international_pt_profile)
        from .email_verification import send_verification
        request.session["international_verified_next"]=next_url
        if not send_verification(request,user.international_pt_profile):
            messages.warning(request,"Your account is saved, but the verification email could not be sent. Try resending below or contact PTJC.")
        return redirect("mobility_verify_pending")
    from .forms import COUNTRIES
    from ptjc_resumes.offers import signup_pdf_price
    return render(request,"career_mobility/signup.html",{"form":form,"country_options":COUNTRIES,"next_url":next_url, "resume_signup_price":signup_pdf_price(next_url, "international")})

@login_required(login_url="mobility_international_login")
def dashboard(request):
    profile=getattr(request.user,"international_pt_profile",None)
    if profile is None: return HttpResponseForbidden("International PT account required.")
    from .international_activity import record
    record(request,'dashboard_viewed')
    return render(request,"career_mobility/dashboard.html",_dashboard_context(request,profile))

def _dashboard_context(request,profile,profile_form=None):
    products=DigitalProduct.objects.filter(is_published=True).order_by("title")
    completed=set(profile.checklist_items.filter(completed=True).values_list("key",flat=True))
    from .planning import build
    plan=build(profile)
    checklist=[dict(step,completed=step["key"] in completed) for step in plan["steps"]]
    fees=ProvincialLicenceFee.objects.filter(is_published=True,province=profile.destination_province).order_by("fee_type")
    rule=PathwayRule.objects.filter(country__iexact=profile.country_of_education,is_published=True).first()
    from .store_access import owned_ids
    paid_ids=owned_ids(request.user)
    from .forms import InternationalProfileUpdateForm
    profile_form = profile_form if profile_form is not None else InternationalProfileUpdateForm(instance=profile)
    completed_count = sum(step["completed"] for step in checklist)
    from .country_content import get_country
    country_guidance=get_country(profile.country_of_education)
    from .shop_gallery import resource_link
    owned_resources = [{'product': p, 'url': resource_link(p, 'international') if p.is_published else ''}
                       for p in DigitalProduct.objects.filter(pk__in=paid_ids)]
    available_resources = [
        {'product': product, 'url': url}
        for product in products.exclude(pk__in=paid_ids).filter(audience__in=('both', 'international'))
        if (url := resource_link(product, 'international'))
    ]
    return {"next_step":next((step for step in checklist if not step["completed"]),None),"plan":plan,"country_guidance":country_guidance,"profile":profile,"products":products,"checklist":checklist,"fees":fees,"rule":rule,"paid_ids":paid_ids,"owned_products":DigitalProduct.objects.filter(pk__in=paid_ids),"owned_resources":owned_resources,"available_resources":available_resources,"completed_count":completed_count,"total_count":len(checklist),"progress":round(100*completed_count/len(checklist)),"profile_form":profile_form,"salary_plans":SavedCareerPlan.objects.filter(user=request.user,plan_type="salary")[:5]}

def _canadian_context():
    costs=ReferenceCost.objects.filter(is_published=True).order_by("province","city","kind")
    rows={}
    citations={}
    for c in costs:
        key=f"{c.city}, {c.province}" if c.city else c.province
        if c.kind == "rent" and not c.reference_period:
            continue
        rows.setdefault(key,{})[c.kind]=str(c.amount_cad)
        citations.setdefault(key,{})[c.kind]={"url":c.source_url,"verified":c.verified_on.isoformat() if c.verified_on else "Unverified","period":c.reference_period,"basis":c.basis}
    database_keys={key for key,refs in citations.items() if "rent" in refs}
    fees=ProvincialLicenceFee.objects.filter(is_published=True).order_by("province","fee_type")
    from .research import research_context
    research = research_context()
    for item in research["locations"]:
        if item["rent"] is None:
            continue
        key = f'{item["city"]}, {item["province"]}'
        # Published database entries are retained; snapshots fill missing references only.
        rows.setdefault(key, {}).setdefault("rent", str(item["rent"]))
        citations.setdefault(key, {}).setdefault("rent", {"url":item["source_url"], "verified":item["verified_on"], "period":item["reference_period"], "basis":item["basis"]})
    from .research_library import rural_housing_references
    from .research_library import records,CODES
    for item in rural_housing_references():
        key=item['community']+', '+item['province']
        rows.setdefault(key,{}).setdefault('rent',str(item['amount']))
        citations.setdefault(key,{}).setdefault('rent',{'url':item['source'],'verified':'2026-10-20','period':item['period'],'basis':item['basis']})
    wages={}
    regional_wages=[]
    for wage in records('pt_wages_regional'):
        if wage['geography_level']=='province_or_territory' and wage.get('median_hourly_cad') is not None:
            wages[CODES[wage['province_code']]]={'hourly':wage['median_hourly_cad'],'period':wage['reference_period'],'source':wage['source_url'],'area':wage['source_area']}
    for wage in records('pt_wages_regional'):
        if wage['geography_level']=='economic_region':
            regional_wages.append({'province':CODES[wage['province_code']],'area':wage['source_area'],'hourly':wage.get('median_hourly_cad'),'period':wage.get('reference_period'),'source':wage['source_url'],'regional':True})
    from .models import SalaryBenchmark,DataSourceReview
    import json
    latest=DataSourceReview.objects.filter(status='approved',source__url='https://www.jobbank.gc.ca/wagereport/occupation/18214',detail__contains='"kind": "jobbank_pt_wages"').order_by('-reviewed_at').first()
    if latest:
        try:approved=json.loads(latest.detail).get('rows',[])
        except (ValueError,TypeError):approved=[]
        for row in approved:
            if row['region']==row['province']:
                if row.get('median_hourly') is None:wages.pop(row['province'],None)
            else:
                regional_wages=[r for r in regional_wages if (r['province'],r['area'])!=(row['province'],row['region'])]
                regional_wages.append({'province':row['province'],'area':row['region'],'hourly':row.get('median_hourly'),'period':row['reference_period'],'source':latest.source.url,'regional':True})
    for wage in SalaryBenchmark.objects.filter(is_published=True):
        if wage.region==wage.province and wage.median_hourly is not None:wages[wage.province]={'hourly':str(wage.median_hourly),'period':wage.reference_period,'source':wage.source_url,'area':wage.region}
        elif wage.median_hourly is not None:
            regional_wages=[r for r in regional_wages if (r['province'],r['area'])!=(wage.province,wage.region)]
            regional_wages.append({'province':wage.province,'area':wage.region,'hourly':str(wage.median_hourly),'period':wage.reference_period,'source':wage.source_url,'regional':True})
    # Resolve bare community names only when the province is unambiguous.
    directory=[{'city':x['city'],'province':x['province']} for x in research['locations']]
    directory += [{'city':x['community'],'province':x['province']} for x in rural_housing_references()]
    directory += [{'city':x['community'],'province':x['province_or_territory']} for x in records('priority_community_coverage')]
    from pathlib import Path
    import json
    geography=json.loads((Path(__file__).parent/'data/community_economic_regions_2021.json').read_text(encoding='utf-8'))
    directory += [{'city':r['city'],'province':r['province']} for r in geography['records']]
    update=json.loads((Path(__file__).parent/'data/community_updates_2026_10_28.json').read_text(encoding='utf-8'))
    for item in update:
        key=item['city']+', '+item['province']
        if key in database_keys:continue
        rows.setdefault(key,{})['rent']=str(item['rent'])
        citations.setdefault(key,{})['rent']={'url':item['source_url'],'verified':item['verified_on'],'period':item['reference_period'],'basis':item['basis']}
        directory.append({'city':item['city'],'province':item['province']})
    toronto_key = 'Toronto, Ontario'
    if toronto_key not in database_keys:
        rows.setdefault(toronto_key,{})['rent']='2034'
        citations.setdefault(toronto_key,{})['rent']={'url':'https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/market-reports/rental-market-reports-major-centres','verified':'2026-11-02','period':'2025','basis':'Greater Toronto Area · two-bedroom purpose-built apartment · average occupied rent'}
    return {"household_food_references":records("food_northern_communities_2026"),"community_geography":geography,"regional_wage_references":regional_wages,"community_directory":directory,"wage_references":wages,"rural_housing_references":rural_housing_references(),"costs":rows,"citations":citations,"fees":fees,"research":research}

def canadian(request):
    return render(request, "career_mobility/canadian_basic.html", _canadian_context())

@login_required
def relocation_comparisons(request):
    """Private, multi-destination planning workspace; never exposes other users' data."""
    if hasattr(request.user, "international_pt_profile") or not getattr(getattr(request.user, "jobseeker", None), "is_approved", False):
        return HttpResponseForbidden("A Canadian job seeker account is required.")
    from decimal import Decimal, InvalidOperation
    from .models import SavedCareerPlan
    plans = SavedCareerPlan.objects.filter(user=request.user, plan_type="relocation").order_by("-created_at")[:50]
    def num(value):
        try:
            n = Decimal(str(value))
            return n if n.is_finite() and n >= 0 and n <= Decimal("100000000") else None
        except (InvalidOperation, ValueError, TypeError):
            return None
    comparisons = []
    for plan in plans:
        data = plan.inputs if isinstance(plan.inputs, dict) else {}
        keys = ("current-salary", "new-salary", "current-rent", "new-rent", "current-living", "new-living")
        values = [num(data.get(key)) for key in keys]
        if data.get("expense_mode") == "itemized":
            for index, side in [(4, "current"), (5, "new")]:
                costs = [num(data.get(side+"-"+kind) or 0) for kind in ("utilities", "transport", "groceries", "childcare", "extra")]
                values[index] = sum(costs, Decimal(0)) if all(c is not None for c in costs) else None
        takehome = [num(data.get(key)) for key in ("current-net", "new-net")]
        income = takehome if all(n is not None for n in takehome) else [n/12 if n is not None else None for n in values[:2]]
        difference = None
        if all(x is not None for x in values):
            a, b, ar, br, al, bl = values
            difference = income[1]-income[0] - (br-ar) - (bl-al)
        comparisons.append({"plan": plan, "origin": str(data.get("origin") or "Not specified")[:90],
            "destination": str(data.get("destination") or "Not specified")[:90],
            "difference": difference, "new_salary": num(data.get("new-salary")),
            "new_rent": num(data.get("new-rent")), "new_living": values[5],
            "monthly_budget": (income[1]-values[3]-values[5]) if all(values[i] is not None for i in (1,3,5)) else None})
    valid = [row for row in comparisons if row["difference"] is not None]
    best = max(valid, key=lambda row: row["difference"]) if valid else None
    return render(request, "career_mobility/relocation_comparisons.html", {
        "comparisons": comparisons, "best": best, "scenario_count": len(comparisons),
        "complete_count": len(valid),
    })

@login_required
@require_POST
def rename_relocation_plan(request, pk):
    """Rename a candidate's own saved scenario; other candidates' plans remain inaccessible."""
    from .models import SavedCareerPlan
    if hasattr(request.user, "international_pt_profile") or not getattr(getattr(request.user, "jobseeker", None), "is_approved", False):
        return HttpResponseForbidden("A Canadian job seeker account is required.")
    plan = get_object_or_404(SavedCareerPlan, pk=pk, user=request.user, plan_type="relocation")
    title = " ".join(request.POST.get("title", "").split())[:120]
    if title:
        plan.title = title
        plan.save(update_fields=["title"])
    return redirect("mobility_relocation_comparisons")

@login_required
def canadian_full(request):
    if hasattr(request.user,"international_pt_profile") or not getattr(getattr(request.user,"jobseeker",None),"is_approved",False):
        return HttpResponseForbidden("Registered Canadian job seeker account required.")
    context = _canadian_context()
    if request.GET.get("saved"):
        try:saved_id=int(request.GET["saved"])
        except (ValueError,TypeError):raise Http404("Saved plan not found")
        plan = get_object_or_404(SavedCareerPlan, pk=saved_id, user=request.user, plan_type="relocation")
        context["saved_inputs"] = plan.inputs
    return render(request, "career_mobility/canadian.html", context)

@login_required
def resource_library(request):
    from .store_views import library
    return library(request)


@login_required
def product_download(request,pk):
    product=get_object_or_404(DigitalProduct,pk=pk)
    from .store_access import has_access
    from .starter import remaining, authorize
    from .product_activity import record as record_product
    if not has_access(request.user,product) and not remaining(request.user, product):
        return HttpResponseForbidden("Purchase required.")
    from .shop_gallery import editor_key, editor_link
    from .store_eligibility import account_type
    audience = 'international' if account_type(request.user) == 'international' else 'canadian'
    if editor_key(product) == 'appointment-card-designs':
        return redirect(editor_link(product, audience))
    if product.includes_card_builder:
        return redirect('ptjc_resumes:cards' if audience == 'international' else 'jobseeker_cards:cards')
    if product.kind=='workbook':return redirect('mobility_personalized_checklist')
    if product.kind=='bundle':return redirect('mobility_resource_library')
    if product.includes_resume_builder and not product.download:
        return redirect('ptjc_canadian_resumes:canadian_index' if product.audience == 'canadian' else 'ptjc_resumes:index')
    if not product.download: raise Http404()
    # Do not redirect to a public storage URL: protected downloads need private storage.
    from django.http import FileResponse
    from .print_palettes import variants
    palette = request.GET.get('palette')
    filename = product.download.name
    design = request.GET.get('design')
    if design and product.slug.removeprefix('ptjc-') == 'business-card-design-files':
        from .recovered_products import card_design_archive
        try:
            with product.download.storage.open(filename,'rb') as source:
                handle = card_design_archive(source, design)
        except (ValueError, OSError):
            raise Http404('That design is unavailable.')
        if not authorize(request.user, product, 1):
            handle.close()
            return HttpResponseForbidden("No starter downloads remain.")
        record_product(product, 'exported', request=request)
        response = FileResponse(handle, as_attachment=True, filename=f'business-card-{design}.zip')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    if palette:
        filename = variants(product.download).get(palette)
        if filename is None:
            raise Http404('This print palette is not available.')
    from .editable_products import TEMPLATES, configured_document
    key = filename.removeprefix("bundled/").removesuffix(".html")
    if filename == "bundled/" + key + ".html" and key in TEMPLATES:
        from io import BytesIO
        handle = BytesIO(configured_document(key).encode("utf-8"))
    else:
        try:handle=product.download.storage.open(filename,"rb")
        except (FileNotFoundError,OSError):raise Http404("This download is temporarily unavailable. Please contact PTJC.")
    if not authorize(request.user, product, 1):
        handle.close()
        return HttpResponseForbidden("No starter downloads remain.")
    response=FileResponse(handle,as_attachment=True,filename=filename.rsplit("/",1)[-1])
    from .product_activity import record
    record(product, 'exported', request=request)
    from .international_activity import record
    if hasattr(request.user,'international_pt_profile'):
        record(request,'product_downloaded',subject=product.slug)
    response["Cache-Control"]="private, no-store"
    response["X-Content-Type-Options"]="nosniff"
    return response


from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from .models import (InternationalChecklistItem, SavedCareerPlan, SalaryBenchmark,
                     ProvincialLicenceFee)

CHECKLIST = [
    ("education", "Confirm education jurisdiction and CAPR pathway"),
    ("capr", "Review current CAPR requirements and document submission rules"),
    ("language", "Check accepted language evidence and exemptions"),
    ("documents", "Request official transcripts and required school documents"),
    ("professional", "Confirm registration or good-standing documentation if applicable"),
    ("assessment", "Budget for CAPR credentialling and assessment stages"),
    ("province", "Review your destination province's regulator requirements"),
    ("fees", "Confirm provincial application, examination and registration fees"),
    ("immigration", "Review IRCC immigration/work authorization requirements separately"),
    ("apply", "Submit applications through official organizations only"),
]

def salary_comparison(request):
    benchmarks = SalaryBenchmark.objects.filter(is_published=True).order_by("region")
    return render(request, "career_mobility/salary_comparison.html", {"benchmarks": benchmarks})

@require_POST
@login_required
def save_plan(request):
    """Legacy endpoint: Canadian planning only; salary uses the canonical validator."""
    import json
    from django.http import JsonResponse
    international = hasattr(request.user, "international_pt_profile")
    canadian = bool(getattr(getattr(request.user, "jobseeker", None), "is_approved", False))
    if international or not canadian:
        return HttpResponseForbidden("A PTJC candidate account is required.")
    try:
        payload = json.loads(request.body)
        plan_type = payload["plan_type"]
        if plan_type == "salary":
            from .salary_save import save_salary_comparison
            return save_salary_comparison(request)
        inputs = payload["inputs"]
        if plan_type not in ("salary", "relocation") or (international and not canadian and plan_type != "salary"):
            return HttpResponseForbidden("This comparison is not available for your account type.")
        if not isinstance(inputs, dict) or len(json.dumps(inputs)) > 6000 or not inputs:
            raise ValueError("Invalid plan")
        import math
        if not all(isinstance(k, str) and isinstance(v, (str, int, float, bool, type(None))) and (not isinstance(v,float) or math.isfinite(v)) for k, v in inputs.items()):
            raise ValueError("Invalid plan fields")
        plan = SavedCareerPlan.objects.create(user=request.user, plan_type=plan_type,
            title=str(payload.get("title") or "My comparison")[:120], inputs=inputs)
        return JsonResponse({"id": plan.pk, "saved": True, "url": reverse("mobility_my_plans")})
    except (ValueError, KeyError, TypeError, AttributeError, json.JSONDecodeError):
        return JsonResponse({"error": "Invalid plan data"}, status=400)

@login_required
def my_plans(request):
    if not (hasattr(request.user, "jobseeker") or hasattr(request.user, "international_pt_profile")):
        return HttpResponseForbidden("A PTJC candidate account is required.")
    return render(request, "career_mobility/my_plans.html", {"plans": SavedCareerPlan.objects.filter(user=request.user).order_by("-created_at")[:50]})

@login_required
@require_POST
def delete_plan(request, pk):
    plan = get_object_or_404(SavedCareerPlan, pk=pk, user=request.user)
    kind=plan.plan_type
    plan.delete()
    return redirect("mobility_relocation_comparisons" if kind=="relocation" else "mobility_my_plans")

@login_required
def plan_pdf(request, pk):
    """Private, simple report for an existing saved comparison; never expose another user's data."""
    plan = get_object_or_404(SavedCareerPlan, pk=pk, user=request.user)
    if plan.plan_type == "salary":
        from .salary_report import pdf_bytes
        try:
            report=pdf_bytes(plan.inputs, plan.title)
        except (ValueError, TypeError, KeyError, OverflowError):
            return HttpResponse("This saved comparison has invalid values.",status=400)
        response=HttpResponse(report,content_type="application/pdf")
        response["Content-Disposition"]='attachment; filename="ptjc-salary-comparison.pdf"'
        response["Cache-Control"]="private, no-store"
        return response

    if plan.plan_type=='relocation':
        from .relocation_pdf import comparison_response
        return comparison_response(plan.inputs)
    raise Http404('Unknown comparison type')


@login_required(login_url="mobility_international_login")
@require_POST
def checklist_toggle(request):
    profile = getattr(request.user, "international_pt_profile", None)
    if profile is None:
        return HttpResponseForbidden("International account required.")
    key = request.POST.get("key", "")
    from .planning import build
    if key not in {step["key"] for step in build(profile)["steps"]}:
        return HttpResponse(status=400)
    item, _ = InternationalChecklistItem.objects.get_or_create(profile=profile, key=key)
    requested=request.POST.get("completed")
    if requested not in (None,"true","false"):return HttpResponse(status=400)
    item.completed = (requested=="true") if requested is not None else not item.completed
    item.save(update_fields=["completed", "updated_at"])
    from .international_activity import record
    record(request,'checklist_completed' if item.completed else 'checklist_reopened',subject=key)
    if request.headers.get("Accept")=="application/json":
        from django.http import JsonResponse
        keys=[step["key"] for step in build(profile)["steps"]]
        completed_keys=set(profile.checklist_items.filter(key__in=keys,completed=True).values_list("key",flat=True))
        next_step=next((step for step in build(profile)["steps"] if step["key"] not in completed_keys),None)
        return JsonResponse({"completed":item.completed,"done":len(completed_keys),"total":len(keys),"next_step":{"label":next_step["label"],"detail":next_step["detail"]} if next_step else None})
    return redirect(reverse("mobility_international_dashboard")+"#checklist")

def personalized_checklist(request):
    from .store_views import workbook
    return workbook(request)

@login_required
@require_POST
def product_checkout(request, pk):
    from .store_views import checkout
    return checkout(request, pk)

@login_required
def product_success(request):
    import os,stripe
    from .product_payments import fulfill,InvalidProductCheckout
    session_id=request.GET.get('session_id','')
    if not session_id or len(session_id)>255:return HttpResponse('Payment reference is missing.',status=400)
    from .store_config import stripe_key
    secret=stripe_key()
    if not secret:return HttpResponse('Payment confirmation is temporarily unavailable.',status=503)
    try:
        session=stripe.checkout.Session.retrieve(session_id,api_key=secret)
        order=fulfill(session,expected_user=request.user.pk,site_base=request.build_absolute_uri('/'))
    except (InvalidProductCheckout,ProductOrder.DoesNotExist):
        return HttpResponse('This payment could not be confirmed for your account. Please contact PTJC with your payment reference.',status=400)
    except stripe.error.StripeError:
        return render(request,'career_mobility/payment_result.html',{'result_base':'career_mobility/standalone.html' if hasattr(request.user,'international_pt_profile') else 'career_mobility/base_tool.html','payment_error':'Payment confirmation is temporarily unavailable. Check your resource library before trying another payment.'},status=503)
    request.session.pop('resource_checkout_token',None)
    from .pricing import pricing_audience
    from .shop_gallery import resource_link
    audience = pricing_audience(request.user, order.product)
    return render(request, 'career_mobility/payment_result.html', {
        'order': order,
        'retry_url': resource_link(order.product, audience),
        'result_base': 'career_mobility/standalone.html' if hasattr(request.user, 'international_pt_profile') else 'career_mobility/base_tool.html',
    })

@csrf_exempt
@require_POST
def mobility_stripe_webhook(request):
    import os,stripe
    from .product_payments import fulfill,InvalidProductCheckout
    secret=os.environ.get('PT_MOBILITY_STRIPE_WEBHOOK_SECRET','')
    if not secret:return HttpResponse(status=503)
    try:event=stripe.Webhook.construct_event(request.body,request.META.get('HTTP_STRIPE_SIGNATURE',''),secret)
    except (ValueError,stripe.error.SignatureVerificationError):return HttpResponse(status=400)
    if event['type'] in ('checkout.session.completed','checkout.session.async_payment_succeeded'):
        obj=event['data']['object']
        reference=obj.get('id','')
        if not (obj.get('metadata',{}).get('mobility_product_id') or ProductOrder.objects.filter(stripe_session_id=reference).exists()):return HttpResponse(status=200)
        # Snapshot payloads use the destination's selected API version. Retrieve
        # older/incomplete snapshots rather than interpreting missing payment data.
        if any(key not in obj for key in ('payment_status','amount_total','currency')) or (obj.get('payment_status')=='unpaid' and 'status' not in obj):
            from .store_config import stripe_key
            key=stripe_key()
            if not key:return HttpResponse(status=503)
            try:obj=stripe.checkout.Session.retrieve(reference,api_key=key,stripe_version=stripe.api_version)
            except stripe.error.StripeError:return HttpResponse(status=503)
            if obj.get('id')!=reference:return HttpResponse(status=400)
        try:fulfill(obj,site_base=request.build_absolute_uri('/'))
        except InvalidProductCheckout:return HttpResponse(status=400)
        except ProductOrder.DoesNotExist:return HttpResponse(status=503)
    if event['type'] in ('checkout.session.expired','checkout.session.async_payment_failed'):
        from django.utils import timezone
        failed=event['type']=='checkout.session.async_payment_failed'
        orders=ProductOrder.objects.filter(stripe_session_id=event['data']['object'].get('id'),paid=False)
        if not failed:orders=orders.exclude(checkout_state='processing')
        orders.update(checkout_state='failed' if failed else 'expired',checkout_expires_at=timezone.now())
    return HttpResponse(status=200)


def clinic_offer_guide(request):
    """Free educational companion to the public salary comparison tool."""
    return render(request, "career_mobility/clinic_offer_guide.html")


@require_POST
def salary_comparison_pdf(request):
    """Generate a private report; do not trust client-calculated totals."""
    import json
    from django.http import HttpResponse, JsonResponse
    from .salary_report import pdf_bytes
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)
    try:
        payload=json.loads(request.body)
        result=pdf_bytes(payload)
    except (ValueError, TypeError, KeyError, OverflowError, json.JSONDecodeError):
        return JsonResponse({"error": "Enter valid values for both offers."}, status=400)
    response=HttpResponse(result,content_type="application/pdf")
    response["Content-Disposition"]='attachment; filename="ptjc-salary-vs-split.pdf"'
    response["Cache-Control"]="private, no-store"
    return response

@login_required(login_url="mobility_international_login")
@require_POST
def update_international_profile(request):
    """Update only the signed-in international PT's own planning details."""
    from .forms import InternationalProfileUpdateForm
    profile = getattr(request.user, "international_pt_profile", None)
    if profile is None:
        return HttpResponseForbidden("International PT account required.")
    form = InternationalProfileUpdateForm(request.POST, instance=profile)
    if form.is_valid():
        form.save()
        from .international_activity import record
        record(request,'profile_updated')
        messages.success(request, "Your planning details were updated.")
        return redirect("mobility_international_dashboard")
    context=_dashboard_context(request,profile,form)
    context['active_tab']='profile'
    return render(request,"career_mobility/dashboard.html",context,status=400)

from django.contrib.auth.views import LoginView,LogoutView
class InternationalLoginView(LoginView):
    template_name='career_mobility/login.html'
    def get_success_url(self):
        if not self.request.user.international_pt_profile.email_is_verified:
            self.request.session['international_verified_next']=self.get_redirect_url()
            return reverse('mobility_verify_pending')
        return self.get_redirect_url() or reverse('mobility_international_dashboard')
    def form_valid(self,form):
        if not hasattr(form.get_user(),'international_pt_profile'):
            form.add_error(None,'Use your international planning account to sign in here.')
            return self.form_invalid(form)
        response=super().form_valid(form)
        from .planner_views import apply_pending
        apply_pending(self.request,self.request.user.international_pt_profile)
        return response
class InternationalLogoutView(LogoutView):
    next_page='mobility_international'

@login_required
def offer_review(request):
    js=getattr(request.user,'jobseeker',None)
    if js is None or not js.is_approved:return HttpResponseForbidden('An approved Canadian job seeker account is required.')
    return render(request,'career_mobility/offer_review.html')

