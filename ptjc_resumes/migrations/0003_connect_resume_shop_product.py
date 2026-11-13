from django.db import migrations

def connect(apps,schema_editor):
    Template=apps.get_model('ptjc_resumes','ResumeTemplate')
    Product=apps.get_model('career_mobility','DigitalProduct')
    template=Template.objects.filter(key='international-professional').first()
    if not template or template.access_product_id:return
    product,_=Product.objects.get_or_create(slug='international-resume-builder-access',defaults={'title':'International physiotherapy resume builder','category':'Resume builder','short_description':'Saved resume drafts, PDF previews and finished resume downloads.','description':'Build your physiotherapy resume online. Save drafts, preview the layout and download finished PDFs after purchase. Return to edit and download again.','price_cad':0,'is_published':False})
    template.access_product_id=product.pk;template.save(update_fields=['access_product'])
class Migration(migrations.Migration):
    dependencies=[('ptjc_resumes','0002_alter_resumetemplate_access_product')]
    operations=[migrations.RunPython(connect,migrations.RunPython.noop)]
