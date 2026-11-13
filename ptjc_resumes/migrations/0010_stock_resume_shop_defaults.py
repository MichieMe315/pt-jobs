from decimal import Decimal

from django.db import migrations


def update_stock_defaults(apps, schema_editor):
    products = apps.get_model("career_mobility", "DigitalProduct").objects.using(schema_editor.connection.alias)
    # A fresh install could retain the original $0 placeholder. Never change
    # the price of an existing published offer or turn a draft into a sale.
    products.filter(
        slug="international-resume-builder-access",
        title="International Physiotherapy Resume Builder",
        price_cad=Decimal("0.00"),
        is_published=False,
    ).update(price_cad=Decimal("19.99"))
    products.filter(slug="canadian-resume-all-designs", storefront_order=100, is_published=False).update(storefront_order=10)
    products.filter(slug="international-resume-builder-access", storefront_order=100, is_published=False).update(storefront_order=60)


class Migration(migrations.Migration):
    dependencies = [
        ("ptjc_resumes", "0009_international_planner_ad"),
        ("career_mobility", "0033_international_sponsors"),
    ]
    operations = [migrations.RunPython(update_stock_defaults, migrations.RunPython.noop)]
