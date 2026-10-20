from django.core.management.base import BaseCommand
from career_mobility.models import DataSource

SOURCES = [
    ("PT wages — Job Bank", "salary", "https://www.jobbank.gc.ca/trend-analysis", "monthly"),
    ("CMHC rental market research", "rent", "https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research", "monthly"),
    ("Statistics Canada CPI", "living", "https://www.statcan.gc.ca/en/subjects-start/prices_and_price_indexes/consumer_price_index", "monthly"),
    ("CAPR", "credentialling", "https://alliancept.org/", "monthly"),
    ("IRCC", "immigration", "https://www.canada.ca/en/immigration-refugees-citizenship.html", "monthly"),
    ("Ontario College of Physiotherapists", "licensing", "https://collegept.org/", "monthly"),
    ("Alberta College of Physiotherapists", "licensing", "https://www.cpta.ab.ca/", "monthly"),
    ("British Columbia College of Health and Care Professionals", "licensing", "https://chcpbc.org/", "monthly"),
]

class Command(BaseCommand):
    help = "Add official mobility research source pages; existing admin edits are preserved."

    def handle(self, *args, **options):
        created = 0
        for name, category, url, cadence in SOURCES:
            _, was_created = DataSource.objects.get_or_create(name=name, defaults={"category":category, "url":url, "cadence":cadence})
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Added {created} sources; {len(SOURCES)} total starter sources."))
