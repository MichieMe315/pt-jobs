# board/migrations/0009_add_jobseeker_timestamps.py
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0008_fix_settings_and_timestamps"),
    ]

    operations = [
        # JOBSEEKER: add created_at/updated_at
        migrations.AddField(
            model_name="jobseeker",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="created at",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="jobseeker",
            name="updated_at",
            field=models.DateTimeField(
                auto_now=True,
                verbose_name="updated at",
            ),
        ),
    ]
