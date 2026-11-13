"""Access is checked against purchased products, never against the browser's UI."""
from career_mobility.store_access import has_access

LAYOUTS = {"classic": "Classic", "clinical": "Clinical", "editorial": "Editorial", "sidebar": "Sidebar"}


def layout_access(user, template, layout):
    from career_mobility.starter import remaining
    return paid_layout_access(user, template, layout) or bool(remaining(user, starter_product(user, template, layout)))


def starter_product(user, template, layout):
    from career_mobility.starter import remaining
    if remaining(user, template.access_product):
        return template.access_product
    offer = template.layout_offers.select_related("product").filter(layout=layout).first()
    return offer.product if offer else None


def paid_layout_access(user, template, layout):
    if template.access_product_id and has_access(user, template.access_product):
        return True
    offer = template.layout_offers.select_related("product").filter(layout=layout).first()
    return bool(offer and has_access(user, offer.product))


def available_offers(template, user):
    if template.access_product_id and has_access(user, template.access_product):
        return []
    offers = [{"label": LAYOUTS[row.layout], "product": row.product}
              for row in template.layout_offers.filter(product__is_published=True).select_related("product").order_by("pk")
              if not has_access(user, row.product)]
    if template.access_product_id and template.access_product.is_published:
        offers.append({"label": "All four designs", "product": template.access_product})
    from career_mobility.pricing import pricing_audience
    storefront = "canadian" if template.key == "canadian-professional" else "international"
    for row in offers:
        product = row["product"]
        row["price"] = product.price_for(pricing_audience(user, product, storefront))
    return [row for row in offers if row["price"] > 0]


def resume_template_for(product):
    from django.db.models import Q
    from .models import ResumeTemplate
    return ResumeTemplate.objects.filter(Q(access_product=product) | Q(layout_offers__product=product), is_enabled=True).first()


def product_access(user, product):
    if has_access(user, product):
        return True
    template = resume_template_for(product) if product.includes_resume_builder else None
    return bool(template and template.access_product_id and has_access(user, template.access_product))


def public_pdf_price(template, audience):
    if not template or not template.is_enabled:
        return None
    products = [row.product for row in template.layout_offers.select_related('product')]
    if template.access_product_id:
        products.append(template.access_product)
    prices = [product.price_for(audience) for product in products
              if product.is_published and product.audience in (audience, 'both') and product.price_for(audience) > 0]
    return min(prices, default=None)


def signup_pdf_price(next_url, audience):
    from urllib.parse import urlsplit
    from django.urls import reverse
    from .models import ResumeTemplate

    claim = 'ptjc_canadian_resumes:canadian_claim' if audience == 'canadian' else 'ptjc_resumes:claim'
    if urlsplit(next_url or '').path != reverse(claim):
        return None
    template = ResumeTemplate.objects.filter(key=f'{audience}-professional', is_enabled=True).first()
    return public_pdf_price(template, audience)
