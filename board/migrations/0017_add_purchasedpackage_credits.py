# board/migrations/0017_add_purchasedpackage_credits.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0016_add_missing_fields_only"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchasedpackage",
            name="credits_granted",
            field=models.PositiveIntegerField(default=1),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name="purchasedpackage",
            name="credits_remaining",
            field=models.PositiveIntegerField(default=1),
            preserve_default=True,
        ),
    ]
