"""Employer-only segmentation and exports. No email delivery side effects."""
import csv
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Q,Count,Max,Case,When,Value,CharField,F
from django.db.models.functions import Coalesce,NullIf,StrIndex,Substr,Trim
from django.http import HttpResponse
from django.utils import timezone
from board.models import EmployerMarketingProfile,MarketingSuppression
from .generator import PROVINCES

BLOCKED={'do_not_email','unsubscribed','bounced'}
def annotate_employers(qs):
    today=timezone.localdate()
    conditions=[When(Q(marketing_profile__province=code)|Q(location__iregex=rf'(^|,|\s-\s)\s*({code}|{full})(\s*,\s*Canada)?\s*$',marketing_profile__province=''),then=Value(full)) for code,full in PROVINCES.items()]
    # Missing marketing profiles also use the employer's existing location.
    conditions += [When(Q(marketing_profile__isnull=True)&Q(location__iregex=rf'(^|,|\s-\s)\s*({code}|{full})(\s*,\s*Canada)?\s*$'),then=Value(full)) for code,full in PROVINCES.items()]
    return qs.annotate(_comma=StrIndex('location',Value(','))).annotate(
        _marketing_city=Coalesce(NullIf('marketing_profile__city',Value('')),Trim(Case(When(_comma__gt=0,then=Substr('location',1,F('_comma')-1)),default=F('location'),output_field=CharField()))),
        _marketing_province=Case(*conditions,default=Value(''),output_field=CharField()),
        _active_jobs=Count('jobs',filter=Q(jobs__is_active=True)&(Q(jobs__expiry_date__gte=today)|Q(jobs__expiry_date__isnull=True)),distinct=True),
        _last_paid=Max('invoices__order_date',filter=Q(invoices__status='paid')),
        _contact_status=Coalesce('marketing_profile__contact_status',Value('unreviewed')),
    ).select_related('marketing_profile')

def exportable(employers):
    suppressed={email.strip().lower() for email in MarketingSuppression.objects.values_list('email',flat=True)}
    # A block on any duplicate employer record blocks the shared address.
    suppressed.update(str(email or '').strip().lower() for email in EmployerMarketingProfile.objects.filter(contact_status__in=BLOCKED).values_list('employer__email',flat=True))
    seen=set()
    for employer in employers:
        email=(employer.email or '').strip().lower();profile=getattr(employer,'marketing_profile',None)
        if not employer.login_active or not profile or profile.contact_status!='ready' or not profile.outreach_basis.strip() or email in suppressed or email in seen:continue
        try:validate_email(email)
        except ValidationError:continue
        seen.add(email);yield employer,email

def csv_response(employers,filename='ptjc-reviewed-marketing-audience.csv'):
    response=HttpResponse(content_type='text/csv; charset=utf-8');response['Content-Disposition']=f'attachment; filename="{filename}"';response.write('\ufeff');writer=csv.writer(response)
    writer.writerow(['Employer ID','Company','Email','Location','Community category','Organization type','Tags','Outreach basis'])
    def safe(value):
        value=str(value or '')
        return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
    for employer,email in exportable(employers):
        profile=employer.marketing_profile
        writer.writerow([safe(v) for v in [employer.pk,employer.company_name,email,employer.location,profile.get_settlement_display(),profile.get_organization_type_display(),profile.tags,profile.outreach_basis]])
    return response
