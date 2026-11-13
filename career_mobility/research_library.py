"""Dated source evidence for career planning. Never invent a city crosswalk or budget."""
import json
from functools import lru_cache
from pathlib import Path
from django.core.paginator import Paginator
from django.shortcuts import render

ROOT=Path(__file__).parent/'data/research_2026_10_20'
DATASETS={
'housing_cmhc_rural_2025':('Rural rents — CMHC','2025 occupied-rental survey averages, not current asking rents. Suppressed and low-quality values are not suggested budgets.'),
'housing_alberta_rural_2025':('Alberta small-community rents','2025 private multifamily survey. Houses, basement suites and condos are outside its scope. Banff vacancy is withheld.'),
'housing_national_2025':('Rental markets — national source areas','2025 historical survey rents. Areas can be regional aggregates; select the exact source geography.'),
'vacancy_small_centres_2025':('Small-centre rental vacancy','2025 survey vacancy, not a list of currently available units.'),
'pt_wages_regional':('Physiotherapist wages','Employee hourly wage references by region. These are not community-specific offers or contractor fees.'),
'licensing_fees':('Provincial and territorial registration costs','Fee components, alternatives and application categories. Do not add every row together.'),
'international_costs':('International assessment and course costs','Assessment, course and refund references. Eligibility, alternatives and exclusions matter.'),
'international_fee_scenarios':('International assessment fee examples','Partial CAPR fee scenarios only. They exclude additional applicant costs and are not individual eligibility decisions.'),
'language_test_prices':('Language test booking prices','Country and currency-specific prices. No currency conversion or booking availability is implied.'),
'international_language_policy':('Language evidence policy','Accepted test scores, validity and exemption conditions; confirm the current policy before booking.'),
'food_northern_communities_2026':('Northern community food baskets','March 2026 reference basket for four people. Monthly values use weekly × 52 ÷ 12; this is not every household’s grocery bill.'),
'household_mbm_family_sizes_2025':('Basic-needs thresholds by household size','Market Basket Measure thresholds, not measured household spending or a relocation quote.'),
'household_mbm_components_2025':('Basic-needs threshold components','Do not add component amounts to a total that already includes them. Nunavut uses a different reference family.'),
'municipal_utility_components':('Municipal water and sewer components','Partial tariffs, not a complete utility bill. Heating, electricity and usage can be missing.'),
'rural_incentives':('Rural recruitment and retention programs','Conditional program examples, not guaranteed earnings. Excluded professions remain explicitly marked.'),
'hospital_pay_examples':('Hospital job posting examples','Dated examples, not regional wage benchmarks. Vacancy and current pay require confirmation.'),
'priority_community_coverage':('Community research coverage','Proposed research communities. Name matches do not establish geographic equivalence.'),
'gaps_and_conflicts':('Research gaps and conflicts','What still needs confirmation. Missing figures stay missing.'),
'international_country_document_notes_2026':('Education-country document guidance','Education, citizenship and residence are separate. Country alone does not establish pathway eligibility.'),
'source_provenance':('Source register','Original download sources and retrieval dates for the research snapshots.'),
}
CODES={'AB':'Alberta','BC':'British Columbia','MB':'Manitoba','NB':'New Brunswick','NL':'Newfoundland and Labrador','NS':'Nova Scotia','NT':'Northwest Territories','NU':'Nunavut','ON':'Ontario','PE':'Prince Edward Island','QC':'Quebec','SK':'Saskatchewan','YT':'Yukon','CA':'Canada'}

@lru_cache(maxsize=24)
def snapshot(name):
    if name not in DATASETS: raise ValueError('Unknown research collection')
    return json.loads((ROOT/(name+'.json')).read_text(encoding='utf-8'))

def records(name): return snapshot(name).get('records',[])

MEASURES={
'monthly_rent_cad':'Average monthly rent (CAD)','rent_low_cad':'Survey rent low (CAD)','rent_high_cad':'Survey rent high (CAD)',
'vacancy_percent':'Vacancy (%)','low_hourly_cad':'Low hourly wage (CAD)','median_hourly_cad':'Median hourly wage (CAD)','high_hourly_cad':'High hourly wage (CAD)',
'amount_cad':'Fee component (CAD)','amount':'Amount in stated currency','total_cad':'Partial scenario total (CAD)',
'weekly_basket_cad':'Weekly reference food basket (CAD)','monthly_basket_derived_cad':'Derived monthly food basket (CAD)','reference_family_size':'Reference family size',
'annual_cad':'Annual threshold (CAD)','monthly_cad':'Monthly threshold (CAD)','maximum_cad':'Conditional maximum (CAD)','advertised_maximum_cad':'Advertised maximum (CAD)',
'monthly_fixed_water_cad':'Fixed water charge per month (CAD)','water_per_cubic_metre_cad':'Water per cubic metre (CAD)',
'cmhc_published_rent_categories':'Published CMHC rent categories','cmhc_good_or_better_rent_categories':'CMHC good-or-better categories',
}
TEXT_FIELDS={'description':'Details','bedrooms':'Bedrooms','currency':'Currency','applicable_period':'Applicable period','tax_treatment':'Taxes','notes':'Notes','status':'Source status','scope':'Scope','use':'Interpretation','budget_treatment':'Budget treatment','conditions':'Conditions','excluded':'Excluded costs','excludes':'Excluded costs','eligibility_status':'Eligibility','gap':'Research gap','next_action':'Still needed','geography_match_status':'Geography','family_size_label':'Household size','component':'Basket component','rent_quality':'Survey reliability','minimum_scores':'Minimum test scores','validity_years':'Test validity in years','exception':'Policy exception','components_cad':'Scenario components (CAD)','language_exemption_note':'Language evidence','specific_note':'Country document guidance'}

def display_value(value):
    if value is None:return 'Not published / needs confirmation'
    if isinstance(value,bool):return 'Yes' if value else 'No'
    if isinstance(value,list):return '; '.join(str(v) for v in value)
    if isinstance(value,dict):return '; '.join(str(k)+': '+display_value(v) for k,v in value.items())
    return str(value).replace('_',' ')

def present(name,row):
    location=row.get('province_or_territory') or row.get('province') or CODES.get(row.get('province_code',''),'') or row.get('country','')
    title=next((row.get(k) for k in ['community','source_csd_name','source_area','program','description','name','test','source_region','topic','source_file'] if row.get(k)),DATASETS[name][0])
    measures=[{'label':label,'value':display_value(row[key])} for key,label in MEASURES.items() if key in row]
    notes=[{'label':label,'value':display_value(row[key])} for key,label in TEXT_FIELDS.items() if key in row and row[key] not in ('',None,[],{})]
    if row.get('pt_eligible') is False:
        notes.insert(0,{'label':'Physiotherapist eligibility','value':'Excluded — do not include this program in a PT budget'})
        measures=[]
    if name=='housing_cmhc_rural_2025' and not row.get('use_for_reviewed_reference'):
        notes.insert(0,{'label':'Planning use','value':'Withheld or insufficient reliability — obtain a local quote'})
        measures=[m for m in measures if m['label']!='Average monthly rent (CAD)']
        measures.insert(0,{'label':'Average monthly rent (CAD)','value':'Not available as a reviewed reference'})
    urls=[row.get('source_url') or row.get('url')]+row.get('source_urls',[])
    return {'title':title,'location':location,'period':row.get('reference_period') or row.get('reference_month') or row.get('survey_year') or row.get('year') or row.get('applicable_period') or '', 'reviewed':row.get('reviewed_on') or row.get('retrieved_on') or row.get('source_updated_on') or snapshot(name).get('compiled_on',''), 'measures':measures,'notes':notes,'sources':list(dict.fromkeys(u for u in urls if isinstance(u,str) and u.startswith('https://')))}

def library(request):
    name=request.GET.get('collection','housing_cmhc_rural_2025')
    if name not in DATASETS:name='housing_cmhc_rural_2025'
    query=request.GET.get('q','').strip()[:100];province=request.GET.get('province','')
    rows=[]
    for row in records(name):
        item=present(name,row)
        if province and province.casefold() not in (item['location']+' '+str(item['title'])).casefold():continue
        if query and query.casefold() not in json.dumps(row,ensure_ascii=False).casefold():continue
        rows.append(item)
    from .forms import PROVINCES
    page=Paginator(rows,20).get_page(request.GET.get('page'))
    params=request.GET.copy();params.pop('page',None)
    return render(request,'career_mobility/research_library.html',{'collections':DATASETS,'collection':name,'collection_title':DATASETS[name][0],'collection_note':DATASETS[name][1],'query':query,'province':province,'provinces':PROVINCES,'page':page,'filter_query':params.urlencode(),'compiled_on':snapshot(name).get('compiled_on','2026-10-20')})

def licence_references(province=None):
    rows=records('licensing_fees')
    return [present('licensing_fees',row) for row in rows if not province or row.get('province_or_territory')==province]

def international_references(profile):
    # Existing and Quebec files must not be quoted a new general-pathway total.
    if profile.destination_province=='Quebec' or profile.application_history!='new':return []
    from .country_content import get_country
    if profile.country_of_education.casefold()=='canada':return []
    country=get_country(profile.country_of_education)
    examples=records('international_fee_scenarios')
    return examples if country and country['preapproved'] else examples[:1]

@lru_cache(maxsize=1)
def rural_housing_references():
    rows=[]
    for collection in ('housing_cmhc_rural_2025','housing_alberta_rural_2025'):
        for index,row in enumerate(records(collection)):
            if row.get('bedrooms') not in ('2_bedroom','2_bedrooms') or row.get('monthly_rent_cad') is None:continue
            if collection=='housing_cmhc_rural_2025' and not row.get('use_for_reviewed_reference'):continue
            if collection=='housing_alberta_rural_2025' and row.get('small_universe_flag'):continue
            rows.append({'id':collection+':'+str(index),'community':row.get('source_csd_name') or row.get('community'),'province':row['province'],'amount':row['monthly_rent_cad'],'period':str(row['survey_year']),'source':row['source_url'],'basis':'2025 survey average, two bedrooms; source geography must be checked','provider':'CMHC' if collection=='housing_cmhc_rural_2025' else 'Alberta'})
    for index,row in enumerate(records('housing_national_2025')):
        if row.get('bedrooms')!='Two bedroom units' or row.get('monthly_rent_cad') is None or row.get('source_status'):continue
        area=row['source_area'];community,sep,province=area.rpartition(', ')
        if not sep:continue
        rows.append({'id':'housing_national_2025:'+str(index),'community':community,'province':province,'amount':row['monthly_rent_cad'],'period':str(row['year']),'source':row['source_url'],'basis':'2025 survey average, two bedrooms; exact published source area','provider':'CMHC / Statistics Canada'})
    return sorted(rows,key=lambda r:(r['province'],r['community'],r['provider']))
