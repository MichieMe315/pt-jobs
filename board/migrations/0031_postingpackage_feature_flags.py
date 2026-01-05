# board/migrations/0031_postingpackage_feature_flags.py
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("board", "0030_jobalert_widgettemplate_alter_application_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="postingpackage",
            name="featured_employer",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="postingpackage",
            name="featured_job",
            field=models.BooleanField(default=False),
        ),
    ]
