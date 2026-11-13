from django import template
from django.urls import reverse

register = template.Library()


def product_links(audience, exclude=None, editor=None):
    from career_mobility.models import DigitalProduct
    from career_mobility.shop_gallery import editor_key, resource_link
    from career_mobility.shop_studios import storefront_products

    links = {}
    if exclude:
        links[exclude] = None
    for product in storefront_products(DigitalProduct.objects.filter(is_published=True), audience).order_by('storefront_order', 'title', 'pk'):
        if (editor and editor_key(product) == editor) or product.kind == 'workbook':
            continue
        url = resource_link(product, audience)
        if url and url not in links:
            links[url] = product.title
            if sum(bool(title) for title in links.values()) == 4:
                break
    return [(title, url) for url, title in links.items() if title]


@register.inclusion_tag('career_mobility/builder_product_nav.html', takes_context=True)
def related_digital_products(context, canadian=False, kind=None):
    audience = 'canadian' if canadian else 'international'
    request = context.get('request')
    from django.urls import NoReverseMatch
    try:
        shop_url = reverse('mobility_shop' if canadian else 'mobility_international_shop')
    except NoReverseMatch:
        return {}
    path = request.path if request else None
    if kind != 'cards' and path and 'resume' in path:
        try:
            path = reverse('ptjc_canadian_resumes:canadian_start' if canadian else 'ptjc_resumes:start')
        except NoReverseMatch:
            pass
    elif kind == 'cards' or (path and 'card' in path):
        path = reverse('mobility_try_cards') + ('?audience=international' if not canadian else '?audience=canadian')
    if kind != 'cards' and path and 'resume' in path:
        if canadian:
            resources = (
                ('Compare salary and clinic splits', 'Estimate take-home pay for an employee offer or a fee split.', 'mobility_salary_comparison'),
                ('Review a clinic offer', 'Bring questions about caseload, compensation and contract terms to your next interview.', 'mobility_clinic_offer_guide'),
            )
        else:
            resources = (
                ('Plan your move to Canada', 'Build a registration checklist for the province where you want to practise.', 'mobility_international'),
                ('Browse physiotherapy jobs', 'Explore current physiotherapy job postings', 'job_list'),
            )
        return {'shop_url': shop_url, 'next_steps': [(title, description, reverse(route)) for title, description, route in resources]}
    links = product_links(audience, path)
    if kind == 'cards':
        route = 'ptjc_canadian_resumes:canadian_start' if canadian else 'ptjc_resumes:start'
        resume_url = reverse(route)
        links = [('Canadian résumé builder' if canadian else 'International résumé builder', resume_url), *[(title, url) for title, url in links if url != resume_url]]
    return {'shop_url': shop_url, 'related': links}
