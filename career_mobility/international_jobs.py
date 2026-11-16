from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from board.models import Job
from ptjc_resumes.ad_context import international_placement


def eligible_jobs():
    today = timezone.localdate()
    return (
        Job.objects.filter(is_active=True, employer__is_approved=True, employer__login_active=True,
                           employer__user__is_active=True, posting_date__lte=today,
                           international_stage__in=[key for key, _ in Job.INTERNATIONAL_STAGE_CHOICES])
        .filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
        .select_related('employer').order_by('-posting_date', '-pk')
    )


def job_feed(request):
    return render(request,'career_mobility/international_jobs.html',{
        'page':Paginator(eligible_jobs(),20).get_page(request.GET.get('page')),
        'international_ad':international_placement(),
    })
