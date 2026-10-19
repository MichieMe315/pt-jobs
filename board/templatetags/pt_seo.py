import json
import re
from datetime import datetime, time
from django import template
from django.utils import timezone
from django.utils.html import format_html, strip_tags
from django.utils.safestring import mark_safe

register = template.Library()
from board.seo_config import SITE
PROVINCES = {'ON':'Ontario','BC':'British Columbia','AB':'Alberta','SK':'Saskatchewan','MB':'Manitoba','QC':'Quebec','NS':'Nova Scotia','NB':'New Brunswick','NL':'Newfoundland and Labrador','PE':'Prince Edward Island','NT':'Northwest Territories','NU':'Nunavut','YT':'Yukon'}


def json_script(data):
    text = json.dumps(data, ensure_ascii=False).replace('&','\\u0026').replace('<','\\u003c').replace('>','\\u003e')
    return mark_safe('<script type="application/ld+json">'+text+'</script>')


def job_schema(job):
    if not job.is_active or (job.expiry_date and job.expiry_date < timezone.localdate()): return None
    # Do not invent an address or assume a country for an unparseable location.
    parts = [p.strip() for p in job.location.split(',') if p.strip()]
    if len(parts)<2: return None
    province = next((abbr for abbr, name in PROVINCES.items() if any(p.lower() in (abbr.lower(), name.lower()) for p in parts[1:])), None)
    if not province: return None
    date = job.posting_date.date() if isinstance(job.posting_date,datetime) else job.posting_date
    if not date or date > timezone.localdate() or not job.description.strip() or not job.employer.company_name.strip(): return None
    data = {'@context':'https://schema.org','@type':'JobPosting','title':job.title, 'description':job.description,
        'datePosted':date.isoformat(), 'identifier':{'@type':'PropertyValue','name':'Physiotherapy Jobs Canada','value':str(job.pk)},
        'url':SITE+f'/jobs/{job.pk}/','hiringOrganization':{'@type':'Organization','name':job.employer.company_name},
        'jobLocation':{'@type':'Place','address':{'@type':'PostalAddress','addressLocality':parts[0],'addressRegion':province,'addressCountry':'CA'}}}
    if job.expiry_date:
        data['validThrough'] = timezone.make_aware(datetime.combine(job.expiry_date,time(23,59,59))).isoformat()
    employment = {'full_time':'FULL_TIME','part_time':'PART_TIME','contractor':'CONTRACTOR','casual':'OTHER','locum':'TEMPORARY','temporary':'TEMPORARY'}
    if job.job_type in employment: data['employmentType'] = employment[job.job_type]
    # Percentage splits are not monetary salaries. Use only stated, valid pay ranges.
    if job.compensation_type in ('hourly','yearly') and job.compensation_min is not None and job.compensation_min>0:
        value = {'@type':'QuantitativeValue','unitText':'HOUR' if job.compensation_type=='hourly' else 'YEAR'}
        if job.compensation_max is not None and job.compensation_max>=job.compensation_min:
            value.update(minValue=float(job.compensation_min),maxValue=float(job.compensation_max))
        elif job.compensation_max is None:
            value['value']=float(job.compensation_min)
        if 'value' in value or 'minValue' in value:
            data['baseSalary']={'@type':'MonetaryAmount','currency':'CAD','value':value}
    return data


@register.simple_tag(takes_context=True)
def seo_head(context):
    request = context.get('request')
    if not request: return ''
    name = request.resolver_match.url_name if request.resolver_match else ''
    private = {'login','logout','employer_signup','jobseeker_signup','employer_dashboard','employer_profile_edit','jobseeker_dashboard','jobseeker_profile_edit','job_create','job_edit','job_duplicate','apply_to_job','checkout_select','checkout_start','checkout_success','paypal_success','invoice_detail','invoice_download','hiring_tool','password_reset','password_reset_done','password_reset_confirm','password_reset_complete','job_alert_signup','job_alert_unsubscribe','stripe_webhook','stripe_create_session'}
    if name in private or request.path.startswith('/admin/'): return mark_safe('<meta name="robots" content="noindex,follow">')
    if name.startswith('province_'): return ''  # Existing province template owns its metadata.
    if request.resolver_match is None:
        return mark_safe('<meta name="robots" content="noindex,follow">')
    canonical = SITE+request.path
    description = ''
    data = None
    if name == 'home':
        pass  # Preserve the existing admin-driven hero/title and description.
    elif name == 'job_list':
        description = 'Find physiotherapy and allied health jobs across Canada. Compare current clinic, rehabilitation, locum and community roles by location.'
    elif name == 'job_detail':
        job = context.get('job')
        if job:
            description = f'{job.title} at {job.employer.company_name} in {job.location}. '+strip_tags(job.description)
            data = job_schema(job)
            if not job.is_active or (job.expiry_date and job.expiry_date<timezone.localdate()):
                return mark_safe('<meta name="robots" content="noindex,follow">')+format_html('<link rel="canonical" href="{}">',canonical)
    elif name == 'career_hub':
        description = 'Explore physiotherapy careers in Canada by city, practice setting and opportunity type. Browse current listings and practical questions to compare roles.'
    elif name == 'career_landing':
        page = context.get('landing',{})
        description = page.get('title','')+'. '+page.get('subtitle','')
        data = {'@context':'https://schema.org','@type':'CollectionPage','name':page.get('title'),'url':canonical,'description':description}
    else:
        description = 'Physiotherapy Jobs Canada connects Canadian clinics and rehabilitation employers with job seekers.'
    html = format_html('<link rel="canonical" href="{}">', canonical)
    if name == 'job_list' and any(request.GET.get(k) for k in ('q','location','job_type')):
        html += mark_safe('<meta name="robots" content="noindex,follow">')
    if description:
        description = re.sub(r'\s+',' ',description).strip()[:165]
        html += format_html('<meta name="description" content="{}"><meta property="og:description" content="{}"><meta property="og:url" content="{}">',description,description,canonical)
    if data: html += json_script(data)
    return html
