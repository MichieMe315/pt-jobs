from django.core.management.base import BaseCommand, CommandError
from career_mobility.models import DigitalProduct
from ptjc_resumes.models import ResumeTemplate

class Command(BaseCommand):
    help='Connect the international resume template to an existing shop product. Does not set a price, create a product or publish anything.'
    def add_arguments(self, parser):
        parser.add_argument('--product-slug',required=True)
        parser.add_argument('--enable',action='store_true')
    def handle(self,*args,**opts):
        try:product=DigitalProduct.objects.get(slug=opts['product_slug'])
        except DigitalProduct.DoesNotExist:raise CommandError('No shop product has this slug. Select or create the intended product in admin first.')
        obj,created=ResumeTemplate.objects.get_or_create(key='international-professional',defaults={'access_product':product})
        if not created and obj.access_product_id!=product.pk:raise CommandError('Template already uses another product. Change it explicitly in admin; existing purchase access would change.')
        if opts['enable']:obj.is_enabled=True;obj.save(update_fields=['is_enabled'])
        self.stdout.write(self.style.SUCCESS(f'Template connected to {product.title}. Price remains CAD {product.price_cad}. Enabled: {obj.is_enabled}.'))
