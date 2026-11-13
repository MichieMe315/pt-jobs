from django.db import migrations


def revise(apps, schema_editor):
    studios = apps.get_model('career_mobility', 'StorefrontStudio').objects.using(schema_editor.connection.alias)
    for key, old, new in (
        ('canadian-resume', 'Tailor your résumé to a Canadian role. Try all four designs.', 'Build and save a résumé in your Canadian job seeker account.'),
        ('calendar', 'Try January with your own photo and logo.', 'Three printable layouts. Add photos to individual months if you want.'),
    ):
        studios.filter(key=key, description=old).update(description=new)
    studios.filter(key='cards', title='Business Card Studio').update(title='Business Card Editor')
    studios.filter(key='international-resume', position=20).update(position=60)


class Migration(migrations.Migration):
    dependencies = [('career_mobility', '0030_specialty_journal_designs')]
    operations = [migrations.RunPython(revise, migrations.RunPython.noop)]
