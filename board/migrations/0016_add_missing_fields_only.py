# board/migrations/0016_add_missing_fields_only.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0015_add_created_at_defaults_clean"),
    ]

    operations = [
        # Add SiteSettings.site_logo if it's not there yet
        migrations.AddField(
            model_name="sitesettings",
            name="site_logo",
            field=models.ImageField(upload_to="site/", blank=True, null=True),
        ),
        # Add Employer.company_description if DB is missing it.
        # We won't drop any old 'description' column (if it exists); leaving it is harmless.
        migrations.AddField(
            model_name="employer",
            name="company_description",
            field=models.TextField(blank=True, default=""),
        ),
        # Add Job.apply_via (routing selector) if DB is missing it.
        migrations.AddField(
            model_name="job",
            name="apply_via",
            field=models.CharField(
                max_length=20,
                choices=[("email", "Email"), ("url", "URL"), ("internal", "Internal Apply")],
                default="internal",
            ),
            preserve_default=True,
        ),
    ]
