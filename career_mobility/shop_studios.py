"""The five fixed editor links and their admin-managed storefront placement."""
from django.templatetags.static import static
from django.urls import NoReverseMatch, reverse

from .editable_products import CALENDAR
from .models import DigitalProduct, StorefrontStudio

STUDIO_LINKS = {
    'canadian-resume': ('canadian', 'resume', 'ptjc_canadian_resumes:canadian_start', (), 'ptjc_resumes/designs/canadian-shop.jpg', 'Start Canadian résumé'),
    'international-resume': ('international', 'resume', 'ptjc_resumes:start', (), 'ptjc_resumes/designs/international-shop.jpg', 'Start international résumé'),
    'cards': ('both', 'card', 'mobility_try_cards', (), None, 'Design a business card'),
    'printables': ('both', '', 'mobility_choose_journal', (), 'career_mobility/product-previews/journals/paediatric-physio-journal/cover.jpg', 'Try the journal'),
    'calendar': ('both', '', 'mobility_editable_preview', (CALENDAR,), 'career_mobility/product-previews/pages/physio-wall-calendar-2027-planner.jpg', 'Personalize the calendar'),
}


def storefront_products(queryset, audience):
    return queryset.filter(audience__in=(audience, 'both'))


def published_journal_slugs(audience):
    from .editable_products import JOURNALS

    return set(storefront_products(DigitalProduct.objects.filter(
        is_published=True, slug__in=['ptjc-' + key for key in JOURNALS],
    ), audience).values_list('slug', flat=True))


def linked_studio_products():
    from ptjc_resumes.models import ResumeTemplate

    slugs = {'cards': 'international-business-card-builder-access',
             'calendar': 'ptjc-physio-wall-calendar-2027'}
    for key, slug in ResumeTemplate.objects.filter(
        key__in=('canadian-professional', 'international-professional'),
        access_product__isnull=False,
    ).values_list('key', 'access_product__slug'):
        slugs[key.replace('-professional', '-resume')] = slug
    products = DigitalProduct.objects.in_bulk(slugs.values(), field_name='slug')
    return {key: products.get(slug) for key, slug in slugs.items()}


def editor_visibility(studio, audience, product):
    if not studio['visible']:
        return 'Editor tile disabled'
    if product and product.audience not in (audience, 'both'):
        return 'Hidden · assigned to the other storefront'
    if product and not product.is_published:
        return 'Hidden · linked product is a draft'
    return 'Visible' if product else 'Free editor · no linked product'


def for_shop(audience, *, include_hidden=False):
    studios = StorefrontStudio.objects.all()
    if not include_hidden:
        studios = studios.filter(is_visible=True)
    for studio in studios:
        spec = STUDIO_LINKS.get(studio.key)
        if not spec:
            continue
        for_audience, artwork, route, args, asset, button = spec
        if audience and for_audience not in ('both', audience):
            continue
        try:
            href = reverse(route, args=args)
        except NoReverseMatch:
            continue
        if audience == 'international' and for_audience == 'both':
            href += '?audience=international'
        image = static(asset) if asset else reverse('mobility_public_card_preview', args=['editorial','front'])
        yield {'key': studio.key, 'title': studio.title, 'description': studio.description,
               'position': studio.position, 'pk': studio.pk, 'visible': studio.is_visible, 'artwork': artwork, 'href': href, 'image': image, 'button': button}
