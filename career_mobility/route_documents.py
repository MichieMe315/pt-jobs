"""Tasks based on the applicable assessor route, rather than nationality."""
BASE='https://alliancept.org/new-comparability-pathway/'
COMPARABILITY=BASE+'comparability-pathway-for-most-internationally-educated-physiotherapists/comparability-pathway-document-requirements/'
PREAPPROVED=BASE+'comparability-pathway-pre-approved-pathway/comparability-pathway-documents/'

def document_tasks(profile,plan):
 code=plan['route_code'];country=plan['country'] or {};name=profile.country_of_education
 if code=='employer-credentials':
  return [{'title':'Confirm the credentials accepted by your employer','action':'Get the hiring organization’s written requirements for Canadian registration, qualification records and professional standing. Then request the documents that organization and the accepted regulator require.','sender':'Your employer and the accepted Canadian regulator confirm the recipients.','source':'https://www.cicic.ca/938/physiotherapists.canada?id=53'}]
 if code in ('quebec','canadian','existing','registration-check'):
  return [{'title':'Use the document list assigned to your file','action':'Keep the current instructions and application reference from '+('OPPQ' if code=='quebec' else 'your destination regulator' if code=='canadian' else 'CAPR')+'. Do not order a new assessment report until the receiving authority confirms the route.','sender':'Your assessor or regulator confirms the list.','source':plan.get('authority',{}).get('url','https://alliancept.org/') if plan.get('authority') else 'https://alliancept.org/'}]
 source=PREAPPROVED if code=='preapproved' else COMPARABILITY
 tasks=[{'title':'Identity and name changes','action':'Prepare valid government identity evidence. Include legal name-change evidence when your academic name differs.','sender':'You upload the required evidence to CAPR.','source':source}]
 if code=='preapproved':
  tasks.append({'title':'Official academic records from '+name,'action':(country.get('action_guide',{}).get('prepare','Ask your school to deliver the required records through CAPR’s Institution Portal or approved delivery channel.')+' '+country.get('action_guide',{}).get('delivery','')),'sender':'The school sends official records.','source':source})
 else:
  tasks.append({'title':'WES education report for your '+name+' qualification','action':'Check your exact institution and credential in WES requirements. Arrange the ICAP Document-by-Document report for CAPR and enter the WES reference in your CAPR file. If WES cannot assess your institution, contact CAPR before paying.','sender':'WES releases the report and included school records to CAPR.','source':source})
 if country.get('school_internship_required') and code!='preapproved':
  tasks.append({'title':'School-issued internship completion certificate','action':'Request the certificate from your physiotherapy school and upload it to CAPR. A hospital or employer certificate is not the required school record.','sender':'Your physiotherapy school issues it; you upload the copy.','source':source})
 if not country.get('language_education_exemption'):
  tasks.append({'title':'Language results, when required','action':'Arrange official result delivery from the testing agency and add the report reference to your CAPR file.','sender':'The testing agency releases results to CAPR.','source':source})
 tasks.append({'title':'Complete an approved Canadian healthcare course','action':'This online course explains Canada’s healthcare system and the physiotherapist’s role within it. CAPR requires it for pre-approved applicants as well, including those educated in '+name+'. Complete one approved course before CAPR begins assessing your application. The current options are offered by the University of Toronto and the University of Alberta.','sender':'The university sends your completion result to CAPR. Give the university your CAPR client reference.','source':source})
 return tasks
