# board/migrations/0023_sync_featured_processor.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0022_sync_missing_triplet"),
    ]

    operations = [
        # Job: is_featured flag used in listings/admin
        migrations.AddField(
            model_name="job",
            name="is_featured",
            field=models.BooleanField(default=False),
        ),

        # Invoice: processor used in admin list_filter
        migrations.AddField(
            model_name="invoice",
            name="processor",
            field=models.CharField(
                max_length=20,
                default="stripe",
                choices=[
                    ("stripe", "Stripe"),
                    ("paypal", "PayPal"),
                    ("admin", "Admin Adjustment"),
                ],
            ),
            preserve_default=True,
        ),
    ]
