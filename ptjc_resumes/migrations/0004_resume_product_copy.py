from django.db import migrations
OLD_TITLE='International physiotherapy resume builder'
OLD_SHORT='Saved resume drafts, PDF previews and finished resume downloads.'
OLD_DESCRIPTION='Build your physiotherapy resume online. Save drafts, preview the layout and download finished PDFs after purchase. Return to edit and download again.'
NEW_TITLE='International Physiotherapy Resume Builder'
NEW_SHORT='Create a Canadian-format resume with your physiotherapy qualifications, clinical experience and registration status. Save drafts, preview the PDF and return to update it.'
NEW_DESCRIPTION='Build a professional resume for your next step in Canada. Organize your physiotherapy qualifications, clinical employment, supervised placements, courses and languages in one place. Show your Canadian registration status clearly, and choose whether to include assessment and examination milestones. Your draft saves as you type. Arrange the sections, inspect the PDF layout and purchase finished PDF access at the price shown. After purchase, return to edit your saved resumes and download updated PDFs.'
def update_copy(apps,schema_editor):
    Product=apps.get_model('career_mobility','DigitalProduct')
    product=Product.objects.filter(slug='international-resume-builder-access').first()
    if not product:return
    fields=[]
    for key,old,new in [('title',OLD_TITLE,NEW_TITLE),('short_description',OLD_SHORT,NEW_SHORT),('description',OLD_DESCRIPTION,NEW_DESCRIPTION)]:
        if getattr(product,key)==old:setattr(product,key,new);fields.append(key)
    if fields:product.save(update_fields=fields)
class Migration(migrations.Migration):
    dependencies=[('ptjc_resumes','0003_connect_resume_shop_product')]
    operations=[migrations.RunPython(update_copy,migrations.RunPython.noop)]
