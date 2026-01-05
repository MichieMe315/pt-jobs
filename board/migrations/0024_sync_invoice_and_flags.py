# board/migrations/0024_sync_invoice_and_flags.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0023_sync_featured_processor"),
    ]

    operations = [
        # Invoice: external processor reference (e.g., Stripe session/intent id or PayPal order id)
        migrations.AddField(
            model_name="invoice",
            name="processor_reference",
            field=models.CharField(max_length=255, blank=True, default=""),
        ),
    ]
