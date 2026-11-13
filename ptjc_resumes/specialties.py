"""Canadian résumé writing prompts. Selection never asserts a credential."""
TRACKS = {
    'general': ('General physiotherapy', 'Lead with your practice setting, the patients you support and what your work helps them do.'),
    'pelvic': ('Pelvic health', 'Describe your relevant training and the populations you actually worked with. Explain your role in consent, education, follow-up and referral. List assessment skills only if trained and used.'),
    'sports': ('Sports rehabilitation', 'Name the sport or level, the injury or rehab phase and your role. Describe how you measured progress and communicated return-to-sport decisions.'),
    'paediatric': ('Paediatric physiotherapy', 'Name the age groups and settings you worked in. Describe a functional goal, how you adapted sessions and how you involved caregivers or school teams.'),
    'neuro': ('Neurological rehabilitation', 'Identify the population and setting. Describe a mobility or participation goal, the measure you used and your role in interdisciplinary care.'),
    'older-adults': ('Older adult rehabilitation', 'Describe your setting, the mobility or independence goals you supported and how you worked with families or care teams.'),
    'msk': ('Orthopaedic and musculoskeletal', 'Describe the caseload and how you assessed function, progressed exercise or supported return to work. Include measures you actually used.'),
    'custom': ('Another practice focus', 'Name the role or practice area you are targeting. Use experience, training and outcomes you can substantiate.'),
}

# Clearly fictional content for preview PDFs only. Never inserted into a draft.
EXAMPLES = {
    'pelvic': {
        'target_role': 'Physiotherapist, pelvic health',
        'specialties': 'Pelvic health rehabilitation, patient education, collaborative care',
        'summary': 'Physiotherapist with outpatient pelvic health experience supporting adults with bladder symptoms and persistent pelvic pain. Builds practical home plans around the activities patients want to return to and coordinates referrals when needs fall outside the clinic’s scope.',
        'setting': 'Outpatient pelvic health and rehabilitation',
        'bullets': 'Worked with patients to identify priorities for bladder habits, comfort during daily activities and return to exercise.\nUsed patient-reported measures to review progress and agreed on follow-up goals at each reassessment.\nCoordinated referrals and shared care updates with the referring team with patient consent.',
    },
    'sports': {
        'target_role': 'Physiotherapist, sport and active rehabilitation',
        'specialties': 'Field-sport rehabilitation, graded loading, functional testing',
        'summary': 'Outpatient physiotherapist supporting recreational and competitive athletes through injury rehabilitation. Uses functional testing, patient goals and sport demands to plan the transition from clinic exercise to practice and competition.',
        'setting': 'Sports rehabilitation and orthopaedic outpatient clinic',
        'bullets': 'Documented strength and movement measures over the course of rehabilitation and discussed changes with athletes.\nBuilt graded return-to-practice plans around position demands and access to equipment.\nCoordinated training modifications with coaches where athletes gave permission.',
    },
    'paediatric': {
        'target_role': 'Physiotherapist, paediatric rehabilitation',
        'specialties': 'Play-based rehabilitation, gross motor goals, caregiver coaching',
        'summary': 'Physiotherapist with experience supporting children and families in outpatient and community settings. Works with caregivers to set practical mobility and participation goals for home, school and play.',
        'setting': 'Community paediatric rehabilitation',
        'bullets': 'Adapted sessions and home activities around children’s interests and each family’s routines.\nRecorded changes in functional mobility and participation against family-selected goals.\nCollaborated with occupational therapists and school teams on practical access and participation strategies.',
    },
}
