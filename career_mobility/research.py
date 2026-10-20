"""Reviewed reference snapshots, read-only. Never seeds or changes the user's database."""
import json
from pathlib import Path
from django.utils import timezone
from django.db.models import Q
from .models import ProvincialLicenceFee

REGULATORS = {
 'Alberta':('College of Physiotherapists of Alberta','https://www.cpta.ab.ca/'),
 'British Columbia':('College of Health and Care Professionals of BC','https://chcpbc.org/'),
 'Manitoba':('College of Physiotherapists of Manitoba','https://manitobaphysio.com/'),
 'New Brunswick':('College of Physiotherapists of New Brunswick','https://www.cptnb.ca/'),
 'Newfoundland and Labrador':('Newfoundland and Labrador College of Physiotherapists','https://nlcpt.com/'),
 'Nova Scotia':('Nova Scotia College of Physiotherapists','https://nsphysio.com/'),
 'Ontario':('College of Physiotherapists of Ontario','https://collegept.org/'),
 'Prince Edward Island':('Prince Edward Island College of Physiotherapy','https://www.peicpt.com/registration'),
 'Quebec':('Ordre professionnel de la physiothérapie du Québec','https://oppq.qc.ca/'),
 'Saskatchewan':('Saskatchewan College of Physical Therapists','https://scpt.org/'),
 'Northwest Territories':('Government of Northwest Territories — professional licensing','https://www.hss.gov.nt.ca/en/services/professional-licensing'),
 'Nunavut':('Government of Nunavut — Health','https://www.gov.nu.ca/en/health'),
 'Yukon':('Government of Yukon — professional licensing','https://yukon.ca/en/doing-business/professional-licensing'),
}

def fee_references():
    rows=[]
    def add(province,kind,description,amount,applies,url,effective):
        rows.append(dict(province=province,regulator=REGULATORS[province][0],fee_type=kind,description=description,amount_cad=str(amount),applies_to=applies,source_url=url,effective_on=effective,verified_on='2026-10-19',reference='Reviewed regulator schedule'))
    ont='https://collegept.org/physiotherapists/registrant-information/'
    ab='https://www.cpta.ab.ca/for-physiotherapists/registration-information/practice-permit-renewal/member-fees/'
    add('Ontario','application','Registration application',114,'Applicants; separate from certificate fee',ont,'2024-04-01')
    add('Ontario','initial','Independent practice certificate — annual rate',648,'New registration is prorated by approval date',ont,'2024-04-01')
    add('Ontario','renewal','Independent practice annual renewal',648,'Existing independent practice registrants','https://collegept.org/physiotherapists/annual-renewal/','2026-04-01')
    add('Alberta','application','Initial or reinstatement application',125,'Waivers may apply to same-year reinstatement',ab,'2026-10-01')
    add('Alberta','initial','Practice permit — full annual rate',805,'2026/27 registration year; initial approval Oct–Mar',ab,'2026-10-01')
    add('Alberta','initial','Practice permit — prorated rate',615,'New application approved Apr–Sep; alternative to full rate',ab,'2026-10-01')
    add('Alberta','renewal','Annual practice permit renewal',805,'2026/27 registration year',ab,'2026-10-01')
    pei='https://www.peicpt.com/registration'
    add('Prince Edward Island','initial','New registration — general',425,'Check category and half-year eligibility',pei,'Not stated on current schedule')
    add('Prince Edward Island','renewal','Registration renewal',400,'Renewing physiotherapists',pei,'Not stated on current schedule')
    add('Prince Edward Island','application','Labour mobility transfer',425,'Canadian labour mobility applicants',pei,'Not stated on current schedule')
    add('Prince Edward Island','exam','Jurisprudence examination',75,'Where required; separate component',pei,'Not stated on current schedule')
    published=ProvincialLicenceFee.objects.filter(is_published=True).filter(Q(expires_on__isnull=True)|Q(expires_on__gte=timezone.localdate()))
    for f in published:
        # Admin-reviewed values take precedence over a bundled matching component.
        rows=[r for r in rows if not (r['province']==f.province and r['description']==f.description)]
        rows.append(dict(province=f.province,regulator=f.regulator,fee_type=f.fee_type,description=f.description,amount_cad=str(f.amount_cad) if f.amount_cad is not None else None,applies_to=f.applies_to,source_url=f.source_url,effective_on=str(f.effective_on or 'Not supplied'),verified_on=str(f.verified_on or 'Not supplied'),reference='Published PTJC review'))
    return rows

def research_context():
    locations=json.loads((Path(__file__).parent/'data/rental_references_2026_q2.json').read_text())
    return {'locations':locations,'fees':fee_references(),'regulators':{p:{'name':v[0],'url':v[1]} for p,v in REGULATORS.items()},'reviewed_on':'2026-10-19'}
