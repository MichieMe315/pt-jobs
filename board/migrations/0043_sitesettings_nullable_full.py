from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0042_add_missing_emailtemplate_html"),
    ]

    operations = [

        # BASIC
        migrations.AlterField(
            model_name="sitesettings",
            name="contact_email",
            field=models.EmailField(max_length=254, blank=True, null=True),
        ),

        # BRANDING / COLORS / FOOTER
        migrations.AlterField(
            model_name="sitesettings",
            name="branding_primary_color",
            field=models.CharField(max_length=20, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="branding_secondary_color",
            field=models.CharField(max_length=20, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="footer_text",
            field=models.TextField(blank=True, null=True),
        ),

        # BANNERS
        migrations.AlterField(
            model_name="sitesettings",
            name="side_banner_html",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="bottom_banner_html",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="branding_footer_html",
            field=models.TextField(blank=True, null=True),
        ),

        # SEO
        migrations.AlterField(
            model_name="sitesettings",
            name="seo_meta_title",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="seo_meta_description",
            field=models.TextField(blank=True, null=True),
        ),

        # TRACKING / MAPBOX
        migrations.AlterField(
            model_name="sitesettings",
            name="google_analytics_id",
            field=models.CharField(max_length=100, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="mapbox_token",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),

        # SOCIAL LINKS
        migrations.AlterField(
            model_name="sitesettings",
            name="facebook_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="instagram_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="reddit_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="linkedin_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="twitter_url",
            field=models.URLField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="social_webhook_url",
            field=models.URLField(blank=True, null=True),
        ),

        # HERO FIELDS
        migrations.AlterField(
            model_name="sitesettings",
            name="home_hero_title",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="home_hero_subtitle",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="home_hero_cta_text",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="home_hero_cta_url",
            field=models.URLField(blank=True, null=True),
        ),

        # HOME PAGE INFO COLUMNS
        migrations.AlterField(
            model_name="sitesettings",
            name="employer_column_title",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="employer_column_content",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="jobseeker_column_title",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="sitesettings",
            name="jobseeker_column_content",
            field=models.TextField(blank=True, null=True),
        ),
    ]
