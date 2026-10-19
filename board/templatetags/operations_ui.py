from django import template
from board.operations import navigation, summary
register=template.Library()

@register.inclusion_tag('admin/operations/summary.html',takes_context=True)
def operations_overview(context):
    request=context['request']
    return {'ops_cards':summary(request.user),'ops_nav':navigation(request.user)}
