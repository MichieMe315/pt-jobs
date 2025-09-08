from django import template

register = template.Library()

@register.filter
def has_employer(user):
    try:
        return bool(user.employer)
    except Exception:
        return False

@register.filter
def has_jobseeker(user):
    try:
        return bool(user.jobseeker)
    except Exception:
        return False
