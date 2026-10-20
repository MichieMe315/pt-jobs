"""Import verified official fee schedules and detect subsequent source changes.

No model edits or migrations. Never auto-publish; ambiguous/unavailable values stay empty.
"""
from datetime import date
from decimal import Decimal
import hashlib
import re
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand
from django.utils import timezone
from career_mobility.models import DataSource, DataSourceReview, ProvincialLicenceFee


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1
        if tag in ('td', 'th', 'tr', 'p', 'li', 'h2', 'h3'):
            self.parts.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('td', 'th', 'tr', 'p', 'li', 'h2', 'h3'):
            self.parts.append(' ')
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


# Each rule identifies a precise fee component, not a province-wide total.
# Effective dates refer to the applicable published schedule, not scraping time.
SCHEDULES = [
    dict(province='Alberta', regulator='College of Physiotherapists of Alberta',
         url='https://www.cpta.ab.ca/for-physiotherapists/registration-information/practice-permit-renewal/member-fees/',
         effective=date(2026, 10, 1), expires=date(2027, 9, 30),
         entries=[
             ('application', 'Initial application (non-refundable)', '125', 'New or reinstating applicants', r'Application fee.{0,240}?\$\s*125'),
             ('initial', 'Practice permit, Oct–Mar approval', '805', 'New applicants approved October–March', r'Practice permit fee.{0,300}?\$\s*805'),
             ('initial', 'Practice permit, Apr–Sep approval', '615', 'New applicants approved April–September', r'pro.rated.{0,250}?\$\s*615'),
             ('renewal', 'Annual practice permit renewal', '805', 'Existing regulated members', r'Practice permit fee.{0,300}?\$\s*805'),
         ]),
    dict(province='Ontario', regulator='College of Physiotherapists of Ontario',
         url='https://collegept.org/physiotherapists/registrant-information/',
         effective=date(2024, 4, 1), expires=None,
         entries=[
             ('application', 'Application fee', '114', 'Applicants', r'Application Fee\s*:?\s*\$\s*114'),
             ('initial', 'Independent practice registration (full annual rate; prorated for new applicants)', '648', 'Independent practice applicants; initial amount prorated', r'Independent Practice Certificate of Registration\s*:?\s*\$\s*648'),
         ]),
    dict(province='Ontario', regulator='College of Physiotherapists of Ontario',
         url='https://collegept.org/physiotherapists/annual-renewal/',
         effective=date(2026, 4, 1), expires=None,
         entries=[('renewal', 'Independent practice annual renewal', '648', 'Independent practice registrants', r'renewal fee.{0,100}?\$\s*648')]),
    dict(province='Nova Scotia', regulator='Nova Scotia College of Physiotherapists',
         url='https://members.nsphysio.com/apply/initial',
         effective=None, expires=None,
         entries=[
             ('initial', 'Full-year registration', '650', 'Full-year registration option', r'Full Year\s*[-–]?\s*\$\s*650'),
             ('initial', 'Three-month registration', '325', 'Three-month option; check eligibility and dates', r'3 Month\s*[-–]?\s*\$\s*325'),
         ]),
]


class Command(BaseCommand):
    help = 'Fetch official PT fee schedules, import confirmed amounts and flag source changes; never publish automatically.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Fetch and validate only; do not modify database')

    def handle(self, *args, **options):
        dry = options['dry_run']
        added = updated = flagged = skipped = 0
        cache = {}
        for schedule in SCHEDULES:
            url = schedule['url']
            if url not in cache:
                try:
                    req = Request(url, headers={'User-Agent': 'PTCareerToolsSourceReview/1.0 (official-public-data)'})
                    with urlopen(req, timeout=18) as response:
                        if response.status != 200:
                            raise ValueError(f'HTTP {response.status}')
                        raw = response.read(2_000_001)
                        if len(raw) > 2_000_000:
                            raise ValueError('Source exceeds 2 MB limit')
                    parser = _VisibleText()
                    parser.feed(raw.decode('utf-8', errors='replace'))
                    visible = re.sub(r'\s+', ' ', ' '.join(parser.parts))
                    cache[url] = (visible, hashlib.sha256(visible.encode()).hexdigest(), '')
                except Exception as exc:
                    cache[url] = ('', '', str(exc))
            visible, digest, error = cache[url]
            if not dry:
                source, _ = DataSource.objects.get_or_create(
                    name=f"PT fee schedule: {schedule['province']} — {url.split('/')[2]}",
                    defaults={'category': 'licensing', 'url': url, 'cadence': 'monthly'},
                )
                old_hash = source.content_sha256
                if error:
                    source.last_error = error[:1000]
                else:
                    source.last_error = ''
                    source.last_http_status = 200
                    if old_hash and old_hash != digest:
                        DataSourceReview.objects.get_or_create(
                            source=source, detected_hash=digest,
                            defaults={'previous_hash': old_hash, 'detail': 'Official fee page changed. Recheck fee amounts, effective dates and applicant conditions.'},
                        )
                        flagged += 1
                    if old_hash != digest:
                        source.last_changed_at = timezone.now()
                    source.content_sha256 = digest
                source.last_checked_at = timezone.now()
                source.save()
            if error:
                skipped += len(schedule['entries'])
                self.stderr.write(f"Unavailable: {url}: {error}")
                continue
            for fee_type, description, expected, applies, pattern in schedule['entries']:
                if not re.search(pattern, visible, flags=re.IGNORECASE):
                    skipped += 1
                    self.stdout.write(f'Needs review: {schedule["province"]}: {description} (source text not confirmed)')
                    continue
                if dry:
                    self.stdout.write(f'Confirmed in source: {schedule["province"]}: {description} ${expected}')
                    continue
                fee, created = ProvincialLicenceFee.objects.get_or_create(
                    province=schedule['province'], fee_type=fee_type, description=description,
                    defaults={'regulator': schedule['regulator'], 'is_published': False},
                )
                amount = Decimal(expected)
                # Preserve published figures pending review; do not overwrite any manual corrections.
                if fee.is_published or (not created and fee.amount_cad is not None and fee.amount_cad != amount):
                    if fee.amount_cad != amount:
                        flagged += 1
                        self.stdout.write(f'Review needed (existing value preserved): {fee}')
                    continue
                fee.amount_cad = amount
                fee.applies_to = applies
                fee.source_url = url
                fee.verified_on = timezone.localdate()
                fee.effective_on = schedule['effective']
                fee.expires_on = schedule['expires']
                fee.notes = 'Official fee-page text matched. Unpublished pending review; see source for full eligibility and taxes.'
                fee.save()
                added += int(created)
                updated += int(not created)
        self.stdout.write(self.style.SUCCESS(f'Added {added}, refreshed {updated}, review flags {flagged}, unverified/unavailable {skipped}. No fees auto-published.'))
