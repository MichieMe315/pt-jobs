from django.db import migrations


def seed(apps, schema_editor):
    Product = apps.get_model('career_mobility', 'DigitalProduct')
    items = [
        ('exercise-tracker', 'My Physio Exercise Tracker', 'Patient worksheets',
         'One printable weekly page with room for four prescribed exercises, daily checkboxes and notes to bring to your next appointment.'),
        ('appointment-notes', 'Questions for My Physiotherapist', 'Patient worksheets',
         'Two printable pages: a question sheet for planning your appointment and a notes sheet for recording the plan you discuss.'),
        ('practice-planner-2027', '2027 Physio Practice Planner', 'Practice planners',
         'Sixteen US Letter pages: a linked month index, 12 dated monthly calendars, and reusable weekly priorities, hours and shifts, and professional learning and renewal logs.'),
    ]
    for slug, title, category, description in items:
        Product.objects.get_or_create(slug='ptjc-' + slug, defaults={
            'title': title, 'category': category, 'short_description': description,
            'description': description + ' Digital PDF. No physical item will be shipped.',
            'audience': 'both', 'kind': 'file', 'download': f'bundled/{slug}.pdf',
            'is_published': False,
        })


class Migration(migrations.Migration):
    dependencies = [('career_mobility', '0022_checkout_payment_state')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
