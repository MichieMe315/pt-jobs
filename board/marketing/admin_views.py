from __future__ import annotations

from datetime import timedelta
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
from .generator import EmployerCard, PROVINCES, render_graphic, split_location


def _active_jobs_queryset():
    today = timezone.localdate()
    return Job.objects.filter(is_active=True).filter(
        Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)
    ).select_related("employer")


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
        .prefetch_related(Prefetch("jobs", queryset=active_jobs, to_attr="marketing_active_jobs"))
        .order_by("company_name", "name", "pk")
    )


def _choices(employers):
    provinces, cities = set(), set()
    for employer in employers:
        for job in getattr(employer, "marketing_active_jobs", []):
            city, province = split_location(job.location or employer.location)
            if province:
                provinces.add(province)
            if city:
                cities.add(city)
    province_choices = [
        (code, PROVINCES.get(code, code))
        for code in sorted(provinces, key=lambda c: PROVINCES.get(c, c))
    ]
    city_choices = [(city, city) for city in sorted(cities, key=str.lower)]
    return province_choices, city_choices


def _employer_matches_location(employer, province="", city=""):
    for job in getattr(employer, "marketing_active_jobs", []):
        job_city, job_province = split_location(job.location or employer.location)
        if province and job_province == province:
            return True
        if city and job_city.lower() == city.lower():
            return True
    return False


def _select(employers, cleaned):
    kind = cleaned["graphic_type"]
    items = list(employers)

    if kind == "province":
        province = cleaned["province"]
        items = [e for e in items if _employer_matches_location(e, province=province)]
        title = f"Hiring in {PROVINCES.get(province, province)}"
    elif kind == "city":
        city = cleaned["city"]
        items = [e for e in items if _employer_matches_location(e, city=city)]
        title = f"Hiring in {city}"
    elif kind == "new":
        cutoff = timezone.now() - timedelta(days=30)
        items = [e for e in items if e.created_at >= cutoff]
        items.sort(key=lambda e: e.created_at, reverse=True)
        title = "New Employers This Month"
    elif kind == "top":
        items.sort(key=lambda e: (-e.active_job_count, (e.company_name or e.name).lower()))
        title = "Top Hiring Employers"
    else:
        title = "Now Hiring Across Canada"

    return items[: cleaned["logo_limit"]], title


@staff_member_required
def marketing_generator(request):
    employers = _active_employers()
    province_choices, city_choices = _choices(employers)
    form = MarketingGraphicForm(
        request.GET or None,
        province_choices=province_choices,
        city_choices=city_choices,
    )

    if form.is_valid() and request.GET.get("action") in {"preview", "download"}:
        selected, title = _select(employers, form.cleaned_data)
        if not selected:
            form.add_error(
                None,
                "No employers with active, unexpired jobs and uploaded logos matched this selection.",
            )
        else:
            cards = [
                EmployerCard(
                    e.company_name or e.name or "Employer",
                    e.location,
                    e.logo,
                    e.active_job_count,
                    e.created_at,
                )
                for e in selected
            ]
            png = render_graphic(
                cards,
                title,
                f"{len(cards)} employers currently hiring",
                form.cleaned_data["output_format"],
            )
            disposition = "inline" if request.GET["action"] == "preview" else "attachment"
            response = HttpResponse(png, content_type="image/png")
            response["Content-Disposition"] = f'{disposition}; filename="{slugify(title)}.png"'
            return response

    context = {
        **admin.site.each_context(request),
        "title": "Marketing Generator",
        "form": form,
        "eligible_count": len(employers),
        "province_count": len(province_choices),
        "city_count": len(city_choices),
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
