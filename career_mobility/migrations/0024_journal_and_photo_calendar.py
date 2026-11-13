from django.db import migrations


def seed(apps, schema_editor):
    products = apps.get_model('career_mobility', 'DigitalProduct').objects.using(schema_editor.connection.alias)
    for slug, title, category, description in (
        ('paediatric-physio-journal', 'Paediatric Physiotherapy Journal', 'Practice planners',
         'Six fillable US Letter pages: a personalised cover and reusable sheets for participation goals, visit planning, play activities, family and school collaboration, and reflection.'),
        ('physio-wall-calendar-2027', '2027 Physiotherapy Photo Wall Calendar', 'Practice planners',
         'Twelve US Letter month pages, January to December 2027. Each month pairs an original physiotherapy image with a Sunday-start grid and fillable space for short notes.'),
    ):
        products.get_or_create(slug=f'ptjc-{slug}', defaults={
            'title': title, 'category': category, 'short_description': description,
            'description': description + ' Digital PDF. No physical item will be shipped.',
            'audience': 'both', 'kind': 'file', 'download': f'bundled/{slug}.pdf', 'is_published': False,
        })


class Migration(migrations.Migration):
    dependencies = [('career_mobility', '0023_printable_collection')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
