# board/migrations/0022_sync_missing_triplet.py
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0021_sync_more_fields"),
    ]

    operations = [
        # Job: relocation assistance flag
        migrations.AddField(
            model_name="job",
            name="relocation_assistance",
            field=models.BooleanField(default=False),
        ),

        # Invoice: status field used in admin list_display
        migrations.AddField(
            model_name="invoice",
            name="status",
            field=models.CharField(
                max_length=20,
                default="pending",
                choices=[
                    ("pending", "Pending"),
                    ("paid", "Paid"),
                    ("refunded", "Refunded"),
                    ("failed", "Failed"),
                ],
            ),
            preserve_default=True,
        ),

        # EmailTemplate: updated_at for admin display/sorting
        migrations.AddField(
            model_name="emailtemplate",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
