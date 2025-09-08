from django import template

register = template.Library()

@register.filter
def cents_to_currency(value):
    try:
        cents = int(value or 0)
        return "${:,.2f}".format(cents / 100.0)
    except Exception:
        return "$0.00"
