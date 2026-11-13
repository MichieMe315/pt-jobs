"""Build reviewed product-file collections into one private purchasable ZIP."""
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify
from .models import DigitalProduct


def build_bundle(collection):
    products=list(collection.products.order_by('pk'))
    if not products or len(products)>40:raise ValueError('Choose between 1 and 40 products.')
    if collection.bundle_product_id in {p.pk for p in products}:raise ValueError('A bundle cannot contain itself.')
    buf=BytesIO();total=0;contents=[]
    with ZipFile(buf,'w',ZIP_DEFLATED) as archive:
        for product in products:
            if not product.download:raise ValueError(f'{product.title} has no private file.')
            with product.download.open('rb') as source:
                data=source.read(50*1024*1024+1)
            total+=len(data)
            if total>50*1024*1024:raise ValueError('Bundle exceeds 50 MB; use smaller files.')
            filename=(slugify(product.slug) or str(product.pk))+'/'+PurePosixPath(product.download.name.replace(chr(92),'/')).name
            archive.writestr(filename,data)
            contents.append(product.title)
    with transaction.atomic():
        product=collection.bundle_product
        if product is None:
            slug=collection.country_slug+'-resource-bundle'
            if DigitalProduct.objects.filter(slug=slug).exists():raise ValueError('Bundle slug already exists; select the existing bundle product or choose another slug.')
            product=DigitalProduct.objects.create(title=collection.title+' bundle',slug=slug,description='Includes: '+', '.join(contents),price_cad=0,is_published=False)
        elif product.is_published:
            raise ValueError('Unpublish the bundle product before replacing its contents.')
        product.download.save(collection.country_slug+'-resources.zip',ContentFile(buf.getvalue()),save=True)
        collection.bundle_product=product;collection.save(update_fields=['bundle_product'])
    return product
