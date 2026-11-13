"""Fields for the interactive versions of the PTJC planning products."""

PLANNERS = {
    'planning-spreadsheet': {
        'title': 'PTJC Planning Workbook',
        'description': 'Track costs, documents, study, applications and offers. Amounts are estimates.',
        'sheets': {
            'Budget': ['Cost item', 'Group', 'Quantity', 'Unit price', 'Currency', 'CAD per unit', 'CAD extras', 'Month', 'Quote source and date'],
            'Cash Plan': ['Month', 'Inflows CAD', 'Living CAD'],
            'Documents': ['Document ID', 'Requirement', 'Required sender', 'Status', 'Follow-up date', 'Accepted date', 'Evidence or source'],
            'Placements': ['Placement ID', 'Institution', 'Setting', 'Start date', 'End date', 'Documented hours', 'Evidence reference'],
            'Study Plan': ['Session date', 'Official content area', 'Practice task', 'Planned minutes', 'Completed minutes', 'What to revisit'],
            'Error Review': ['Gap ID', 'Reasoning or knowledge gap', 'Corrective resource', 'Next practice action', 'Review date', 'Status'],
            'Applications': ['Record ID', 'Employer and role', 'Type', 'Current status', 'Next action', 'Due date', 'Eligibility or conditions'],
            'Offer Compare': ['Employer', 'Pay basis', 'Hourly CAD', 'Paid hours/week', 'Paid weeks/year', 'Written annual CAD', 'Cancellations and charting', 'Mentorship and conditions'],
        },
    },
    'practice-planner-2027': {
        'title': '2027 Physio Practice Planner',
        'description': 'Plan your month, set weekly priorities and track your hours and professional learning.',
        'calendar': 2027,
        'sheets': {
            'Weekly priorities': ['Week beginning', 'Priority', 'Next action', 'Due date', 'Status'],
            'Hours and shifts': ['Date', 'Setting', 'Start time', 'End time', 'Break minutes', 'Notes'],
            'Learning and renewal': ['Activity', 'Provider', 'Date', 'Hours', 'Renewal date', 'Evidence or notes'],
        },
    },
}
