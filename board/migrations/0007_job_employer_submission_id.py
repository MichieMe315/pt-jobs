from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("board", "0006_job_publication_request")]

    operations = [
        migrations.AddField(
            model_name="job",
            name="employer_submission_id",
            field=models.UUIDField(editable=False, null=True, unique=True),
        ),
    ]
