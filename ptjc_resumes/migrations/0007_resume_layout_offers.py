from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


def seed(apps, schema_editor):
    Product = apps.get_model('career_mobility', 'DigitalProduct')
    Template = apps.get_model('ptjc_resumes', 'ResumeTemplate')
    Offer = apps.get_model('ptjc_resumes', 'ResumeLayoutOffer')
    Product.objects.filter(slug='international-resume-builder-access', price_cad=Decimal('12.99')).update(price_cad=Decimal('19.99'))
    canadian_pack, _ = Product.objects.get_or_create(slug='canadian-resume-all-designs', defaults=dict(
        title='Canadian physiotherapy resume — all four designs', audience='canadian', kind='file',
        category='Resume builder', price_cad='19.99', is_published=False,
        description='Unlock Classic, Clinical, Editorial and Sidebar for your Canadian job seeker resumes.'))
    Template.objects.get_or_create(key='canadian-professional', defaults=dict(title='Canadian physiotherapy resume', is_enabled=True, access_product=canadian_pack))
    for audience in ('international', 'canadian'):
        template = Template.objects.filter(key=f'{audience}-professional').first()
        if not template:
            continue
        for layout in ('classic', 'clinical', 'editorial', 'sidebar'):
            product, _ = Product.objects.get_or_create(slug=f'{audience}-resume-{layout}', defaults=dict(
                title=f'{audience.title()} physiotherapy resume — {layout.title()}',
                audience=audience, kind='file', category='Resume builder', price_cad='5.99',
                is_published=False, description=f'Unlock finished PDF downloads in the {layout.title()} design.'))
            Offer.objects.get_or_create(template=template, layout=layout, defaults={'product': product})


class Migration(migrations.Migration):
    dependencies = [('ptjc_resumes', '0006_resource_builders_upgrade'), ('career_mobility', '0022_checkout_payment_state')]
    operations = [
        migrations.CreateModel(
            name='ResumeLayoutOffer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('layout', models.CharField(max_length=30, choices=[(x, x.title()) for x in ('classic', 'clinical', 'editorial', 'sidebar')])),
                ('template', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='layout_offers', to='ptjc_resumes.resumetemplate')),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='resume_layout_offer', to='career_mobility.digitalproduct')),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('template', 'layout'), name='ptjc_resume_template_layout')]},
        ),
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
