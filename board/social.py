import json
import logging

from django.urls import reverse

from .models import SiteSettings, Job

log = logging.getLogger(__name__)


def _get_sitesettings() -> SiteSettings | None:
    return SiteSettings.objects.order_by("-id").first()


def _job_url(request, job: Job) -> str:
    try:
        return request.build_absolute_uri(reverse("job_detail", args=[job.pk]))
    except Exception:
        # Fallback – relative URL
        return f"/jobs/{job.pk}/"


def post_job_to_social(request, job: Job):
    """
    Called from views when a job is posted/published (credit consumed).

    Behaviour:
    - Reads SiteSettings:
        - social_webhook_url
        - share_facebook / share_instagram / share_reddit
    - If social_webhook_url is set and any share_* is True:
        - Sends a JSON payload to that webhook (Make.com scenario).
    - If anything goes wrong, it only logs – never breaks the site.
    """

    ss = _get_sitesettings()
    if not ss:
        return

    if not ss.social_webhook_url:
        # No webhook configured → auto-posting effectively disabled
        return

    platforms = {
        "facebook": bool(ss.share_facebook),
        "instagram": bool(ss.share_instagram),
        "reddit": bool(ss.share_reddit),
    }

    if not any(platforms.values()):
        # No platform enabled → nothing to do
        return

    # Import requests lazily so the project can still run if it's not installed.
    try:
        import requests  # type: ignore
    except Exception:
        log.warning("requests library not available; skipping social webhook call.")
        return

    job_url = _job_url(request, job)

    payload = {
        "job": {
            "id": job.pk,
            "title": job.title,
            "description": job.description,
            "employer": job.employer.company_name,
            "location": job.location,
            "job_type": job.job_type,
            "compensation_type": job.compensation_type,
            "posting_date": job.posting_date.isoformat() if job.posting_date else None,
            "expiry_date": job.expiry_date.isoformat() if job.expiry_date else None,
            "url": job_url,
        },
        "platforms": platforms,
    }

    try:
        resp = requests.post(
            ss.social_webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        if resp.status_code >= 400:
            log.warning(
                "Social webhook responded with %s: %s",
                resp.status_code,
                resp.text[:500],
            )
    except Exception as e:
        log.exception("Error calling social webhook: %s", e)
