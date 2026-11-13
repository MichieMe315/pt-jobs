"""Import PT resume V6 as private, unpublished shop products.

Run: python manage.py import_pt_resume_v6
Optional: --update-files to replace a previously imported download.
Prices remain 0 and products remain unpublished until admin review.
"""
from pathlib import Path
from django.core.files import File
from django.core.management.base import BaseCommand,CommandError
from django.utils.text import slugify
from career_mobility.models import DigitalProduct

ASSETS = Path(__file__).resolve().parents[2] / 'product_imports'

class Command(BaseCommand):
    help = 'Import reviewed PT Resume V6 files as unpublished individual and bundle products'

    def add_arguments(self, parser):
        parser.add_argument('--update-files', action='store_true')

    def handle(self, *args, **options):
        if not ASSETS.exists():
            raise CommandError('Product import assets are missing.')
        items = []
        for p in sorted(ASSETS.glob('0*.zip')):
            label = p.stem.split('_', 1)[1].replace('_', ' ')
            items.append((p, f'PT Resume & Cover Letter — {label}', f'PT-specific resume and cover letter templates, worked examples, and editable Word files for {label.lower()}.' ))
        for filename, title, desc in [
            ('Annotated_PT_Resume_Examples.pdf', 'Annotated PT Resume Examples', 'Annotated physiotherapy resume examples for review and learning.'),
            ('PT_Application_Studio.pdf', 'PT Application Studio', 'Application preparation resource for physiotherapists.'),
            ('PT_Resume_Writing_and_Personalization.pdf', 'PT Resume Writing & Personalization', 'Guidance for tailoring a physiotherapy resume.'),
            ('PT_Personal_Brand_Graphics.zip', 'PT Personal Brand Graphics Kit', 'Downloadable branding graphics and logo/banner maker; review usage before publishing.'),
            ('PT_Resume_Complete_Collection.zip', 'Complete PT Resume Collection', 'Bundle of all nine PT resume specializations, examples, guides and brand assets.'),
        ]:
            items.append((ASSETS / filename, title, desc))
        missing=[path.name for path,_,_ in items if not path.is_file()]
        if missing:raise CommandError('Missing product import files: '+', '.join(missing))
        for path, title, description in items:
            category=('International resumes' if 'International' in path.stem else 'Canadian resumes') if path.stem[:2].isdigit() else 'Resume bundles' if 'Complete_Collection' in path.stem else 'Brand assets' if 'Graphics' in path.stem else 'Application guides'
            slug = 'pt-v6-' + slugify(path.stem)[:40]
            product, created = DigitalProduct.objects.get_or_create(slug=slug, defaults={
                'title': title, 'description': description, 'category':category, 'is_published': False,
            })
            if created or options['update_files'] or not product.download:
                with path.open('rb') as f:
                    product.download.save(path.name, File(f), save=False)
                product.save(update_fields=['download'])
            self.stdout.write(f"{'Created' if created else 'Existing'}: {title} — {'DRAFT' if not product.is_published else 'PUBLISHED'}")
        self.stdout.write(self.style.SUCCESS(f'Processed {len(items)} products. Set prices and publish in admin after review.'))
