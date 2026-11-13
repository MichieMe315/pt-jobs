"""Product-specific pages for workbooks people complete in the browser."""

WORKBOOKS = {
    'resume-cover-letter-workspace': ('Résumé and cover letter workspace', (
        ('Résumé: contact and summary', ('Contact and registration', 'Enter your name, contact information and the registration status you actually hold.'), ('Professional summary', 'Describe the relevant patient population, setting and strengths you bring to this role.')),
        ('Résumé: evidence and qualifications', ('Employment and placements', 'Add your role, setting, dates and relevant contributions. Keep supervised placements distinct from employment.'), ('Education and professional learning', 'List qualifications, institutions, dates and relevant courses.')),
        ('Cover letter', ('Opening and fit', 'Name the role and explain why this employer or clinical setting is a fit.'), ('Evidence and close', 'Describe one relevant example, then close with your availability and contact details.')),
    )),
    'application-workspace': ('Physiotherapy application workspace', (
        ('Plan the application', ('Role requirements', 'Record the employer, role and requirements you can demonstrate.'), ('Application materials', 'List the documents to prepare, submission details and due date.')),
        ('Tailor your experience', ('Evidence to feature', 'Pick examples that match the role and note what you contributed.'), ('Follow-up plan', 'Record the application date, next action and follow-up date.')),
    )),
    'resume-review-workspace': ('Résumé review and personalization', (
        ('Review your draft', ('What you want to keep', 'Note the strongest sections and why they are relevant to the role.'), ('What you want to change', 'Identify vague wording, missing dates and qualifications that need clarification.')),
        ('Rewrite for a specific role', ('Target role', 'List the top requirements in the job posting.'), ('Revised examples', 'Rewrite the summary and two experience bullets using evidence you can support.')),
    )),
    'canadian-pt-relocation-guide': ('Canadian PT relocation workbook', (
        ('Compare two communities', ('Community A', 'Record the offer, housing cost, commute and expected start date.'), ('Community B', 'Use the same measures, including costs you will pay only once.')),
        ('Plan the move', ('Break-even and reserves', 'Record your expected monthly surplus, moving costs and the funds you need before starting.'), ('Registration and next actions', 'Note the regulator, registration dates, and what to confirm with the employer.')),
    )),
    'international-pt-pathway-guide': ('International PT pathway workbook', (
        ('Map your registration route', ('Destination and regulator', 'Record your intended province, regulator, and where you verified the process.'), ('Documents and milestones', 'Record outstanding requirements, deadlines and questions for the authority.')),
        ('Build a practical timeline', ('Budget and timing', 'List estimated costs, when you expect to pay them, and dependencies between steps.'), ('Work authorization questions', 'Record questions to verify separately with official immigration sources.')),
    )),
    'pt-salary-contractor-guide': ('Employee versus contractor workbook', (
        ('Compare the offers', ('Employee offer', 'Record gross pay, paid hours, benefits and the written offer date.'), ('Contractor offer', 'Record the fee split, billable rate, estimated visits, cancellations and unpaid time.')),
        ('Compare the costs', ('Expenses and unpaid time', 'List operating costs, insurance, vacation and other unpaid time you expect.'), ('Follow-up questions', 'Record which assumptions to verify before comparing the two offers.')),
    )),
    'candidate-interview-workbook': ('Candidate interview workbook', (
        ('Prepare for the clinic interview', ('Role and setting', 'What does the posting tell you about the team, patients and workload?'), ('Questions for the clinic', 'What do you want to know about support, scheduling or compensation?')),
        ('Build your examples', ('Clinical judgement', 'Describe the situation, your assessment, what you did and the outcome.'), ('Working with others', 'Choose an example of adapting your approach with a patient, family or colleague.')),
        ('After the interview', ('What you learned', 'Record what the clinic said and any details that still need checking.'), ('Follow-up', 'Note your next action and when you plan to take it.')),
    )),
    'career-workbook-files': ('Career workbook', (
        ('Achievement portfolio', ('Clinical example', 'Record the setting, the action you took and an outcome you can support.'), ('Evidence to keep', 'What feedback, measure or document supports the example?')),
        ('Résumé planning', ('Target role', 'Which requirements are most relevant to your experience?'), ('Experience to feature', 'List roles, qualifications and examples that demonstrate those requirements.')),
        ('Offer review', ('Terms to compare', 'Record pay basis, hours, caseload, expenses and supports.'), ('Questions before deciding', 'Which terms need clarification or confirmation in writing?')),
    )),
    'international-workbook-files': ('International planning workbook', (
        ('Document preparation', ('Documents to gather', 'Record the document, issuer and where it needs to go.'), ('Outstanding requests', 'Track requests sent, replies received and next follow-up dates.')),
        ('Budget', ('Estimated expenses', 'List costs, currency, expected payment dates and what you have confirmed.'), ('Budget changes', 'Track revised estimates and the amount you have set aside.')),
        ('Exam preparation', ('Study plan', 'Record the subjects, materials and practice schedule you will use.'), ('Progress review', 'Note what you practised, what improved and what needs another session.')),
        ('Registration route', ('Intended destination', 'Record the province, relevant regulator and your next confirmed step.'), ('Items to verify', 'Note questions to check with the appropriate regulator and when you checked them.')),
    )),
    'exercise-tracker': ('My physio exercise tracker', (
        ('My exercises this week', ('Exercise 1', 'Name, prescribed reps or time, and notes.'), ('Exercise 2', 'Name, prescribed reps or time, and notes.'), ('Exercise 3', 'Name, prescribed reps or time, and notes.'), ('Exercise 4', 'Name, prescribed reps or time, and notes.')),
        ('How I felt', ('Before my exercises', 'Note how you felt before starting.'), ('After my exercises', 'Note any changes or concerns to discuss at your next appointment.')),
    )),
    'appointment-notes': ('Questions for my physiotherapist', (
        ('Before the appointment', ('Symptoms and activities', 'Write down changes you want to discuss and the activities that are difficult.'), ('My questions', 'List your questions about symptoms, exercise and daily activities.')),
        ('Before I leave', ('Plan to remember', 'Write down the instructions and follow-up agreed at your appointment.'), ('Next visit', 'Record the date and anything to bring or track before then.')),
    )),
}


def worksheets(key):
    return [
        {'title': title, 'intro': '', 'fields': [
            {'label': label, 'prompt': prompt} for label, prompt in fields
        ]}
        for title, *fields in WORKBOOKS[key][1]
    ]
