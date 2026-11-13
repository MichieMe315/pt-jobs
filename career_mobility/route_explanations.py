"""Plain-language summaries of the route selected from the candidate's answers."""
def explain(profile,plan):
    country=profile.country_of_education;destination=plan['destination'];code=plan['route_code']
    authority=plan.get('authority') or {}
    regulator=authority.get('name') or ('your destination regulator' if destination!='Undecided' else 'the regulator where you decide to practise')
    capr='Canadian Alliance of Physiotherapy Regulators (CAPR)'
    if code=='preapproved':
        title='Your route: pre-approved qualifications assessment'
        intro=f'The {capr} checks your education and professional registration before you can take Canada’s physiotherapy examination. {country} is on its pre-approved list, so eligible applicants use a streamlined document review rather than the comparability assessment route.'
        conditions=f'You need a recognized physiotherapy degree from {country}. If you graduated more than two years before applying to CAPR, you need current registration there with no restrictions. If you graduated within two years of applying to CAPR, you do not have to be registered already. You must still meet the rules to register as a physiotherapist without restrictions in your education country. CAPR checks this with that country’s regulator; graduation alone does not establish eligibility. An expired registration is not the same as current registration. CAPR checks your evidence and decides whether you qualify.'
        steps=[('Prepare your application','Collect identity, academic and registration records, and complete an approved Canadian healthcare course.'),('CAPR reviews your qualifications','Submit the pre-approved application. CAPR checks the required evidence and confirms your examination eligibility.'),('Pass the Canadian examination','The Canadian Physiotherapy Examination (CPTE) assesses readiness for entry-level practice. Pre-approved assessment does not exempt you from this examination.'),('Apply for provincial registration',f'After meeting the assessment and exam requirements, apply to {regulator}. Your provincial registration is the authorization to practise.')]
    elif code=='comparability':
        title='Your route: qualifications and comparability assessment'
        intro=f'{capr} first checks your degree, clinical education and required documents. The comparability process then assesses how your knowledge and skills compare with Canadian entry-level physiotherapy standards.'
        conditions='Your assessment result determines the next step. Additional education or assessment may be required before examination eligibility.'
        steps=[('Prepare the required evidence','Arrange the education report, supporting documents, language evidence when needed, and an approved Canadian healthcare course.'),('Complete the assigned assessment','Follow CAPR’s qualifications assessment and Physiotherapy Evaluation Tool (PET) instructions. Use your result to identify any additional requirements.'),('Complete the examination requirements','Apply for the CPTE after CAPR confirms eligibility.'),('Apply for destination registration',f'Submit the evidence required by {regulator} and obtain registration before practising.')]
    elif code=='existing':
        title='Your route: continue your existing assessment application'
        intro='Use the route and outstanding-document list assigned to your existing CAPR application. A new policy does not automatically move your file into a different assessment process.'
        conditions='Keep your application reference and latest correspondence. Confirm your assigned route before paying for another assessment.'
        steps=[('Check your latest CAPR instructions','Identify the next outstanding document, assessment or result.'),('Complete the remaining requirements','Use the requirements assigned to your own file.'),('Apply to your destination regulator',f'Confirm the examination evidence and registration requirements with {regulator}.')]
    elif code=='registration-check':
        title='First confirm whether you qualify for the pre-approved route'
        intro=f'{country} is on CAPR’s pre-approved education list, but the registration status you selected does not confirm unrestricted registration there.'
        conditions='Applicants generally need current unrestricted registration where they trained. Recent graduates applying within two years may use eligibility for unrestricted registration. Expired registration does not establish current eligibility.'
        steps=[('Confirm your registration or recent-graduate eligibility','Ask CAPR which evidence it needs for your circumstances.'),('Use the route CAPR confirms','Then prepare the documents and budget for that route.'),('Complete examination and destination registration','Assessment approval alone is not a licence to practise.')]
    elif code=='quebec':
        title='Your route: Quebec equivalence and registration'
        intro='The Ordre professionnel de la physiothérapie du Québec (OPPQ) reviews your qualification and decides how it compares with Quebec’s requirements.'
        conditions='OPPQ may assign additional courses, placements or assessments. Use its individual decision and French-language requirements.'
        steps=[('Apply for an equivalence review','Submit OPPQ’s required documents.'),('Complete your assigned requirements','Follow the courses, assessments and language conditions in your decision.'),('Obtain your Quebec permit','Confirm approval and any conditions before practising.')]
    elif code=='employer-credentials':
        title='Your route: employer credential requirements'
        intro='Northwest Territories and Nunavut do not have a separate territorial physiotherapy regulator listed in the national directory. The hiring organization must confirm which Canadian registration it accepts.'
        conditions='Get the employer’s requirements in writing before choosing an assessment route or paying registration fees.'
        steps=[('Confirm accepted credentials','Ask which Canadian registration and standing evidence the employer requires.'),('Meet the accepted jurisdiction’s requirements','Complete any required assessment, examination and registration.'),('Complete employer onboarding','Confirm insurance and permission to begin the role.')]
    else:
        title='Your route: Canadian-educated registration'
        intro=f'Use {regulator}’s instructions for graduates of Canadian physiotherapy programs.'
        conditions='Your examination history and intended registration category determine the application requirements.'
        steps=[('Confirm examination evidence','Check the accepted examination results for your category.'),('Apply for registration','Submit the regulator’s required evidence and fees.'),('Confirm approval','Check registration and any conditions before practising.')]
    return {'title':title,'intro':intro,'conditions':conditions,'steps':[{'title':a,'detail':b} for a,b in steps]}
