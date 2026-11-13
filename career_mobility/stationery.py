"""Editable print sizes and field sets for the practice stationery products."""

STATIONERY = {
    'appointment-card-designs': {
        'title': 'Appointment cards', 'size': [3.5, 2],
        'designs': [('clinical', 'Clinical'), ('community', 'Community'), ('editorial', 'Editorial')],
        'fields': [('heading', 'Heading', 'Your next appointment'), ('name', 'Practice name', ''),
                   ('date', 'Date label', 'Date'), ('time', 'Time label', 'Time'),
                   ('with', 'Clinician label', 'With'), ('note', 'Footer', 'To reschedule, call your clinic')],
    },
    'practice-postcards': {
        'title': 'Practice postcards', 'size': [6, 4],
        'designs': [('editorial', 'Editorial'), ('clinical', 'Clinical'), ('split', 'Photo split'), ('community', 'Community')],
        'fields': [('heading', 'Front headline', 'Welcome to our practice'), ('name', 'Practice name', ''),
                   ('body', 'Back message', ''), ('note', 'Contact details', '')],
    },
    'practice-prints': {
        'title': 'Practice prints', 'size': [8.5, 11],
        'designs': [('editorial', 'Editorial'), ('clinical', 'Clinical'), ('split', 'Photo split'), ('community', 'Community')],
        'fields': [('heading', 'Title', 'Movement matters'), ('name', 'Practice name', ''),
                   ('body', 'Message', ''), ('note', 'Footer', '')],
    },
    'practice-brand-assets': {
        'title': 'Practice brand assets', 'size': [8, 3],
        'designs': [('editorial', 'Wordmark'), ('split', 'Logo and text'), ('community', 'Centered banner')],
        'fields': [('heading', 'Practice name', 'Your practice'), ('name', 'Tagline', ''), ('note', 'Contact details', '')],
    },
}
