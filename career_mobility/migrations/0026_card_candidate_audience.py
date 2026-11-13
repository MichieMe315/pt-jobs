from django.db import migrations


def expose_to_candidates(apps, schema_editor):
    Product = apps.get_model('career_mobility', 'DigitalProduct')
    Product.objects.using(schema_editor.connection.alias).filter(
        slug='international-business-card-builder-access', audience='international'
    ).update(audience='both')


class Migration(migrations.Migration):
    dependencies = [('career_mobility', '0025_editable_specialty_templates')]
    operations = [migrations.RunPython(expose_to_candidates, migrations.RunPython.noop)]
