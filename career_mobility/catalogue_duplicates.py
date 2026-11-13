"""Read-only duplicate candidates; aliases and intentional variants need review."""
from collections import defaultdict
import unicodedata


def duplicate_groups(products):
    by_title, by_file = defaultdict(list), defaultdict(list)
    for product in products:
        title = ''.join(c for c in unicodedata.normalize('NFKC',product.title).casefold() if c.isalnum())
        if title:
            by_title[(product.audience, title)].append(product)
        if product.download:
            by_file[product.download.name].append(product)
    return [
        {'reason':reason, 'products':rows}
        for reason, buckets in [('Same title and audience',by_title), ('Same download file',by_file)]
        for rows in buckets.values() if len(rows)>1
    ]
