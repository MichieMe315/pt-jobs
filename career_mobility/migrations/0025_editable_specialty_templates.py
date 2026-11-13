from django.db import migrations


PRODUCTS = [
    ('physio-wall-calendar-2027', '2027 Physiotherapy Photo Wall Calendar'),
    ('general-physio-journal', 'General Physiotherapy Journal'),
    ('pelvic-physio-journal', 'Pelvic Health Journal'),
    ('sports-physio-journal', 'Sports Rehabilitation Journal'),
    ('paediatric-physio-journal', 'Paediatric Physiotherapy Journal'),
    ('neuro-physio-journal', 'Neurological Rehabilitation Journal'),
    ('older-adults-physio-journal', 'Older Adult Rehabilitation Journal'),
    ('msk-physio-journal', 'Orthopaedic and Musculoskeletal Journal'),
    ('custom-physio-journal', 'Custom Specialty Journal'),
    ('vestibular-physio-journal', 'Vestibular Rehabilitation Journal'),
    ('cardiorespiratory-physio-journal', 'Cardiorespiratory Physiotherapy Journal'),
    ('oncology-physio-journal', 'Oncology Rehabilitation Journal'),
    ('hand-physio-journal', 'Hand and Upper Limb Rehabilitation Journal'),
    ('persistent-pain-physio-journal', 'Persistent Pain Rehabilitation Journal'),
    ('occupational-physio-journal', 'Occupational Rehabilitation Journal'),
    ('community-physio-journal', 'Community and Home Care Journal'),
]


def seed(apps, schema_editor):
    products = apps.get_model('career_mobility', 'DigitalProduct').objects.using(schema_editor.connection.alias)
    for key, title in PRODUCTS:
        slug = 'ptjc-' + key
        calendar = key == 'physio-wall-calendar-2027'
        description = (
            'Twelve editable months. Add a different photo to each month, upload your logo, set your clinic name and accent colour, and add dates and notes.'
            if calendar else
            'Five editable pages: a cover and four reusable planning sheets. Replace the cover photo and logo, set your name and colours, and edit the headings, prompts and notes.'
        )
        short_description = description
        description += ' Opens offline in a web browser. Save your editable project and print or export a PDF.'
        path = 'bundled/' + key + '.html'
        product, created = products.get_or_create(slug=slug, defaults={
            'title':title, 'category':'Practice planners' if calendar else 'Specialty journals',
            'short_description':short_description, 'description':description, 'audience':'both',
            'kind':'file', 'download':path, 'is_published':False,
        })
        if not created and product.download.name == 'bundled/' + key + '.pdf':
            products.filter(pk=product.pk, download=product.download.name).update(
                download=path, short_description=short_description, description=description,
            )


class Migration(migrations.Migration):
    dependencies = [('career_mobility', '0024_journal_and_photo_calendar')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
