from django.db import migrations


def seed(apps, schema_editor):
    from career_mobility.recovered_products import PRODUCTS, FILES
    Product = apps.get_model('career_mobility','DigitalProduct')
    for key,title,category,audience,description,_ in PRODUCTS:
        Product.objects.using(schema_editor.connection.alias).get_or_create(slug=f'ptjc-{key}',defaults={
            'title':title,'audience':audience,'category':category,'short_description':description,
            'description':description+' Digital download.','download':'bundled/'+FILES[key],'is_published':False,
        })


class Migration(migrations.Migration):
    dependencies = [('career_mobility','0031_clearer_shop_listings')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
