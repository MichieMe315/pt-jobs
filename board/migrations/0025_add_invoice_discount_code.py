# board/migrations/0025_add_invoice_discount_code.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0024_sync_invoice_and_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="discount_code",
            field=models.CharField(max_length=50, blank=True, default=""),
        ),
    ]
