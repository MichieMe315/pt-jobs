from __future__ import annotations
from decimal import Decimal
from django import template

register = template.Library()

@register.filter
def money_cents_to_dollars(value):
    try:
        return f"{(Decimal(value) / Decimal('100')).quantize(Decimal('0.01'))}"
    except Exception:
        return value
