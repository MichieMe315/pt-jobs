from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
class Migration(migrations.Migration):
    dependencies = [("career_mobility", "0004_provincial_licence_fee"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="InternationalChecklistItem", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("key", models.SlugField(max_length=90)),
            ("completed", models.BooleanField(default=False)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="checklist_items", to="career_mobility.internationalprofile")),
        ]),
        migrations.AddConstraint(model_name="internationalchecklistitem", constraint=models.UniqueConstraint(fields=("profile", "key"), name="mobility_unique_checklist_item")),
        migrations.CreateModel(name="SavedCareerPlan", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("plan_type", models.CharField(choices=[("salary", "Salary comparison"), ("relocation", "Relocation")], max_length=20)),
            ("title", models.CharField(max_length=120)),
            ("inputs", models.JSONField(default=dict)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="mobility_plans", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["-created_at"]}),
        migrations.CreateModel(name="SalaryBenchmark", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("region", models.CharField(max_length=130, unique=True)),
            ("province", models.CharField(blank=True, max_length=90)),
            ("low_hourly", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
            ("median_hourly", models.DecimalField(decimal_places=2, max_digits=8)),
            ("high_hourly", models.DecimalField(blank=True, decimal_places=2, max_digits=8, null=True)),
            ("source_url", models.URLField(max_length=500)),
            ("reference_period", models.CharField(max_length=90)),
            ("verified_on", models.DateField()),
            ("is_published", models.BooleanField(default=False)),
        ]),
    ]
