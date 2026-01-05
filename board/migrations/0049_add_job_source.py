from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0048_delete_jobalertsignup_remove_emailtemplate_body_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="source",
            field=models.CharField(
                choices=[("admin", "Admin"), ("import", "Import"), ("employer", "Employer")],
                db_index=True,
                default="employer",
                max_length=20,
            ),
        ),
    ]
