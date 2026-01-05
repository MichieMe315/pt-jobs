from django.db import migrations, models
import board.models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0040_sitesettings_bottom_banner_html_and_more"),
    ]

    operations = [

        # HERO FIELDS
        migrations.AddField(
            model_name="sitesettings",
            name="home_hero_image",
            field=models.ImageField(
                upload_to=board.models.branding_upload_path,
                blank=True,
                null=True
            ),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="home_hero_title",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="home_hero_subtitle",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="home_hero_cta_text",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="home_hero_cta_url",
            field=models.URLField(blank=True, null=True),
        ),

        # INFO COLUMNS
        migrations.AddField(
            model_name="sitesettings",
            name="employer_column_title",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="employer_column_content",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="jobseeker_column_title",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="jobseeker_column_content",
            field=models.TextField(blank=True, null=True),
        ),
    ]
