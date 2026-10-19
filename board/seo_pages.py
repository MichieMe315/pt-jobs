"""Curated search landing pages; listing matches are explicit and never invented."""
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from .models import Job

# Copy is editorial, not an assertion that a matching vacancy is currently available.
TOPICS = {
 'locum': ('Locum physiotherapy jobs in Canada', 'Cover a defined period while keeping the details clear.', ['locum'], 'locum', [
 ('What does a locum role involve?', 'Locum positions provide temporary cover. The posting should explain the dates, patient mix, expected hours and handover arrangements. A role may cover leave or a short-term gap; confirm the actual reason and duration with the employer.'),
 ('What should you clarify before accepting?', 'Ask about the compensation basis, cancellation terms, documentation access, orientation, scheduling and who supports clinical handover. If travel or accommodation is mentioned, ask what is covered and how it is arranged.'),
 ('How do you compare locum opportunities?', 'Compare the full commitment, including preparation, travel, accommodation and administrative time. Confirm the registration requirements for the province where you would practise. Each posting and employer sets its own requirements.')]),
 'travel': ('Travel physiotherapy jobs in Canada', 'Explore roles that explicitly mention travel or travel assignments.', ['travel physiotherapist','travel physiotherapy','travel pt','travel assignment'], None, [
 ('How are travel roles different?', 'Travel positions can involve a time-limited assignment away from your usual home or work between communities. Not every role outside a large city is a travel position. Read the location and work arrangement in each listing.'),
 ('What belongs in the assignment details?', 'Confirm the worksite, length of the assignment, hours, orientation and clinical support. Ask whether travel time, accommodation, transport and return travel are paid for, reimbursed or arranged independently.'),
 ('What should you verify before moving?', 'Check provincial registration, the employer and the written terms before making travel commitments. Relocation assistance and ongoing travel reimbursement are different benefits; clarify which is offered.')]),
 'rural': ('Rural physiotherapy jobs in Canada', 'Explore postings that describe rural, remote or northern practice.', ['rural','remote community','northern community','northern ontario','northern bc'], None, [
 ('What might rural practice involve?', 'A rural role may offer a broad caseload, community-based care and collaboration with a smaller local team. Work settings differ considerably. Ask the employer which services are delivered on site and how referrals and escalation work.'),
 ('How much support is available?', 'Ask who provides clinical supervision, how mentoring is scheduled and which other disciplines are available. Clarify coverage during leave, access to equipment, professional development and the limits of the expected role.'),
 ('What should you ask about relocation?', 'Discuss housing, transport, relocation assistance and the expected length of commitment. Check the terms of any incentive, including repayment conditions. A rural listing does not automatically include accommodation or financial assistance.')]),
 'sports': ('Sports physiotherapy jobs in Canada', 'Find postings that mention sports rehabilitation and active patients.', ['sport','sports','athlete','athletes','athletic'], None, [
 ('What work might a sports role include?', 'Sports-focused roles may include musculoskeletal rehabilitation, exercise prescription and return-to-activity planning. Ask about the actual patient mix rather than assuming the clinic works mainly with competitive athletes.'),
 ('Which responsibilities need clarification?', 'Check whether the role includes clinic appointments, team coverage, evening events or travel. Discuss facilities, rehabilitation space, documentation time and how care is coordinated with other professionals.'),
 ('How should you assess development opportunities?', 'Ask about case discussions, access to experienced clinicians and support for further education. Confirm which qualifications are essential and which are preferences in the individual posting.')]),
 'private-practice': ('Private practice physiotherapy jobs in Canada', 'Compare clinic roles by caseload, support and working arrangement.', ['private practice','private clinic'], None, [
 ('What should you compare between clinics?', 'Look at appointment lengths, expected caseload, administrative support, facilities and the opportunity to collaborate. A clear posting should explain what your working day involves and how patient bookings are managed.'),
 ('How do compensation arrangements differ?', 'Listings may describe hourly pay, a salary or a percentage split. Ask what is included in the stated rate, whether administrative time is covered, and which costs and benefits belong to each party.'),
 ('What matters for a new graduate?', 'Ask whether mentorship is scheduled, who delivers it and whether the time is protected. Clarify the approach to caseload growth, feedback and professional development. Do not assume mentorship is included unless the employer states it.')]),
 'advanced-practice': ('Advanced practice physiotherapy jobs in Canada', 'Explore postings that explicitly mention advanced or extended practice.', ['advanced practice','extended scope','consultant physiotherapist','physiotherapy consultant'], None, [
 ('What does advanced practice mean in a listing?', 'The title can describe different responsibilities across organizations. Read the actual duties, patient population, decision-making responsibilities and reporting relationships in each posting.'),
 ('Which experience should you check?', 'Employers may specify relevant clinical experience, additional education or particular competencies. Confirm the exact requirements directly; a job title alone does not establish the permitted scope of practice.'),
 ('How should you evaluate the role?', 'Discuss orientation, clinical governance, referral pathways, supervision and access to the wider care team. Ask how the organization measures the role and supports ongoing learning.')]),
}
CITIES = {
 'saskatoon': ('Saskatoon','Saskatchewan','SK'), 'london': ('London','Ontario','ON'),
 'parksville': ('Parksville','British Columbia','BC'), 'vancouver': ('Vancouver','British Columbia','BC'),
 'winnipeg': ('Winnipeg','Manitoba','MB'), 'hamilton': ('Hamilton','Ontario','ON'),
}

def landing_catalog():
    pages = []
    for slug,(title,subtitle,terms,job_type,sections) in TOPICS.items():
        pages.append({'slug': slug+'-physiotherapy-jobs-canada','title':title,'subtitle':subtitle,'terms':terms,'job_type':job_type,'sections':sections})
    regional_notes = {
        'saskatoon': ('Clarify the local service area', 'For a Saskatoon role, ask whether all appointments are at one city clinic or whether work includes community visits or travel beyond the city. Confirm how travel, documentation and access to the wider clinical team fit into the schedule.'),
        'london': ('Check the worksite in southwestern Ontario', 'For a London role, confirm the street address and whether the employer expects work across more than one clinic. Ask how your schedule is divided between sites and whether the stated compensation covers travel between appointments.'),
        'parksville': ('Plan for the Vancouver Island location', 'Parksville is on Vancouver Island. If you are moving to the area, clarify the actual worksite, start date and any relocation support before making commitments. Ask whether the role also includes nearby communities such as Qualicum Beach.'),
        'vancouver': ('Separate the city from the wider region', 'A Vancouver search can include employers describing a wider Metro Vancouver service area. Confirm the specific worksite, transit or parking arrangements and whether the job involves multiple locations. Check the individual listing rather than assuming all appointments are in Vancouver itself.'),
        'winnipeg': ('Compare the patient mix and service area', 'For a Winnipeg position, ask whether the work is based in a clinic, delivered in homes or split across community locations. Clarify the service area, travel expectations, appointment lengths and access to support between visits.'),
        'hamilton': ('Understand the Hamilton work arrangement', 'For a Hamilton role, confirm whether the worksite is a single clinic or a group of locations. Ask about evening or weekend appointments, the patient population and how you will work with the wider rehabilitation team. A familiar city name does not replace a clear address and schedule.'),
    }
    for slug,(city,province,abbr) in CITIES.items():
        pages.append({'slug': 'physiotherapy-jobs-'+slug,'title':f'Physiotherapy jobs in {city}, {province}','subtitle':f'Explore physiotherapist opportunities in {city} and compare the details that matter to your next role.', 'city':city,'province':province,'abbr':abbr,'sections':[regional_notes[slug],
            (f'Finding your next role in {city}',f'Use the current listings below to explore physiotherapy work in {city}. Employers may offer different settings and employment arrangements. Read each description for the exact worksite, patient mix, schedule and compensation.'),
            ('Compare the clinic and the working day', 'Ask about assessment and follow-up appointment lengths, administrative support, facilities, documentation time and clinical collaboration. Compare the stated caseload with your experience and the support available.'),
            ('Questions to ask before applying',f'Confirm the location, registration requirements for {province}, expected hours and employment arrangement. Ask about mentoring, continuing education and the process for building your caseload. Requirements and benefits vary by employer.'),
            ('If there are no current matches','Vacancies change as employers post and positions expire. Browse the wider province and the national job board, or register your interest through job alerts. A page being available does not mean there is a current vacancy in that city.') ]})
    return pages

PAGES = {p['slug']:p for p in landing_catalog()}

def matching_jobs(page):
    from .views import _active_jobs_qs
    qs = _active_jobs_qs().select_related('employer').filter(title__iregex=r'(^|[^A-Za-z])(physiotherapist(s)?|physiotherapy|physio|physical[\s-]+therapist(s)?)([^A-Za-z]|$)')
    if page.get('city'):
        import re
        qs = qs.filter(location__iregex=r'(^|[^A-Za-z])'+re.escape(page['city'])+r'([^A-Za-z]|$)')
        qs = qs.filter(Q(location__icontains=page['province']) | Q(location__iregex=r'(^|[,\s])'+page['abbr']+r'([,\s]|$)'))
        return qs.order_by('-posting_date','-id')
    import re
    terms = Q()
    for term in page['terms']:
        pattern=r'(^|[^A-Za-z])'+r'[\s-]+'.join(re.escape(word) for word in term.split())+r'([^A-Za-z]|$)'
        terms |= Q(title__iregex=pattern) | Q(description__iregex=pattern)
    if page.get('job_type'): terms |= Q(job_type=page['job_type'])
    return qs.filter(terms).order_by('-posting_date','-id')

def career_hub(request):
    return render(request,'board/career_hub.html',{'landing_pages':list(PAGES.values())})

def career_landing(request, slug):
    if slug not in PAGES: raise Http404
    page = PAGES[slug]
    return render(request,'board/career_landing.html',{'landing':page,'live_jobs':matching_jobs(page)[:30], 'related_pages':sorted([p for p in PAGES.values() if p['slug']!=slug], key=lambda p: (bool(p.get('city')) != bool(page.get('city')), p['title']))[:6]})
