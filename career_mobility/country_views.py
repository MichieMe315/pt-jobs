from urllib.parse import urlencode
from ptjc_resumes.ad_context import international_placement
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from .country_content import countries, get_country
from .international_activity import record
from .models import CountryResourceCollection, DigitalProduct, ProductOrder
from .forms import PROVINCES


def country_index(request):
    from .views import international
    return international(request)


def country_page(request,slug):
    country=get_country(slug)
    if not country:raise Http404('Country not found')
    profile=getattr(request.user,'international_pt_profile',None)
    from .planning import from_answers,build
    from .countries import COUNTRIES
    selected={'country':country['name'],'province':request.GET.get('province',profile.destination_province if profile else '') or 'Undecided','applied':request.GET.get('applied',{'new':'not-applied','existing':'before','after':'after','unsure':'unsure'}.get(request.GET.get('application_history',profile.application_history if profile else 'new'),'not-applied')),'registration':request.GET.get('registration',profile.registered_in_education_country if profile else 'unsure') or 'unsure'}
    if selected['registration']=='recent':selected['registration']='no'
    try:answers=from_answers(selected)
    except ValueError as exc:return HttpResponse(str(exc),status=400)
    plan=build(answers)
    completed=set(profile.checklist_items.filter(completed=True).values_list('key',flat=True)) if profile else set()
    steps=[dict(s,completed=s['key'] in completed) for s in plan['steps']]
    record(request,'country_viewed',page_country=country['name'])
    return render(request,'career_mobility/country.html',{'international_ad':international_placement(),'country':country,'plan':plan,'steps':steps,'answers':selected,'profile':profile,'provinces':PROVINCES})


def country_resources(request,slug):
    country=get_country(slug)
    if not country:raise Http404
    from .planning import from_answers
    from .planner_views import snapshot
    profile=getattr(request.user,'international_pt_profile',None)
    selected={'country':country['name'],'province':request.GET.get('province',profile.destination_province if profile else '') or 'Undecided','applied':request.GET.get('applied',{'new':'not-applied','existing':'before','after':'after','unsure':'unsure'}.get(profile.application_history if profile else 'new','not-applied')),'registration':request.GET.get('registration',profile.registered_in_education_country if profile else 'unsure') or 'unsure'}
    try:answers=from_answers(selected)
    except ValueError as exc:return HttpResponse(str(exc),status=400)
    signup_query=urlencode(snapshot(answers))
    explicit=any(key in request.GET for key in ('province','applied','registration'))
    saved_plan_matches=bool(profile and (not explicit or all(getattr(profile,key)==value for key,value in snapshot(answers).items())))
    record(request,'resources_viewed',page_country=country['name'])
    collection=CountryResourceCollection.objects.filter(country_slug=country['slug'],is_published=True).first()
    products=collection.products.filter(is_published=True).exclude(download='') if collection else DigitalProduct.objects.none()
    bundle=collection.bundle_product if collection and collection.bundle_product_id and collection.bundle_product.is_published and collection.bundle_product.download else None
    from .store_access import owned_ids
    owned=owned_ids(request.user)
    return render(request,'career_mobility/country_resources.html',{'country':country,'collection':collection,'products':products,'bundle':bundle,'owned_ids':owned,'signup_query':signup_query,'saved_plan_matches':saved_plan_matches})


@login_required(login_url='mobility_international_login')
def country_guide(request,slug):
    country=get_country(slug)
    profile=getattr(request.user,'international_pt_profile',None)
    if not country:raise Http404
    if not profile:return HttpResponse('International account required.',status=403)
    if country['name']!=profile.country_of_education:return HttpResponse('Choose the education country saved in your profile.',status=400)
    from .views import personalized_checklist
    response=personalized_checklist(request)
    if response.get('Content-Type','').startswith('application/pdf'):
        record(request,'country_guide_downloaded',page_country=country['name'])
    return response
