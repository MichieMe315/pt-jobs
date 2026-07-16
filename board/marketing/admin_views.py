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
from .generator import (
    EmployerCard,
    PROVINCES,
    headline_text,
    render_graphic,
    split_location,
)


def _active_jobs_queryset():
    today = timezone.localdate()
    return (
        Job.objects.filter(is_active=True)
        .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
        .select_related("employer")
    )


def _active_employers():
    active_jobs = _active_jobs_queryset()
    return list(
        Employer.objects.filter(is_approved=True)
        .exclude(logo__isnull=True)
        .exclude(logo="")
        .annotate(
            active_job_count=Count(
                "jobs",
                filter=Q(jobs__in=active_jobs),
                distinct=True,
            )
        )
        .filter(active_job_count__gt=0)
        .prefetch_related(
            Prefetch("jobs", queryset=active_jobs, to_attr="marketing_active_jobs")
        )
        .order_by("company_name", "name", "pk")
    )


def _location_choices(employers):
    province_cities = {}

    for employer in employers:
        for job in getattr(employer, "marketing_active_jobs", []):
            city, province = split_location(job.location or employer.location)
            if not province:
                continue
            province_cities.setdefault(province, set())
            if city:
                province_cities[province].add(city)

    province_choices = [
        (code, PROVINCES.get(code, code))
        for code in sorted(
            province_cities,
            key=lambda code: PROVINCES.get(code, code).lower(),
        )
    ]

    all_cities = sorted(
        {city for cities in province_cities.values() for city in cities},
        key=str.lower,
    )
    city_choices = [(city, city) for city in all_cities]

    city_map = {
        province: sorted(cities, key=str.lower)
        for province, cities in province_cities.items()
    }
    return province_choices, city_choices, city_map


def _employer_matches_location(employer, province="", city=""):
    for job in getattr(employer, "marketing_active_jobs", []):
        job_city, job_province = split_location(job.location or employer.location)
        province_match = not province or job_province == province
        city_match = not city or job_city.lower() == city.lower()
        if province_match and city_match:
            return True
    return False


def _selection_context(cleaned):
    kind = cleaned["graphic_type"]
    province = cleaned.get("province") or ""
    city = cleaned.get("city") or ""

    if kind == "province":
        return PROVINCES.get(province, province)
    if kind == "city":
        return city
    return "Canada"


def _select(employers, cleaned):
    kind = cleaned["graphic_type"]
    items = list(employers)

    if kind == "province":
        province = cleaned["province"]
        items = [
            employer
            for employer in items
            if _employer_matches_location(employer, province=province)
        ]
    elif kind == "city":
        city = cleaned["city"]
        province = cleaned.get("province") or ""
        items = [
            employer
            for employer in items
            if _employer_matches_location(
                employer,
                province=province,
                city=city,
            )
        ]
    elif kind == "new":
        cutoff = timezone.now() - timedelta(days=30)
        items = [employer for employer in items if employer.created_at >= cutoff]
        items.sort(key=lambda employer: employer.created_at, reverse=True)
    elif kind == "top":
        items.sort(
            key=lambda employer: (
                -employer.active_job_count,
                (employer.company_name or employer.name or "").lower(),
            )
        )

    return items[: cleaned["logo_limit"]]


@staff_member_required
def marketing_generator(request):
    employers = _active_employers()
    province_choices, city_choices, city_map = _location_choices(employers)

    selected_province = request.GET.get("province", "")
    if selected_province and selected_province in city_map:
        city_choices = [(city, city) for city in city_map[selected_province]]

    form = MarketingGraphicForm(
        request.GET or None,
        province_choices=province_choices,
        city_choices=city_choices,
    )

    if form.is_valid() and request.GET.get("action") in {"preview", "download"}:
        selected = _select(employers, form.cleaned_data)

        if not selected:
            form.add_error(
                None,
                "No active employers with uploaded logos matched this selection.",
            )
        else:
            cards = [
                EmployerCard(
                    name=employer.company_name or employer.name or "Employer",
                    location=employer.location or "",
                    logo=employer.logo,
                    active_jobs=employer.active_job_count,
                    created_at=employer.created_at,
                )
                for employer in selected
            ]

            region = _selection_context(form.cleaned_data)
            headline = headline_text(form.cleaned_data["headline"])

            png = render_graphic(
                cards=cards,
                headline_key=form.cleaned_data["headline"],
                headline=headline,
                region=region,
                output_format=form.cleaned_data["output_format"],
            )

            disposition = (
                "inline"
                if request.GET["action"] == "preview"
                else "attachment"
            )
            filename = slugify(f"{headline}-{region}") or "marketing-graphic"
            response = HttpResponse(png, content_type="image/png")
            response["Content-Disposition"] = (
                f'{disposition}; filename="{filename}.png"'
            )
            return response

    context = {
        **admin.site.each_context(request),
        "title": "Marketing Generator",
        "form": form,
        "eligible_count": len(employers),
        "province_count": len(province_choices),
        "city_count": sum(len(cities) for cities in city_map.values()),
        "city_map_json": json.dumps(city_map),
        "database_empty": Employer.objects.count() == 0 and Job.objects.count() == 0,
        "opts": None,
    }
    return render(request, "admin/marketing/generator.html", context)


def install_marketing_admin_urls():
    if getattr(admin.site, "_marketing_generator_installed", False):
        return

    original_get_urls = admin.site.get_urls

    def get_urls():
        custom = [
            path(
                "marketing-generator/",
                admin.site.admin_view(marketing_generator),
                name="marketing_generator",
            )
        ]
        return custom + original_get_urls()

    admin.site.get_urls = get_urls
    admin.site._marketing_generator_installed = True
