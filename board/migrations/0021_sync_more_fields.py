# board/migrations/0021_sync_more_fields.py
from django.db import migrations, models
import django.utils.timezone
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0020_bulk_sync_remaining_fields"),
    ]

    operations = [
        # ---------------- Job: compensation fields ----------------
        migrations.AddField(
            model_name="job",
            name="compensation_min",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="job",
            name="compensation_max",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="job",
            name="split_percent",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),

        # ---------------- Resume: timestamp ----------------
        migrations.AddField(
            model_name="resume",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),

        # ---------------- JobSeeker: timestamp ----------------
        migrations.AddField(
            model_name="jobseeker",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),

        # ---------------- Invoice: link to PurchasedPackage ----------------
        migrations.AddField(
            model_name="invoice",
            name="purchased_package",
            field=models.ForeignKey(
                to="board.purchasedpackage",
                on_delete=models.SET_NULL,
                related_name="invoices",
                null=True,
                blank=True,
            ),
        ),

        # ---------------- PostingPackage: price ----------------
        migrations.AddField(
            model_name="postingpackage",
            name="price",
            field=models.DecimalField(max_digits=9, decimal_places=2, default=Decimal("0.00")),
            preserve_default=True,
        ),
    ]
