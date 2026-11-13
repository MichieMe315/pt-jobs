from django.db import migrations

def seed(apps,schema_editor):
    Product=apps.get_model('career_mobility','DigitalProduct')
    Product.objects.get_or_create(slug='international-planning-workbook',defaults={'title':'Personalized International Planning Workbook','kind':'workbook','category':'International planning','short_description':'A personalized PDF with your saved route and checklist progress. One download credit per purchase.','description':'Generate a private planning workbook from your current education country, destination and saved checklist. Each purchase gives one download credit; download when you are ready. The free online checklist remains available.','price_cad':'1.99','is_published':True})

class Migration(migrations.Migration):
    dependencies=[('career_mobility','0017_digital_store_offers_and_access')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]
