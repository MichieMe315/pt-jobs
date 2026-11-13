from .country_content import get_country


def for_profile(profile, base):
    rows=dict(base);country=get_country(profile.country_of_education)
    if profile.destination_province=='Quebec':
        rows['education']='Review the Quebec equivalence route with OPPQ'
        rows['assessment']='Budget for the Quebec route and any prescribed assessment/training'
        rows['capr']='Confirm which assessments OPPQ requires for your qualification'
    elif profile.application_history in ('existing','after','unsure'):
        rows['capr']='Confirm the pathway already assigned to your existing CAPR file'
    elif country and country['preapproved']:
        rows['capr']='Check pre-approved education AND unrestricted registration/recent-graduate eligibility'
    else:
        rows['capr']='Review qualifications assessment, PET and outcome-specific steps for a new application'
    if country and country['school_internship_required']:
        rows['documents']='Request degree/transcript and a school-issued internship certificate; not a hospital certificate'
    if country and country['language_education_exemption']:
        rows['language']='Check the classroom AND clinical education conditions for a language exemption'
    elif country:
        rows['language']='Arrange an accepted language test unless another documented exemption applies'
    if profile.country_of_education.casefold()=='canada':
        rows['education']='Confirm the Canadian-educated applicant route for your destination'
        rows['capr']='Confirm the examination requirements for your Canadian qualification and application history'
        rows['assessment']='Budget for applicable examinations and registration; do not assume international credentialling applies'
    if profile.registered_in_education_country=='previous':
        rows['professional']='Request evidence of previous registration and confirm whether reinstatement or recent-graduate eligibility applies'
    elif profile.registered_in_education_country=='no':
        rows['professional']='Confirm how to document your professional status where no registration is held'
    return list(rows.items())
