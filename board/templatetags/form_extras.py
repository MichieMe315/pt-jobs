from django import template
from django.forms.boundfield import BoundField

register = template.Library()

@register.filter
def as_widget(bound_field, arg_string=""):
    """
    Usage: {{ form.field|as_widget:"class:form-control rows:5 placeholder:Type..." }}
    Works only on BoundField; if not, returns value unchanged (safe).
    """
    if not isinstance(bound_field, BoundField):
        return bound_field

    # parse arg_string as key:value space-separated
    attrs = {}
    if arg_string:
        parts = [p for p in arg_string.split(" ") if p.strip()]
        for p in parts:
            if ":" in p:
                k, v = p.split(":", 1)
                attrs[k.strip()] = v.strip()
    return bound_field.as_widget(attrs=attrs)
