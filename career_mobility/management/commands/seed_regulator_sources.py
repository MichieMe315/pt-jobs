from django.core.management.base import BaseCommand
from career_mobility.models import DataSource
# Source URLs are regulatory homepages; monthly review detects changes, but does not assert any specific fee.
REGULATORS = [
 ("British Columbia","https://chcpbc.org/"),
 ("Saskatchewan","https://www.saskphysio.org/"),
 ("New Brunswick","https://www.cptnb.ca/"),
 ("Newfoundland and Labrador","https://nlcpt.com/"),
 ("Northwest Territories","https://www.hss.gov.nt.ca/en/services/professional-licensing"),
 ("Nunavut","https://www.gov.nu.ca/en/health"),
 ("Yukon","https://yukon.ca/en/doing-business/professional-licensing"),
]
class Command(BaseCommand):
    help="Register official regulator homepages for recurring change checks. No fee values are invented."
    def handle(self,*args,**kwargs):
        for province,url in REGULATORS:
            obj,created=DataSource.objects.get_or_create(name=f"PT regulator research: {province}",defaults={"category":"licensing","url":url,"cadence":"monthly"})
            self.stdout.write(f"{'Added' if created else 'Kept'} {province}")
