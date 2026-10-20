from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("career_mobility", "0003_data_source_monitor")]
    operations = [
        migrations.CreateModel(
            name="ProvincialLicenceFee",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("province", models.CharField(max_length=80)),
                ("regulator", models.CharField(max_length=180)),
                ("fee_type", models.CharField(max_length=20, choices=[("application", "Application/assessment"), ("initial", "Initial registration"), ("renewal", "Annual renewal"), ("provisional", "Provisional registration"), ("exam", "Exam/assessment"), ("other", "Other")])),
                ("description", models.CharField(max_length=240)),
                ("amount_cad", models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)),
                ("applies_to", models.CharField(max_length=160, blank=True, help_text="e.g. Canadian graduate, internationally educated applicant, specific dates")),
                ("effective_on", models.DateField(null=True, blank=True)),
                ("expires_on", models.DateField(null=True, blank=True)),
                ("source_url", models.URLField(max_length=500, blank=True)),
                ("verified_on", models.DateField(null=True, blank=True)),
                ("notes", models.TextField(blank=True)),
                ("is_published", models.BooleanField(default=False)),
            ],
            options={"ordering": ["province", "fee_type", "description"]},
        ),
    ]
