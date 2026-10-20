"""Monitor official pages; never scrape/replace published figures automatically."""
import hashlib
import urllib.error
import urllib.request
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from career_mobility.models import DataSource, DataSourceReview

class Command(BaseCommand):
    help = "Check official source pages for changes and queue manual reviews. Run daily from an external scheduler."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Ignore monthly/quarterly check interval")
        parser.add_argument("--dry-run", action="store_true", help="List due sources without network requests")

    def handle(self, *args, **opts):
        now = timezone.now()
        checked = changed = failed = 0
        for source in DataSource.objects.filter(enabled=True).order_by("name"):
            days = 30 if source.cadence == "monthly" else 90
            if not opts["force"] and source.last_checked_at and now - source.last_checked_at < timedelta(days=days):
                continue
            if opts["dry_run"]:
                self.stdout.write(f"DUE: {source.name} — {source.url}")
                continue
            try:
                req = urllib.request.Request(source.url, headers={"User-Agent": "PTCareerDataMonitor/1.0 (publication change monitoring)", "Accept": "text/html"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    status = resp.status
                    # Bound memory and avoid downloading large files; HTML pages only.
                    content_type = resp.headers.get("Content-Type", "").lower()
                    if "text/html" not in content_type:
                        raise ValueError(f"Unsupported content type: {content_type}")
                    body = resp.read(2_000_001)
                    if len(body) > 2_000_000:
                        raise ValueError("Page exceeds 2MB; review manually")
                digest = hashlib.sha256(body).hexdigest()
                if source.content_sha256 and digest != source.content_sha256:
                    DataSourceReview.objects.create(source=source, previous_hash=source.content_sha256,
                        detected_hash=digest, detail="Source page HTML changed. Check actual publication dates and figures before updating public data.")
                    source.last_changed_at = now
                    changed += 1
                source.content_sha256 = digest
                source.last_http_status = status
                source.last_error = ""
                checked += 1
            except (urllib.error.URLError, ValueError, TimeoutError, OSError) as exc:
                source.last_error = str(exc)[:1000]
                source.last_http_status = None
                failed += 1
                self.stderr.write(f"ERROR {source.name}: {source.last_error}")
            source.last_checked_at = now
            source.save(update_fields=["last_checked_at", "last_changed_at", "last_http_status", "content_sha256", "last_error"])
        self.stdout.write(f"Checked: {checked}; changed: {changed}; failed: {failed}. Changes require admin review.")
