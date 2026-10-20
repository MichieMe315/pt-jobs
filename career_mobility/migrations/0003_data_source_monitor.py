from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("career_mobility", "0002_international_identity_context")]
    operations = [
        migrations.CreateModel(name="DataSource", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("category", models.CharField(max_length=40)),
            ("name", models.CharField(max_length=180, unique=True)),
            ("url", models.URLField(max_length=500)),
            ("cadence", models.CharField(choices=[("monthly", "Monthly"), ("quarterly", "Quarterly")], default="monthly", max_length=12)),
            ("last_checked_at", models.DateTimeField(blank=True, null=True)),
            ("last_changed_at", models.DateTimeField(blank=True, null=True)),
            ("last_http_status", models.PositiveSmallIntegerField(blank=True, null=True)),
            ("content_sha256", models.CharField(blank=True, max_length=64)),
            ("last_error", models.TextField(blank=True)),
            ("enabled", models.BooleanField(default=True)),
            ("notes", models.TextField(blank=True)),
        ]),
        migrations.CreateModel(name="DataSourceReview", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("detected_at", models.DateTimeField(auto_now_add=True)),
            ("status", models.CharField(choices=[("pending", "Needs review"), ("approved", "Reviewed"), ("dismissed", "Dismissed")], default="pending", max_length=12)),
            ("previous_hash", models.CharField(blank=True, max_length=64)),
            ("detected_hash", models.CharField(max_length=64)),
            ("detail", models.TextField(blank=True)),
            ("reviewed_at", models.DateTimeField(blank=True, null=True)),
            ("source", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="career_mobility.datasource")),
        ], options={"ordering": ["-detected_at"]}),
    ]
