from __future__ import annotations

from datetime import timedelta
import json

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path
from django.utils import timezone
from django.utils.text import slugify

from board.models import Employer, Job
from .forms import MarketingGraphicForm
from .generator import EmployerCard, PROVINCES, headline_text, render_graphic, render_single_graphic, split_location


def _active_jobs_queryset():
    today = timezone.localdate()
    return Job.objects.filter(is_active=True).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)).select_related("employer")


def _active_employers():
    active_jobs = _active_jobs_queryset()
    return list(
        Employer.objects.filter(is_approved=True).exclude(logo__isnull=True).exclude(logo="")
        .annotate(active_job_count=Count("jobs", filter=Q(jobs__in=active_jobs), distinct=True))
        .filter(active_job_count__gt=0)
        .prefetch_related(Prefetch("jobs", queryset=active_jobs, to_attr="marketing_active_jobs"))
        .order_by("company_name", "name", "pk")
    )


def _location_choices(employers):
    province_cities = {}
    for employer in employers:
        for job in getattr(employer, "marketing_active_jobs", []):
            city, province = split_location(job.location or employer.location)
            if province:
                province_cities.setdefault(province, set())
                if city:
                    province_cities[province].add(city)
    provinces = [(code, PROVINCES.get(code, code)) for code in sorted(province_cities, key=lambda c: PROVINCES.get(c, c).lower())]
    cities = sorted({city for values in province_cities.values() for city in values}, key=str.lower)
    return provinces, [(city, city) for city in cities], {code: sorted(values, key=str.lower) for code, values in province_cities.items()}


def _matches(employer, province="", city=""):
    for job in getattr(employer, "marketing_active_jobs", []):
        job_city, job_province = split_location(job.location or employer.location)
        if (not province or job_province == province) and (not city or job_city.lower() == city.lower()):
            return True
    return False


def _select(employers, cleaned):
    kind, items = cleaned["graphic_type"], list(employers)
    if kind == "province":
        items = [e for e in items if _matches(e, province=cleaned["province"])]
    elif kind == "city":
        items = [e for e in items if _matches(e, province=cleaned.get("province") or "", city=cleaned["city"])]
    elif kind == "new":
        cutoff = timezone.now() - timedelta(days=30)
        items = sorted([e for e in items if e.created_at >= cutoff], key=lambda e: e.created_at, reverse=True)
    elif kind == "top":
        items.sort(key=lambda e: (-e.active_job_count, (e.company_name or e.name or "").lower()))
    return items[:cleaned["logo_limit"]]


def _card(employer):
    return EmployerCard(employer.company_name or employer.name or "Employer", employer.location or "", employer.logo, employer.active_job_count, employer.created_at)


@staff_member_required
def marketing_generator(request):
    employers = _active_employers()
    province_choices, city_choices, city_map = _location_choices(employers)
    selected_province = request.GET.get("province", "")
    if selected_province in city_map:
        city_choices = [(city, city) for city in city_map[selected_province]]
    employer_choices = [(str(e.pk), e.company_name or e.name or f"Employer {e.pk}") for e in employers]
    form = MarketingGraphicForm(request.GET or None, province_choices=province_choices, city_choices=city_choices, employer_choices=employer_choices)

    if form.is_valid() and request.GET.get("action") in {"preview", "download"}:
        kind = form.cleaned_data["graphic_type"]
        png = None
        title = "marketing-graphic"
        if kind == "single":
            selected = next((e for e in employers if str(e.pk) == str(form.cleaned_data["employer"])), None)
            if selected:
                card = _card(selected)
                png = render_single_graphic(card, form.cleaned_data["output_format"])
                title = f"{card.name}-hiring"
            else:
                form.add_error("employer", "That clinic is no longer eligible.")
        else:
            selected = _select(employers, form.cleaned_data)
            if selected:
                region = "Canada"
                if kind == "province": region = PROVINCES.get(form.cleaned_data["province"], form.cleaned_data["province"])
                elif kind == "city": region = form.cleaned_data["city"]
                headline = headline_text(form.cleaned_data["headline"])
                png = render_graphic(cards=[_card(e) for e in selected], headline_key=form.cleaned_data["headline"], headline=headline, region=region, output_format=form.cleaned_data["output_format"])
                title = f"{headline}-{region}"
            else:
                form.add_error(None, "No active employers with uploaded logos matched this selection.")
        if png:
            disposition = "inline" if request.GET["action"] == "preview" else "attachment"
            response = HttpResponse(png, content_type="image/png")
            response["Content-Disposition"] = f'{disposition}; filename="{slugify(title) or "marketing-graphic"}.png"'
            return response

    context = {**admin.site.each_context(request), "title": "Marketing Generator", "form": form, "eligible_count": len(employers), "province_count": len(province_choices), "city_count": sum(len(v) for v in city_map.values()), "city_map_json": json.dumps(city_map), "database_empty": Employer.objects.count() == 0 and Job.objects.count() == 0, "opts": None}
    return render(request, "admin/marketing/generator.html", context)


def install_marketing_admin_urls():
    if getattr(admin.site, "_marketing_generator_installed", False):
        return
    original_get_urls = admin.site.get_urls
    def get_urls():
        return [path("marketing-generator/", admin.site.admin_view(marketing_generator), name="marketing_generator")] + original_get_urls()
    admin.site.get_urls = get_urls
    admin.site._marketing_generator_installed = True
