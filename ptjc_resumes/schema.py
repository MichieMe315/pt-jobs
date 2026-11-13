"""Applicant-entered facts only. No eligibility scoring or applicant-role conversion."""
from django.core.exceptions import ValidationError
from django.core.validators import validate_email, URLValidator

PROVINCES = ['Alberta','British Columbia','Manitoba','New Brunswick','Newfoundland and Labrador','Northwest Territories','Nova Scotia','Nunavut','Ontario','Prince Edward Island','Quebec','Saskatchewan','Yukon']
PATHWAYS = ['Not selected','Comparability','Pre-Approved','Alternative Evaluation','Existing Standard file','Quebec process','Other or awaiting confirmation']
REGISTRATION = ['Not registered in Canada','Application in progress','Registration held — enter exact class and conditions']
ASSESSMENT = ['Not started','Preparing documents','Application submitted','Documents under review','Decision received — describe exact outcome','Not applicable / authority confirmation held']
PET = ['Not applicable / not confirmed','Not started','Scheduled','Completed — awaiting outcome','Comparable','Partially comparable','Not comparable','Remediation completed — outcome confirmed']
EXAM = ['Not applicable / not confirmed','Not yet eligible','Eligibility confirmed','Exam booked','Completed — awaiting result','Passed','Unsuccessful attempt — planning next step']
SOURCES = [
 {'label':'CAPR current credentialling routes','url':'https://alliancept.org/new-comparability-pathway/comparability-pathway-start-here/'},
 {'label':'CAPR Comparability assessment requirements','url':'https://alliancept.org/new-comparability-pathway/comparability-pathway-for-most-internationally-educated-physiotherapists/comparability-pathway-assessment-requirements/'},
 {'label':'Quebec international candidates','url':'https://oppq.qc.ca/en/become-a-member/international-candidates/'},
]
PALETTES = ('original', 'slate', 'navy', 'plum', 'grayscale', 'forest', 'teal', 'berry', 'clay', 'cobalt')
TYPEFACES = ('original', 'serif', 'sans', 'helvetica', 'times', 'mono', 'italic')
SCALARS = {'palette':12,'typeface':12,'accent_colour':7,'header_colour':7,'extra_heading':80,'extra_text':1200,'name':120,'email':180,'phone':80,'location':180,'profile_url':300,'summary':1800,'education_country':100,'destination':80,'pathway':100,'assessment':100,'assessment_detail':500,'pet':100,'pet_detail':500,'exam':100,'exam_detail':500,'exam_date':10,'canadian_registration':100,'regulator':160,'registration_class':160,'registration_number':80,'registration_conditions':500,'work_authorization':300,'relocation':300,'home_registration':500,'layout':30,'specialties':600,'practice_track':40,'target_role':110}
LISTS = {
 'education': {'degree':180,'institution':180,'country':100,'completed':80},
 'experience': {'role':160,'employer':180,'country':100,'location':180,'dates':100,'setting':180,'bullets':2500},
 'canadian_experience': {'role':160,'employer':180,'location':100,'dates':100,'setting':180,'bullets':2500},
 'placements': {'institution':180,'country':100,'location':180,'dates':100,'setting':180,'hours':20,'contribution':1500},
 'development': {'course':180,'provider':180,'completed':80},
 'languages': {'language':80,'proficiency':180,'evidence':200},
}
DEFAULT_ORDER = ['summary','status','experience','canadian_experience','education','placements','home_registration','development','languages','availability']

def normalize(payload):
    if not isinstance(payload, dict): raise ValidationError('Resume data must be an object.')
    out = {}
    for key, limit in SCALARS.items():
        value = payload.get(key, '')
        if not isinstance(value, str) or len(value)>limit: raise ValidationError(f'{key}: enter text of no more than {limit} characters.')
        if any(ord(c)<32 and c not in '\n\r\t' for c in value): raise ValidationError(f'{key}: invalid control character.')
        try:value.encode('utf-8')
        except UnicodeEncodeError:raise ValidationError(f'{key}: unsupported character encoding.')
        out[key] = value.strip()
    out['layout']=out['layout'] or 'classic'
    if out['layout'] not in ('classic','clinical','editorial','sidebar'):raise ValidationError('Choose one of the four resume designs.')
    out['palette'] = out['palette'] or 'original'
    if out['palette'] not in PALETTES:
        raise ValidationError('Choose a listed résumé colour.')
    out['typeface'] = out['typeface'] or 'original'
    if out['typeface'] not in TYPEFACES:
        raise ValidationError('Choose a listed résumé font.')
    import re
    if out['accent_colour'] and not re.fullmatch(r'#[0-9a-fA-F]{6}',out['accent_colour']):
        raise ValidationError('Choose a valid accent colour.')
    if out['header_colour'] and not re.fullmatch(r'#[0-9a-fA-F]{6}',out['header_colour']):
        raise ValidationError('Choose a valid header background colour.')
    for key, fields in LISTS.items():
        rows = payload.get(key, [])
        if not isinstance(rows,list) or len(rows)>20: raise ValidationError(f'{key}: no more than 20 entries.')
        result=[]
        for row in rows:
            if not isinstance(row,dict): raise ValidationError(f'{key}: invalid entry.')
            clean={}
            for name,limit in fields.items():
                val=row.get(name,'')
                if not isinstance(val,str) or len(val)>limit: raise ValidationError(f'{key}.{name}: enter text of no more than {limit} characters.')
                if any(ord(c)<32 and c not in '\n\r\t' for c in val): raise ValidationError(f'{key}.{name}: invalid control character.')
                try:val.encode('utf-8')
                except UnicodeEncodeError:raise ValidationError(f'{key}.{name}: unsupported character encoding.')
                clean[name]=val.strip()
            if key=='placements' and clean['hours']:
                try:
                    hrs=float(clean['hours'])
                    if not 0<=hrs<=100000: raise ValueError()
                except ValueError: raise ValidationError('Placement hours must be a non-negative documented number.')
            if any(clean.values()):result.append(clean)
        out[key]=result
    for key,values in [('destination',PROVINCES),('pathway',PATHWAYS),('canadian_registration',REGISTRATION),('assessment',ASSESSMENT),('pet',PET),('exam',EXAM)]:
        if out[key] and out[key] not in values: raise ValidationError(f'{key}: choose one of the listed options.')
    if out['exam_date']:
        from datetime import date
        try: date.fromisoformat(out['exam_date'])
        except ValueError: raise ValidationError('Choose a valid exam date.')
    if out['email']:
        try:validate_email(out['email'])
        except ValidationError:raise ValidationError('Enter a valid email address.')
    if out['profile_url']:
        try:URLValidator(schemes=['https','http'])(out['profile_url'])
        except ValidationError:raise ValidationError('Profile link must be a complete http or https URL.')
    order=payload.get('section_order',DEFAULT_ORDER)
    legacy=[k for k in DEFAULT_ORDER if k!='canadian_experience']
    if isinstance(order,list) and all(isinstance(k,str) for k in order) and sorted(order)==sorted(legacy):
        order=list(order);order.insert(order.index('experience')+1,'canadian_experience')
    if not isinstance(order,list) or not all(isinstance(k,str) for k in order) or sorted(order)!=sorted(DEFAULT_ORDER):raise ValidationError('Section order is invalid.')
    out['section_order']=order
    hidden = payload.get('hidden_sections', [])
    if not isinstance(hidden,list) or any(key not in DEFAULT_ORDER for key in hidden):
        raise ValidationError('Invalid section visibility.')
    out['hidden_sections'] = [key for key in DEFAULT_ORDER if key in hidden]
    photo = payload.get('portrait','')
    if not isinstance(photo,str) or len(photo)>40_000:
        raise ValidationError('Choose a smaller portrait.')
    from .cards import artwork
    out['portrait'] = artwork(photo)
    size = payload.get('portrait_size',64)
    if type(size) is not int or not 40 <= size <= 90:
        raise ValidationError('Choose a portrait size between 40 and 90.')
    out['portrait_size'] = size
    show=payload.get('show_availability',False)
    if not isinstance(show,bool):raise ValidationError('Availability visibility must be true or false.')
    details=payload.get('show_assessment_details',False)
    if not isinstance(details,bool):raise ValidationError('Assessment detail visibility must be true or false.')
    out['show_assessment_details']=details
    out['show_availability']=show
    return out

def completion_errors(d):
    errors=[]
    for key,label in [('name','Name'),('email','Email'),('education_country','Country of education'),('canadian_registration','Current Canadian registration status')]:
        if not d.get(key):errors.append(label+' is required before PDF export.')
    if not d.get('education') or not all(r.get('degree') and r.get('institution') and r.get('country') for r in d['education']):errors.append('Add your exact qualification, institution and education country.')
    if d.get('canadian_registration')==REGISTRATION[2] and not (d.get('regulator') and d.get('registration_class')):errors.append('Name the regulator and exact registration class when registration is held.')
    return errors

def status_lines(d):
    rows=[]
    if d.get('destination'):rows.append(('Intended destination',d['destination']))
    if d.get('show_assessment_details') and d.get('pathway') and d['pathway']!='Not selected':rows.append(('Assessment route',d['pathway']))
    if d.get('show_assessment_details') and d.get('assessment'):rows.append(('Credential assessment',d['assessment']+(' — '+d['assessment_detail'] if d.get('assessment_detail') else '')))
    if d.get('show_assessment_details') and d.get('pathway')=='Comparability' and d.get('pet') and d['pet']!='Not applicable / not confirmed':rows.append(('PET',d['pet']+(' — '+d['pet_detail'] if d.get('pet_detail') else '')))
    if d.get('show_assessment_details') and d.get('exam') and d['exam']!='Not applicable / not confirmed':rows.append(('Examination',d['exam']+(' · '+d['exam_date'] if d.get('exam_date') else '')+(' — '+d['exam_detail'] if d.get('exam_detail') else '')))
    reg=d.get('canadian_registration','')
    if reg==REGISTRATION[2]:reg=' | '.join(filter(None,[d.get('regulator'),d.get('registration_class'),('Registration '+d['registration_number']) if d.get('registration_number') else '',d.get('registration_conditions')]))
    if reg:rows.append(('Canadian registration',reg))
    return rows

EXAMPLE = {
    'name': 'Morgan Ellis', 'email': 'morgan.ellis@example.com', 'phone': '+1 613 555 0142',
    'location': 'Ottawa, ON', 'education_country': 'United Kingdom',
    'canadian_registration': 'Not registered in Canada',
    'summary': 'Physiotherapy graduate with experience in outpatient musculoskeletal rehabilitation and inpatient discharge planning. Comfortable adapting exercise programs to a patient’s goals, home environment and recovery stage.',
    'education': [{'degree': 'BSc (Hons) Physiotherapy', 'institution': 'Sample UK university', 'country': 'United Kingdom', 'completed': '2020'}],
    'experience': [{'role': 'Physiotherapist', 'employer': 'Sample outpatient rehabilitation clinic', 'location': 'Leeds', 'country': 'United Kingdom', 'dates': '2021–2025', 'setting': 'Musculoskeletal and post-operative rehabilitation',
                    'bullets': 'Adapted progressive loading programs for patients returning to work after lower-limb injury.\nDocumented changes in function and shared treatment plans with referring clinicians.\nCoached patients on pacing and home exercises using written and demonstrated instructions.'}],
    'specialties': 'Musculoskeletal rehabilitation, patient education, return-to-work planning',
    'development': [{'course': 'Motivational interviewing workshop', 'completed': '2024'}],
}
CANADIAN_EXAMPLE = {
    'name': 'Morgan Ellis', 'email': 'morgan.ellis@example.com', 'phone': '613 555 0142', 'location': 'Ottawa, ON',
    'summary': 'Outpatient clinician with experience in musculoskeletal care, post-operative rehabilitation and return-to-work planning. Builds practical home programs and communicates measurable functional goals to patients and referring providers.',
    'home_registration': 'Ontario · Independent practice · Sample registration EXAMPLE-024',
    'specialties': 'Exercise prescription, functional assessment, interdisciplinary care',
    'canadian_experience': [{'role': 'Physiotherapist', 'employer': 'Sample rehabilitation clinic', 'location': 'Ottawa, ON', 'dates': '2021–present',
        'bullets': 'Planned graded exercise for patients recovering from joint replacement and work injuries.\nReviewed progress with functional measures and adapted home programs to available equipment.\nCoordinated discharge goals and follow-up with the referring care team.'},
        {'role': 'Physiotherapist', 'employer': 'Sample community rehabilitation service', 'location': 'Kingston, ON', 'dates': '2019–2021',
         'setting': 'Home and community rehabilitation',
         'bullets': 'Assessed mobility and transfer needs in the home.\nAgreed on functional goals with patients and caregivers and adjusted plans at follow-up.\nShared equipment recommendations with the occupational therapy team.'}],
    'education': [{'degree': 'Master of Physical Therapy', 'institution': 'Sample Canadian university', 'country': 'Canada', 'completed': '2019'}],
    'development': [{'course': 'Clinical education and supervision workshop', 'completed': '2024'}, {'course': 'Clinical outcome measures workshop', 'completed': '2023'}],
}
