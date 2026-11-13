from django import template

from career_mobility.shop_gallery import resource_link

register = template.Library()


@register.simple_tag
def owned_resource_editor(product, international=False):
    audience = 'international' if international else 'canadian'
    if product.is_published and product.audience in (audience, 'both'):
        return resource_link(product, audience)
    return ''
