# board/migrations/0014_fix_invoice_created_at.py
from django.db import migrations, models
from django.utils import timezone


def backfill_invoice_created_at(apps, schema_editor):
    Invoice = apps.get_model("board", "Invoice")
    # For any legacy rows that have NULL created_at, set to "now" so we can make it non-nullable safely.
    Invoice.objects.filter(created_at__isnull=True).update(created_at=timezone.now())


class Migration(migrations.Migration):

    # IMPORTANT: this must point to your latest real migration
    dependencies = [
        ("board", "0013_employer_approved_at_purchasedpackage_invoice_and_more"),
    ]

    operations = [
        # 1) Temporarily allow NULL so older rows don't block the migration
        migrations.AlterField(
            model_name="invoice",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
        ),
        # 2) Backfill legacy NULLs
        migrations.RunPython(backfill_invoice_created_at, migrations.RunPython.noop),
        # 3) Lock the field back to non-nullable
        migrations.AlterField(
            model_name="invoice",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
