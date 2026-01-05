from __future__ import annotations
from django import template
from django.utils import timezone
from django.db.models import Q
from board.models import Job

register = template.Library()

@register.inclusion_tag("includes/_jobs_widget.html")
def recent_jobs_widget(limit=5, title="Recent Jobs"):
    now = timezone.now()
    jobs = Job.objects.filter(posting_date__lte=now).filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=now.date())).order_by("-posting_date")[:limit]
    return {"jobs": jobs, "title": title}
