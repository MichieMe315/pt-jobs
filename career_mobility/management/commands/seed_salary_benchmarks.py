from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from career_mobility.models import SalaryBenchmark

# Preliminary Job Bank reference points. Never auto-published.
REGIONS = [
    ("Canada", "", "46.15"),
    ("Ontario", "Ontario", "46.00"),
    ("Toronto region", "Ontario", "47.00"),
    ("Kitchener–Waterloo–Barrie", "Ontario", "45.00"),
    ("Ottawa region", "Ontario", "46.70"),
]
SOURCE="https://www.jobbank.gc.ca/marketreport/wages-occupation/18214/ca"
class Command(BaseCommand):
    help="Seed unpublished PT wage benchmarks for admin source review; does not overwrite data."
    def handle(self,*args,**kwargs):
        for region,province,wage in REGIONS:
            _,created=SalaryBenchmark.objects.get_or_create(region=region,defaults={"province":province,"median_hourly":Decimal(wage),"source_url":SOURCE,"reference_period":"Job Bank 2023–2024 reference; verify current regional page","verified_on":date(2026,10,19),"is_published":False})
            self.stdout.write(f"{'Added' if created else 'Kept'} {region}")
