"""Source-linked destination preparation, reviewed 21 October 2026.
Tasks say what to confirm; a task does not confer eligibility or permission to practise.
"""
DESTINATIONS={
'Alberta':{'url':'https://www.cpta.ab.ca/for-applicants/educated-outside-canada/general-register/','note':'New provisional admissions closed after 30 September 2026. Existing provisional registrants must check continuity and limits.','tasks':['Check General Register eligibility and the CPTE requirement for new applicants','Arrange regulatory history reports from relevant jurisdictions; check the 90-day validity window','Confirm jurisprudence, liability insurance and practice-currency requirements']},
'British Columbia':{'url':'https://chcpbc.org/applicants/physical-therapy/','note':'CHCPBC directs internationally educated applicants to contact licensure before starting an application.','tasks':['Contact CHCPBC licensure before starting the application','Confirm full versus provisional eligibility and the evidence required for your category']},
'Manitoba':{'url':'https://manitobaphysio.com/','note':'Use the College registration policies for the intended practice location.','tasks':['Confirm the applicable register and current application documents with CPM','Review the College transition-to-practice guide and ongoing professional obligations']},
'Saskatchewan':{'url':'https://www.scpt.org/site/iept?nav=sidebar','note':'Review SCPT international applicant and CPTE transition guidance together.','tasks':['Confirm the SCPT registration route and current examination transition rules','If considering provisional practice, confirm employer, supervisor and examination-registration conditions']},
'Ontario':{'url':'https://collegept.org/how-to-become-a-physiotherapist/how-to-apply/','note':'The College separates internationally educated applicants, examination requirements and registration categories.','tasks':['Confirm the current examination requirement for your application history','Confirm registration category eligibility; do not assume resident practice is available','Check the College application evidence and authorization before beginning PT practice']},
'Quebec':{'url':'https://oppq.qc.ca/','note':'OPPQ determines equivalence and any individual conditions. Do not assume the general CAPR route replaces this decision.','tasks':['Request the OPPQ equivalence application instructions for your qualification','Confirm French-language evidence and any prescribed courses, placements or assessments','Obtain the individual equivalence decision before treating requirements as finalized']},
'New Brunswick':{'url':'https://cptnb.ca/language/en/international-registrations/','note':'Use the current international registration instructions and confirm current examination requirements.','tasks':['Review CPTNB international applicant forms and the current CPTE instructions','Confirm required supporting documents and payment before submitting the online application']},
'Nova Scotia':{'url':'https://nsphysio.com/registration/overview/internationally-educated-applicants','note':'The current registration pages identify the Nova Scotia Regulator of Physiotherapy.','tasks':['Confirm credentialling and language requirements before applying','Check international criminal-record evidence requirements','If considering a conditional resident licence, confirm the current policy and supervision conditions']},
'Newfoundland and Labrador':{'url':'https://nlcpt.com/new-applicants-registration/','note':'Some international applicant pages retain older PCE wording. Confirm the current examination transition directly with NLCP.','tasks':['Resolve the PCE/CPTE wording with NLCP for your application date','Use the current registration-year form and confirm fee components']},
'Prince Edward Island':{'url':'https://www.peicpt.com/registration','note':'The current registration page is the starting source; individual category and examination eligibility require confirmation.','tasks':['Confirm international applicant eligibility and current examination evidence','Confirm jurisprudence requirements and whether any partial-year fee applies']},
'Yukon':{'url':'https://yukon.ca/en/doing-business/professional-licensing/apply-physiotherapist-certificate','note':'Yukon has its own physiotherapist certificate application.','tasks':['Confirm full versus interim certificate eligibility through Yukon licensing','Check examination evidence and any employer or supervisor requirements for your category']},
'Northwest Territories':{'url':'https://www.hss.gov.nt.ca/en/services/professional-licensing','note':'Do not assume a separate territorial PT licence is issued. The employer must confirm the credentials accepted for the role.','tasks':['Ask the hiring organization which Canadian PT registration it accepts','Confirm professional standing, liability coverage and local onboarding before accepting a start date']},
'Nunavut':{'url':'https://www.gov.nu.ca/en/health','note':'Confirm the employer credential requirements directly; do not invent a territorial PT licensing application.','tasks':['Obtain written employer confirmation of accepted Canadian PT registration','Confirm liability coverage, scope, orientation and remote-practice support']},
}
for value in DESTINATIONS.values(): value['reviewed_on']='2026-10-21'

# General Register instructions checked against the linked College page.
DESTINATIONS['Alberta'].update(
 note='Alberta’s General Register requires assessment and approved clinical examination evidence, jurisprudence, patient-protection education and current liability insurance.',
 reviewed_on='2026-10-27',
 tasks=['Confirm approved clinical examination evidence','Complete jurisprudence and patient-protection education','Arrange criminal checks and regulatory history reports','Obtain current professional liability insurance'],
 step_details=[
  ('Check which approved clinical examination result your application needs. The College lists CPTE and approved alternative clinical examinations.','Your examination and assessment confirmations.'),
  ('Complete the College jurisprudence module and mandatory sexual abuse and sexual misconduct education. Keep both completion records.','Jurisprudence summary and education certificate.'),
  ('Arrange the required criminal checks and regulatory reports. Follow the instructions for your last 10 years of registration and professional work. Coordinate delivery: reports and checks have 90-day validity limits.','Reports received within the College’s validity periods.'),
  ('Arrange active personal liability insurance with CAD $5 million coverage per occurrence and annual policy period. A future-dated policy is not accepted.','Your current insurance certificate.')])

# Ontario first-time independent practice requirements checked 28 October 2026.
DESTINATIONS['Ontario'].update(
 reviewed_on='2026-10-28',
 note='Ontario’s new applicants use independent practice registration after the accepted examination. Provisional practice is closed to new applications.',
 tasks=['Provide the accepted examination result','Arrange regulatory history reports','Check the practice-currency requirement','Arrange professional liability insurance','Apply through the Ontario PT Portal','Confirm registration before starting patient care'],
 step_details=[
  ('Keep your CPTE pass result. If you completed earlier examinations, check which written and clinical result combination the College accepts for your file.','The accepted examination results for your application.'),
  ('Ask every regulator where you have been registered to send Ontario’s Regulatory History Form directly to the College. The forms must be dated within six months of your application.','Direct delivery confirmations from the issuing regulators.'),
  ('Check the College’s recent-examination or practice-hours condition. If neither applies, ask the Registration Team about review before submitting.','Your examination date or practice-hours record and any College instructions.'),
  ('Arrange liability insurance meeting the College’s requirements before providing patient care.','The insurance certificate and coverage dates.'),
  ('Create or sign in to the Ontario PT Portal. Submit the required evidence and application payment; respond to any request for missing information.','Your submitted application, receipt and outstanding-document messages.'),
  ('Check the College’s approval, registration number, conditions and registration fee before agreeing to a patient-care start date.','The registration confirmation and any practice conditions.')])

DESTINATIONS['New Brunswick'].update(
 reviewed_on='2026-10-28',
 note='Complete CAPR’s qualification assessment, pass the CPTE, then apply to CPTNB for full registration.',
 tasks=['Complete the qualification assessment with CAPR','Pass the Canadian Physiotherapy Examination','Submit the CPTNB registration application'],
 step_details=[
  ('Follow the CAPR assessment route that applies to your education and registration history. Keep its assessment decision and examination eligibility confirmation.','CAPR assessment outcome and eligibility correspondence.'),
  ('After eligibility is confirmed, complete the CPTE. CPTNB counts previous unsuccessful Canadian clinical-exam or alternative-assessment attempts toward its three-attempt limit.','The accepted examination result and your examination history.'),
  ('Use CPTNB’s online registration application after passing the CPTE. Submit its supporting documents and the applicable registration fees; respond to any requests for missing information.','Your application receipt and CPTNB registration confirmation.')])
