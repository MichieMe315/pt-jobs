from __future__ import annotations

from datetime import date, datetime
from django.core.management.base import BaseCommand
from django.db.models import F, CharField, Value
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone

from board.models import Job


def _parse_date_from_text(s: str | None) -> date | None:
    if not s:
        return None
    s = s.strip()
    # Keep only YYYY-MM-DD if a datetime string comes through
    try:
        y, m, d = s.split("T")[0].split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def _parse_dt_from_text(s: str | None) -> datetime:
    if not s:
        return timezone.now()
    try:
        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    except Exception:
        return timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


class Command(BaseCommand):
    help = "Normalize bad Job.posting_date / Job.created_at values to valid types without loading raw date columns."

    def handle(self, *args, **options):
        """
        IMPORTANT: we never fetch the real date/datetime fields.
        We fetch only text casts produced by the DB so Django doesn't try to parse them on read.
        """
        qs = (
            Job.objects.only("id")  # don't load actual posting_date/created_at
            .annotate(
                posting_date_txt=Cast(F("posting_date"), CharField()),
                created_at_txt=Cast(F("created_at"), CharField()),
                # fallbacks (empty string if NULL)
                posting_date_txt2=Coalesce(F("posting_date_txt"), Value("")),
                created_at_txt2=Coalesce(F("created_at_txt"), Value("")),
            )
            .values("id", "posting_date_txt2", "created_at_txt2")
        )

        fixed = 0
        for row in qs.iterator(chunk_size=500):
            job_id = row["id"]
            pd_txt = row["posting_date_txt2"] or ""
            ca_txt = row["created_at_txt2"] or ""

            new_pd = _parse_date_from_text(pd_txt)
            new_ca = _parse_dt_from_text(ca_txt)

            # Fetch a single instance by id; now we will overwrite with safe values.
            job = Job.objects.only("id").get(pk=job_id)
            update_fields = []

            # For posting_date: keep None if invalid text
            try:
                # Assign even if None; DB will store NULL
                job.posting_date = new_pd
                update_fields.append("posting_date")
            except Exception:
                # If assignment fails for some reason, skip posting_date
                pass

            try:
                job.created_at = new_ca
                update_fields.append("created_at")
            except Exception:
                pass

            if update_fields:
                job.save(update_fields=update_fields)
                fixed += 1

        self.stdout.write(self.style.SUCCESS(f"Normalized date fields on {fixed} Job rows."))
