from django.db import migrations
from django.db.models import Q


def revise(apps, schema_editor):
    products = apps.get_model('career_mobility', 'DigitalProduct').objects.using(schema_editor.connection.alias)
    products.filter(
        Q(description__icontains='after purchase') | Q(description__icontains='purchase finished PDF access'),
        slug='international-resume-builder-access',
    ).update(
        description=(
            'Build a résumé that shows your physiotherapy training and experience. Include your '
            'qualifications, supervised placements, registration status, and work in Canada and abroad. '
            'You can show assessment and examination milestones if relevant. Save your draft, preview '
            'the layout, and return to edit or download it from your account.'
        ),
    )


class Migration(migrations.Migration):
    dependencies = [('career_mobility', '0026_card_candidate_audience'), ('ptjc_resumes', '0004_resume_product_copy')]
    operations = [migrations.RunPython(revise, migrations.RunPython.noop)]
