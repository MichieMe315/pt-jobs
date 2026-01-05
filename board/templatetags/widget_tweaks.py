from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def render_field(field, **attrs):
    """
    Lightweight stand-in for django-widget-tweaks' `render_field` tag.

    Usage in templates:
        {% render_field form.some_field class="form-control" placeholder="..." %}

    This helper merges the given attrs into the field's widget attrs and renders it.
    """
    widget = field.field.widget
    merged_attrs = widget.attrs.copy()
    merged_attrs.update(attrs)
    return mark_safe(field.as_widget(attrs=merged_attrs))
