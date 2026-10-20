"""Import additional PT regulator fee figures only when source text confirms them.

Does not alter existing models, publish data, or invent effective dates.
"""
import re
from decimal import Decimal
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from django.core.management.base import BaseCommand
from django.utils import timezone
from career_mobility.models import ProvincialLicenceFee


class Visible(HTMLParser):
    def __init__(self):
        super().__init__()
        self.words = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
        if tag in ('tr', 'td', 'li', 'p', 'h2', 'h3'):
            self.words.append(' ')
    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
        if tag in ('tr', 'td', 'li', 'p', 'h2', 'h3'):
            self.words.append(' ')
    def handle_data(self, data):
        if not self.skip:
            self.words.append(data)

# Regexes require both a descriptive label and an exact figure close together.
# No figures from other professions are included.
SOURCES = [
    ('Manitoba', 'College of Physiotherapists of Manitoba',
     'https://manitobaphysio.com/registration/registration-process-2/', [
        ('initial', 'Initial registration application', '200.00', 'Initial applicants', r'Initial registration fee of\s*\$\s*200(?:\.00)?\b'),
        ('initial', 'Active registration full year (2026)', '913.00', 'Active registrants; 2026', r'Active registration fee of\s*\$\s*913(?:\.00)?\b'),
        ('initial', 'Active registration prorated after August 1 (2026)', '456.50', 'Eligible applications after August 1; 2026', r'\$\s*913(?:\.00)?\s*or\s*\$\s*456\.50\s*pro.rated'),
        ('provisional', 'Exam candidate registration', '863.00', 'Exam candidates', r'Exam Candidate registration fee of\s*\$\s*863(?:\.00)?\b'),
    ]),
    ('Prince Edward Island', 'Prince Edward Island College of Physiotherapy',
     'https://www.peicpt.com/registration', [
        ('initial', 'New registration (general)', '425.00', 'General applicants', r'New registration\s*\(general\)\s*\$?\s*425\b'),
        ('renewal', 'Registration renewal', '400.00', 'Renewing registrants', r'Registration renewal\s*\$?\s*400\b'),
        ('application', 'Labour mobility transfer', '425.00', 'Canadian labour mobility applicants', r'Labour mobility transfer\s*\$?\s*425\b'),
        ('exam', 'Jurisprudence exam', '75.00', 'Where required', r'Jurisprudence exam\s*\$?\s*75\b'),
    ]),
    ('Quebec', 'Ordre professionnel de la physiothérapie du Québec',
     'https://oppq.qc.ca/en/become-a-member/quebec-canada-candidates/', [
        ('application', 'First-time registration enrollment', '125.00', 'Quebec/Canada applicants; not a total annual fee', r'Enrollment fee\s*[–-]\s*first.time registration\s*:\s*\$\s*125\b'),
    ]),
]


class Command(BaseCommand):
    help = 'Import official PT fees for Manitoba, PEI, and Quebec after live source validation; never publish automatically.'
    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
    def handle(self, *args, **options):
        dry = options['dry_run']
        verified = saved = skipped = 0
        for province, regulator, url, entries in SOURCES:
            try:
                req = Request(url, headers={'User-Agent': 'Mozilla/5.0 PTCareerTools/1.0'})
                with urlopen(req, timeout=20) as response:
                    if response.status != 200:
                        raise ValueError(f'HTTP {response.status}')
                    raw = response.read(1_500_001)
                    if len(raw) > 1_500_000:
                        raise ValueError('Page too large')
                parser = Visible()
                parser.feed(raw.decode('utf-8', errors='replace'))
                text = re.sub(r'\s+', ' ', ' '.join(parser.words))
            except Exception as exc:
                self.stderr.write(f'{province}: unable to verify official page ({exc})')
                skipped += len(entries)
                continue
            for kind, label, amount, applies, pattern in entries:
                if not re.search(pattern, text, flags=re.I):
                    self.stderr.write(f'{province}: not verified: {label} (${amount})')
                    skipped += 1
                    continue
                verified += 1
                self.stdout.write(f'CONFIRMED {province}: {label} ${amount}')
                if dry:
                    continue
                # Stable identity; do not overwrite a published record or a human-edited amount.
                existing = ProvincialLicenceFee.objects.filter(province=province, description=label).first()
                if existing and (existing.is_published or (existing.amount_cad is not None and existing.amount_cad != Decimal(amount))):
                    self.stderr.write(f'REVIEW REQUIRED: {province}: {label}; existing value retained')
                    continue
                if existing is None:
                    existing = ProvincialLicenceFee(province=province, description=label)
                existing.regulator = regulator
                existing.fee_type = kind
                existing.amount_cad = Decimal(amount)
                existing.applies_to = applies
                existing.source_url = url
                existing.verified_on = timezone.localdate()
                existing.is_published = False
                existing.notes = 'Automatically source-matched; effective date and applicability require confirmation before publication.'
                existing.save()
                saved += 1
        self.stdout.write(f'Validated {verified}; saved {saved}; unverified {skipped}. No records published.')
