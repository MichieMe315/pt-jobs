from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("board", "0041_add_hero_fields"),
    ]

    operations = [
        # Add the missing html field so EmailTemplate matches the model
        migrations.AddField(
            model_name="emailtemplate",
            name="html",
            field=models.TextField(blank=True, null=True),
        ),
    ]
