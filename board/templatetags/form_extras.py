# board/templatetags/form_extras.py
from django import template
from django.utils.safestring import mark_safe
from django.forms.boundfield import BoundField

register = template.Library()

def _as_bound(field):
    """
    Return a BoundField or None. If the template accidentally passes a string
    (SafeString) instead of a BoundField, we simply return None so filters are no-ops.
    """
    return field if isinstance(field, BoundField) else None

@register.filter(name="add_class")
def add_class(field, css):
    bf = _as_bound(field)
    if not bf:
        return field  # no-op if not a BoundField
    return bf.as_widget(attrs={**bf.field.widget.attrs, "class": f"{bf.field.widget.attrs.get('class','')} {css}".strip()})

@register.filter(name="add_attr")
def add_attr(field, arg):
    bf = _as_bound(field)
    if not bf:
        return field
    key, _, val = (arg or "").partition(":")
    key = key.strip()
    val = val.strip()
    if not key:
        return bf
    return bf.as_widget(attrs={**bf.field.widget.attrs, key: val})

@register.filter(name="add_placeholder")
def add_placeholder(field, text):
    bf = _as_bound(field)
    if not bf:
        return field
    return bf.as_widget(attrs={**bf.field.widget.attrs, "placeholder": text or ""})

@register.filter(name="cents_to_currency")
def cents_to_currency(amount_cents):
    """
    Simple cents->currency formatting used by checkout template.
    If you store Decimal dollars instead, you can replace this.
    """
    try:
       cents = int(amount_cents or 0)
    except (TypeError, ValueError):
       cents = 0
    return "${:,.2f}".format(cents / 100.0)
