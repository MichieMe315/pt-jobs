from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("career_mobility", "0033_international_sponsors")]
    operations = [
        migrations.AddField(
            model_name="digitalproduct",
            name=name,
            field=models.DecimalField(
                blank=True, null=True, max_digits=9, decimal_places=2,
                validators=[MinValueValidator(0)],
            ),
        )
        for name in ("canadian_price_cad", "international_price_cad")
    ]
