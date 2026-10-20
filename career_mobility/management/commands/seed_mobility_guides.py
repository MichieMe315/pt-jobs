from pathlib import Path
from django.core.files import File
from django.core.management.base import BaseCommand
from career_mobility.models import DigitalProduct

GUIDES = [
    ("international-pt-pathway-guide", "International PT Pathway Planning Guide", "International education, CAPR, province and immigration planning."),
    ("canadian-pt-relocation-guide", "Canadian PT Relocation Decision Guide", "Housing, income, licensing and break-even planning."),
    ("pt-salary-contractor-guide", "PT Employee vs Contractor Guide", "Fee splits, patient billing and contractor expenses."),
]
class Command(BaseCommand):
    help = "Install the three finished starter PDF guides as private, unpublished products; never set a price."
    def handle(self,*args,**kwargs):
        root=Path(__file__).resolve().parents[2] / "guides"
        for slug,title,description in GUIDES:
            product,created=DigitalProduct.objects.get_or_create(slug=slug,defaults={"title":title,"description":description,"is_published":False,"price_cad":0})
            if not product.download:
                with (root / (slug+".pdf")).open("rb") as f:
                    product.download.save(slug+".pdf",File(f),save=True)
                self.stdout.write(f"Installed private PDF: {title}")
            else:
                self.stdout.write(f"Kept existing product: {title}")
        self.stdout.write("Products remain unpublished. Review content, set price and publish in admin when ready.")
