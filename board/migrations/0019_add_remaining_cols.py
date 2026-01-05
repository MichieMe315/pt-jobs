# board/migrations/0019_add_remaining_cols.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0018_add_missing_cols_2"),
    ]

    operations = [
        # Employer: credits counter for posting
        migrations.AddField(
            model_name="employer",
            name="credits",
            field=models.PositiveIntegerField(default=0),
            preserve_default=True,
        ),

        # SiteSettings: social + misc toggles used by admin/UI
        migrations.AddField(
            model_name="sitesettings",
            name="facebook_page",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="instagram_account",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="sitesettings",
            name="reddit_sub",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
    ]
