from django import template
from board.admin_section_models import WebsitePage

register = template.Library()


@register.simple_tag(takes_context=True)
def navigation_pages(context, placement):
    if placement not in ("header", "footer"):
        return ()
    key = "managed_website_navigation_pages"
    if key not in context.render_context.dicts[0]:
        from django.db.models import Q
        context.render_context.dicts[0][key] = list(WebsitePage.objects.filter(published=True).filter(Q(header=True) | Q(footer=True)))
    return [page for page in context.render_context.dicts[0][key] if getattr(page, placement)]


@register.simple_tag
def affiliate_program_available():
    from board.admin_section_models import AffiliateProgram
    return AffiliateProgram.objects.filter(pk=1, enabled=True, applications_open=True).exclude(terms="").exists()
