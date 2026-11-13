from pathlib import Path
"""Shared public/saved planning rules. Unknown requirements remain confirmation tasks."""
from types import SimpleNamespace
from .checklists import for_profile
from .research import REGULATORS
from .country_content import get_country
from .forms import PROVINCES
import hashlib

BASE=[('education','Confirm the assessment route for your qualification'),('capr','Review assessment and examination requirements'),('language','Confirm accepted language evidence'),('documents','Request official education records'),('professional','Confirm professional standing evidence'),('assessment','Budget for assessment stages'),('province','Confirm destination requirements'),('fees','Confirm application and registration costs'),('immigration','Confirm Canadian work authorization separately'),('apply','Submit the required applications')]

def _original_build(profile):
    country=get_country(profile.country_of_education)
    province=profile.destination_province
    regulator=REGULATORS.get(province)
    route='Review the current comparability pathway'
    if profile.application_history=='existing': route='Review your existing assessment file'
    elif profile.application_history in ('unsure','after'): route='Confirm the pathway assigned to your application'
    elif country and country['preapproved']: route='Check pre-approved pathway eligibility and registration conditions'
    if province=='Quebec': route='Review the Quebec equivalence route with OPPQ'
    if profile.country_of_education.casefold()=='canada': route='Review the Canadian-educated applicant route with your destination authority'
    rows=[]
    for key,label in for_profile(profile,BASE):
        if key in ('province','fees','apply'):
            scope=hashlib.sha256(province.encode()).hexdigest()[:10]
            key=f'{key}_{scope}'
        rows.append({'key':key,'label':label,'stage':'Destination registration' if key.startswith(('province','fees','apply')) else 'Preparation'})
    if regulator:
        rows[6]['label']=f'Confirm the applicable registration category with {regulator[0]}'
        rows[7]['label']=f'Confirm {province} fees, required evidence and renewal dates'
        rows[9]['label']=f'Submit the {province} application after confirming eligibility'
    if province in ('Northwest Territories','Nunavut'):
        rows[6]['label']=f'Confirm {province} employer credential requirements and whether registration elsewhere in Canada is required'
        rows[7]['label']='Obtain written confirmation of applicable registration and employment costs'
        rows[9]['label']='Complete the employer credential review before beginning practice'
    from .destination_guidance import DESTINATIONS
    guidance=DESTINATIONS.get(province)
    if guidance:
        for index,task in enumerate(guidance['tasks']):
            rows.append({'key':f'local{index}','label':task,'stage':'Destination registration'})
    # Completion follows the meaning of a task, and reappears when returning to that route.
    for row in rows:
        original=row['key'].split('_')[0]
        scope=province if row['stage']=='Destination registration' else (profile.country_of_education+'|'+profile.application_history+'|'+profile.registered_in_education_country)
        if country:
            source_field={'education':'pathway_url','capr':'pathway_url','documents':'documents_url','language':'language_url','assessment':'fees_url'}.get(original)
            if source_field: row['source_url']=country[source_field]
        if original=='immigration':
            scope='shared'
            row['source_url']='https://www.canada.ca/en/immigration-refugees-citizenship.html'
        row['key']=original+'_'+hashlib.sha256((scope+'|'+row['label']).encode()).hexdigest()[:12]
        row['source_url']=row.get('source_url') or ((guidance['url'] if guidance else regulator[1] if regulator else '') if row['stage']=='Destination registration' else 'https://alliancept.org/')
    from .research_library import records,international_references
    licence_rows=[r for r in records('licensing_fees') if r['province_or_territory']==province]
    return {'licence_research':licence_rows,'cost_examples':international_references(profile),'guidance':guidance,'route':route,'steps':rows,'destination':province or 'Undecided','authority':{'name':regulator[0],'url':regulator[1]} if regulator else None,'country':country,'checklist_free':True}

def from_answers(data):
    country=' '.join(data.get('country','').split())[:100]
    province=data.get('province','')
    applied=data.get('applied','')
    registration=data.get('registration','')
    if len(country)<2 or province not in PROVINCES+['Undecided'] or applied not in ('not-applied','before','after','unsure') or registration not in ('yes','previous','no','unsure'):
        raise ValueError('Complete all four questions using the available options.')
    return SimpleNamespace(country_of_education=country,destination_province='' if province=='Undecided' else province,application_history={'not-applied':'new','before':'existing','after':'after','unsure':'unsure'}[applied],registered_in_education_country=registration)


def build(profile):
    plan=_original_build(profile)
    country=plan['country'];history=profile.application_history
    if profile.destination_province in ('Northwest Territories','Nunavut'):code='employer-credentials';route='Employer credential review and accepted Canadian registration'
    elif profile.destination_province=='Quebec':code='quebec';route='Quebec equivalence and registration'
    elif profile.country_of_education=='Canada':code='canadian';route='Canadian-educated registration'
    elif history in ('existing','after','unsure'):code='existing';route='Continue your existing assessment file'
    elif country and country['preapproved'] and profile.registered_in_education_country=='yes':code='preapproved';route='Pre-approved pathway: confirm your qualification and registration'
    elif country and country['preapproved']:code='registration-check';route='Confirm whether you meet the pre-approved registration conditions'
    else:code='comparability';route='Qualifications assessment and comparability pathway'
    plan.update(route=route,route_code=code)
    plan['country_note']=country.get('specific_note','') if country else ''
    if code=='employer-credentials':plan['country_note']='Confirm which Canadian registration and credentials the hiring organization accepts before choosing an assessment route or paying registration fees. The accepted jurisdiction determines those requirements.'
    elif code=='quebec':plan['country_note']='OPPQ assesses your qualification for Quebec and decides any additional education, clinical training and French-language requirements. Use the document instructions assigned to your equivalence file.'
    elif code=='canadian':plan['country_note']='Use your destination regulator’s Canadian-educated application instructions for your qualification, examination history and registration category.'
    details={
    'education':('Identify the assessment route','Compare your qualification and application history with the route shown above. Keep the written eligibility response or assessment decision.','Your qualification name, institution and application reference.'),
    'capr':('Open or continue your assessment file','Follow the instructions for your assigned route. If you have already applied, use your existing file before paying for another application.','Your application confirmation and the next action requested by the assessor.'),
    'language':('Prepare your language evidence','For physiotherapy education completed in '+profile.country_of_education+', plan for an accepted language test. CAPR also provides an exemption for applicants who completed all primary and secondary education in Canada. Confirm any applicable exemption and check the required score in each skill before booking. '+('Manitoba has additional language-policy provisions.' if profile.destination_province=='Manitoba' else '')+'','An exemption confirmation or accepted test results.'),
    'documents':('Request academic records','Ask your school for your degree, transcript and required clinical training records. Check who must send each record and how it must be delivered.','A document request log, delivery confirmations and accepted translations.'),
    'professional':('Obtain professional standing records','List every place where you have been registered. Ask the receiving authority which standing reports it needs and how recent they must be.','Registration history and reports sent by the issuing regulators.'),
    'assessment':('Plan assessment and examination costs','Use the budget tab to separate assessment, examination and destination costs. Add document services, language testing and any individually assigned education.','A budget with confirmed fees, dates and room for additional requirements.'),
    'province':('Confirm destination registration requirements','Ask the destination authority which registration category applies after your assessment and examinations. Confirm the required evidence before submitting an application.','The applicable category and a current application document list.'),
    'fees':('Confirm destination fees','Separate application, initial permit and renewal fees. Partial-year permits are alternatives to full-year permits, not extra fees to add automatically.','A dated fee schedule for the category and start date you intend to use.'),
    'immigration':('Confirm authorization to work in Canada','Check the work authorization that applies to your circumstances. Professional registration and permission to work are separate requirements.','Your work authorization and any conditions that affect your start date.'),
    'apply':('Submit the destination application','Check that the authority has received the required documents and payment. Wait for confirmation of registration before starting work as a physiotherapist.','Your registration confirmation, conditions and renewal date.')}
    for row in plan['steps']:
        key=row['key'].split('_')[0]
        title,detail,evidence=details.get(key,(row['label'],'Read the destination instructions and complete this requirement for your registration category. Keep the confirmation in your records.','Written confirmation that this requirement is complete.'))
        if not key.startswith('local'):row['label']=title
        row['detail']=detail;row['evidence']=evidence
        if key=='documents' and country and country['school_internship_required']:
            row['detail']+=' For '+country['name']+', request the internship completion certificate from your physiotherapy school. An employment or hospital-issued certificate does not replace that school record.'
        if code in ('quebec','canadian') and key in ('education','capr','language','documents','professional','assessment') and plan.get('authority'):
            row['source_url']=plan['authority']['url']
        if code=='employer-credentials' and key in ('education','capr','language','documents','professional','assessment'):
            row['source_url']='https://www.cicic.ca/938/physiotherapists.canada?id=53'
            row['detail']='Ask the hiring organization which Canadian registration, qualification records, language evidence and insurance it accepts. Use its written requirements and the accepted regulator’s instructions to decide which assessments, documents and fees apply.'
        if key=='documents' and code in ('quebec','canadian'):row['detail']='Request the academic records and supporting documents listed by '+('OPPQ for your equivalence file.' if code=='quebec' else 'the destination regulator for Canadian-educated applicants.')
        if key=='language' and code=='canadian':row['detail']='Use the destination regulator’s Canadian-educated requirements to confirm the language evidence you need.'
        if key=='language' and code=='quebec':row['detail']='Confirm the French-language evidence OPPQ requires for the permit you are seeking.'
        if key=='capr' and code=='quebec':row['detail']='Follow the OPPQ equivalence application instructions. The individual decision may require additional courses, placements or assessments.'
        if key=='capr' and code=='canadian':row['detail']='Confirm the examination and registration requirements for your Canadian qualification with the destination authority.'
        if key in ('province','fees','apply') and profile.destination_province in ('Nunavut','Northwest Territories'):
            row['label']={'province':'Confirm the employer credential requirements','fees':'Confirm accepted registration and related costs','apply':'Complete the employer credential review'}[key]
            row['detail']='Ask the hiring organization which Canadian PT registration it accepts. Obtain written confirmation of professional standing, insurance and onboarding requirements before agreeing to a start date.'
        if key=='language' and code not in ('quebec','canadian','employer-credentials') and country and country['language_education_exemption']:
            row['label']='Language test exemption'
            row['evidence']='Education records confirming where both classroom and clinical training were completed.'
            row['detail']='A CAPR language test is not required when both the classroom and clinical parts of your physiotherapy education were completed in '+profile.country_of_education+'. If part of your training was completed elsewhere, ask CAPR whether the exemption applies to that training.'
        if key=='capr' and code=='existing':
            row['detail']='Use the instructions and reference number for your existing CAPR file. Confirm your next outstanding action before starting a new application or paying another assessment fee.'
        if key=='professional' and profile.registered_in_education_country=='no':
            row['detail']='Tell the assessor that you have not held professional registration where you trained. Ask what evidence it accepts for your circumstances before requesting a standing report.'
        elif key=='professional' and profile.registered_in_education_country=='previous':
            row['detail']='Record where and when you were registered, including expired registrations. Ask the receiving authority which standing reports it needs from your previous regulators.'
        if key.startswith('local') and plan['guidance'] and plan['guidance'].get('step_details'):
            index=int(key[5:])
            if index<len(plan['guidance']['step_details']):row['detail'],row['evidence']=plan['guidance']['step_details'][index]
        row['stage']='Documents and language' if key in ('documents','language','professional') else row['stage']
    plan['cost_examples']=[]
    if code in ('comparability','preapproved'):
        from .research_library import records
        examples=records('international_fee_scenarios')
        plan['cost_examples']=[examples[1] if code=='preapproved' else examples[0]]
    # Published reviewed admin fees take precedence over the bundled snapshot.
    from .models import ProvincialLicenceFee
    active=ProvincialLicenceFee.objects.filter(is_published=True,province=profile.destination_province)
    plan['licence_research_from_admin']=active.exists()
    if plan['licence_research_from_admin']:plan['licence_research']=[{'description':f.description,'amount_cad':str(f.amount_cad) if f.amount_cad is not None else None,'applicable_period':f.applies_to,'reviewed_on':str(f.verified_on or ''),'source_url':f.source_url} for f in active]
    order={'Preparation':0,'Documents and language':1,'Destination registration':2}
    plan['steps'].sort(key=lambda s:order.get(s['stage'],3))
    for row in plan['steps']:
        if code in ('quebec','canadian','employer-credentials') and row['stage']!='Destination registration' and not row['key'].startswith('immigration_'):
            row['key']=row['key'].split('_')[0]+'_'+hashlib.sha256((code+'|'+row['key']).encode()).hexdigest()[:12]
    for index,row in enumerate(plan['steps'],1):row['number']=index
    plan['stages']=list(dict.fromkeys(s['stage'] for s in plan['steps']))
    from .countries import CODES
    code2=CODES.get(profile.country_of_education,'')
    plan['flag_code']=code2 if (Path(__file__).parent.parent/'static/career_mobility/flags'/(code2+'.svg')).is_file() else ''
    plan['flag']=''.join(chr(127397+ord(c)) for c in code2)
    for row in plan['licence_research']:
        for field in ('description','applicable_period'):
            if isinstance(row.get(field),str):row[field]=row[field].replace('â€“','–').replace('â€™',"'")
    plan['reviewed_on']=max(country['reviewed_on'] if country else '2026-10-21',(plan['guidance'] or {}).get('reviewed_on','2026-10-21'))
    from .route_documents import document_tasks
    plan['document_tasks']=document_tasks(profile,plan)
    concrete=[]
    for task in plan['steps']:
        if task['key'].startswith('documents_') and code in ('comparability','preapproved'):
            for item in plan['document_tasks']:
                if item['title'].startswith('Language results'):continue
                identity='Canadian practice course' if item['title']=='Complete an approved Canadian healthcare course' else item['title']
                key='record_'+hashlib.sha256((profile.country_of_education+'|'+profile.destination_province+'|'+code+'|'+identity).encode()).hexdigest()[:18]
                concrete.append({'key':key,'label':item['title'],'detail':item['action'],'evidence':item['sender'],'source_url':item['source'],'stage':'Documents and language'})
        else:concrete.append(task)
    if profile.destination_province in ('Ontario','New Brunswick'):
        concrete=[task for task in concrete if task['key'].split('_')[0] not in ('province','fees','apply')]
    plan['steps']=concrete
    for index,task in enumerate(plan['steps'],1):task['number']=index

    from .research_library import records
    plan['language_exempt']=bool(country and country.get('language_education_exemption') and code not in ('quebec','canadian','employer-credentials'))
    plan['language_policy']=records('international_language_policy')[0] if code not in ('quebec','canadian','employer-credentials') and not plan['language_exempt'] else None
    from .route_explanations import explain
    plan['explanation']=explain(profile,plan)
    # Explicit dated examples; never add mutually exclusive permit categories.
    examples_by_destination={
      'Ontario':[('Full-year independent practice example',114,648,'Initial approval is prorated by the College. Your actual certificate fee may be lower.')],
      'Alberta':[('Full registration year',125,805,'2026/2027 permit year.'),('Approval April 1–September 30',125,615,'Alternative partial-year permit; not an additional fee.')],
      'New Brunswick':[('Full-year practising registration',150,400,'2026 schedule.'),('Half-year practising registration',150,275,'Alternative partial-year registration.')],
      'Manitoba':[('Active register',200,913,'2026 schedule.'),('Active register after August 1',200,456.50,'Alternative partial-year active registration.'),('Examination Candidate register',200,863,'Alternative register; confirm eligibility.')],
    }
    if profile.destination_province == 'British Columbia' and not plan['licence_research_from_admin']:
        amounts={row['description']:row['amount_cad'] for row in plan['licence_research']}
        labels=('Full or provisional application','Full or provisional annual registration','Registration from October 1; half-year alternative')
        if all(amounts.get(label) is not None for label in labels):
            application,annual,half_year=(amounts[label] for label in labels)
            examples_by_destination['British Columbia']=[
                ('Full-year registration',application,annual,'Application plus the full-year registration fee.'),
                ('October 1 or later: half-year registration',application,half_year,'Application plus the half-year fee, if applicable. This replaces the full-year fee.'),
            ]
    from decimal import Decimal
    plan['registration_examples']=[]
    if not plan['licence_research_from_admin']:
        for label,application,permit,note in examples_by_destination.get(profile.destination_province,[]):
            total=Decimal(str(application))+Decimal(str(permit))
            plan['registration_examples'].append({'label':label,'application':application,'permit':permit,'total':total,'note':note})
    plan['listed_budget']=None
    if plan['cost_examples'] and plan['registration_examples']:
        assessment=Decimal(str(plan['cost_examples'][0]['total_cad']))
        option=plan['registration_examples'][0]
        plan['listed_budget']={'assessment':assessment,'registration':option['total'],'total':assessment+option['total'],'registration_label':option['label']}

    return plan

_original_answers=from_answers
def from_answers(data):
    from .countries import canonical
    values=data.copy();values['country']=canonical(data.get('country',''))
    return _original_answers(values)
