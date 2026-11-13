from django import template
from career_mobility.models import InternationalSponsor
from career_mobility.countries import canonical

register = template.Library()


@register.inclusion_tag('career_mobility/_international_sponsor.html',takes_context=True)
def international_sponsor(context):
    request = context.get('request')
    if not request or not request.resolver_match:
        return {}
    route = request.resolver_match.url_name or ""
    if any(term in route for term in ('login','signup','logout','verify','password','checkout','payment')):
        return {}
    profile = getattr(request.user,'international_pt_profile',None)
    country = context.get('country') or {}
    answers = context.get('answers') or {}
    selected = (country.get('name','') if isinstance(country,dict) else '') or (
        answers.get('country','') if isinstance(answers,dict) else '') or getattr(profile,'country_of_education','')
    try:
        selected = canonical(selected)
    except ValueError:
        selected = ''
    ads = InternationalSponsor.objects.filter(enabled=True)
    sponsor = ads.filter(country__iexact=selected).first() if selected else None
    return {'sponsor':sponsor or ads.filter(country='').first()}
