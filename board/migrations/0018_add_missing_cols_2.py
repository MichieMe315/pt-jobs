# board/migrations/0018_add_missing_cols_2.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0017_add_purchasedpackage_credits"),
    ]

    operations = [
        # Add SiteSettings.mapbox_token if it's missing
        migrations.AddField(
            model_name="sitesettings",
            name="mapbox_token",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
        # Add PurchasedPackage.external_reference if it's missing
        migrations.AddField(
            model_name="purchasedpackage",
            name="external_reference",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
    ]
