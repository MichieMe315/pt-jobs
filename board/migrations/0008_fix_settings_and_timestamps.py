# board/migrations/0008_fix_settings_and_timestamps.py
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    # Make this depend on your 0007 so the graph is linear
    dependencies = [
        ("board", "0007_emailsettings_sitesettings_job_percent_split_max_and_more"),
    ]

    operations = [
        # EMPLOYER: add created_at/updated_at
        # created_at is non-null, so we backfill with "now" then drop the default
        migrations.AddField(
            model_name="employer",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="created at",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="employer",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                verbose_name="updated at",
            ),
        ),

        # EMAILTEMPLATE: only updated_at is missing per your error
        # Allow null initially so we don't need a backfill default; model code can treat it as readonly
        migrations.AddField(
            model_name="emailtemplate",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                null=True,
                blank=True,
                verbose_name="updated at",
            ),
        ),

        # POSTINGPACKAGE: only updated_at is missing per your error
        migrations.AddField(
            model_name="postingpackage",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                null=True,
                blank=True,
                verbose_name="updated at",
            ),
        ),
    ]
