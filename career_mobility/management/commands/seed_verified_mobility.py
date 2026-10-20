from datetime import date
from decimal import Decimal
from django.core.management.base import BaseCommand
from career_mobility.models import ReferenceCost, PathwayRule

CMHC='https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/market-reports/rental-market-reports-major-centres'
RENTS=[('Toronto','Ontario',2547),('Vancouver','British Columbia',2696),('Calgary','Alberta',1836),('Edmonton','Alberta',1600),('Ottawa','Ontario',2155),('Halifax','Nova Scotia',2058),('Montréal','Quebec',1644)]
CAPR='https://alliancept.org/new-comparability-pathway/policies-and-requirements/pre-approved-pathway-policy/'
PRE=['Australia','Hong Kong','Ireland','New Zealand','South Africa','United Kingdom','United States']
OTHER=['India','Philippines','Nigeria','Pakistan','Bangladesh','Nepal','Ghana','Egypt','United Arab Emirates','France']
class Command(BaseCommand):
 help='Load source-backed starter references; never overwrite admin-edited records.'
 def handle(self,*args,**kwargs):
  for city,province,rent in RENTS:
   obj,created=ReferenceCost.objects.get_or_create(kind='rent',city=city,province=province,defaults={'amount_cad':Decimal(rent),'source_url':CMHC,'verified_on':date(2026,10,17),'is_published':True})
   self.stdout.write(f'{"Added" if created else "Kept"} rent: {city}')
  for country in PRE+OTHER:
   pre=country in PRE
   summary=('Potential pre-approved pathway only if the CAPR education and unrestricted registration/recent graduate eligibility criteria are met. Citizenship alone does not establish eligibility.' if pre else 'New applicants generally require CAPR comparability assessment unless another pathway applies. Verify qualification, language, documents and application status with CAPR.')
   obj,created=PathwayRule.objects.get_or_create(country=country,defaults={'pathway_label':'Potential Pre-Approved Pathway' if pre else 'Review Comparability Pathway','summary':summary,'source_url':CAPR if pre else 'https://alliancept.org/comparability-pathway-launching-october-2026/','verified_on':date(2026,10,17),'is_published':True})
   self.stdout.write(f'{"Added" if created else "Kept"} country: {country}')
  self.stdout.write(self.style.SUCCESS('Starter references seeded. Review in admin before public launch.'))
