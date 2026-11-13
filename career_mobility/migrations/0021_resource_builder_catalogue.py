from django.db import migrations

def seed(apps,schema_editor):
    Product=apps.get_model('career_mobility','DigitalProduct')
    Product.objects.filter(slug__in=['international-resume-builder-access','international-planning-workbook']).update(audience='international')
    Collection=apps.get_model('career_mobility','CountryResourceCollection')
    country_products=set()
    for collection in Collection.objects.all():
        country_products.update(collection.products.values_list('pk',flat=True))
        if collection.bundle_product_id:country_products.add(collection.bundle_product_id)
    Product.objects.filter(pk__in=country_products).update(audience='international')
    Product.objects.get_or_create(slug='international-business-card-builder-access',defaults={'title':'International Business Card Studio','audience':'international','category':'Business cards','short_description':'Four editable front-and-back designs with private saved drafts and finished PDF access.','description':'Create and save professional networking cards online. Choose Clinical, Community, Editorial or International Networking. Edit both sides with your own details and accurate registration status. PDF access includes front and back at 3.5 × 2 inches.','price_cad':0,'is_published':False})

class Migration(migrations.Migration):
    dependencies=[('career_mobility','0020_resource_builders_upgrade')]
    operations=[migrations.RunPython(seed,migrations.RunPython.noop)]
