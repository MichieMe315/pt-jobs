"""Named international account activity, kept separate from job seeker records."""
import logging
import uuid
from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from .models import InternationalActivity


def enabled():
    import os
    return getattr(settings,'INTERNATIONAL_PLANNER_ENABLED',False) or os.environ.get('INTERNATIONAL_PLANNER_ENABLED', '0').lower() in ('1','true','yes')


def record(request, action, *, profile=None, page_country='', subject='', event_key=None):
    user=getattr(request,'user',None)
    if getattr(user, 'is_staff', False) or (profile and profile.user.is_staff):
        return
    profile = profile or getattr(user, 'international_pt_profile', None)
    if profile is None and (request.headers.get('DNT') == '1' or request.headers.get('Sec-GPC') == '1'):
        return
    if action not in dict(InternationalActivity.ACTIONS):
        raise ValueError('Unknown international activity')
    if 'international_visit' not in request.session:
        request.session['international_visit'] = str(uuid.uuid4())
    from .geolocation import visitor_country
    values = dict(profile=profile, action=action, visitor_country=visitor_country(request),
        education_country=profile.country_of_education if profile else '',
        residence_country=profile.residence_country if profile else '',
        page_country=page_country[:100], subject=subject[:160],
        visit_hash=salted_hmac('ptjc.international', request.session['international_visit'], algorithm='sha256').hexdigest())
    try:
        # A savepoint prevents an analytics failure from rolling back account/payment work.
        with transaction.atomic():
            if event_key:
                InternationalActivity.objects.get_or_create(event_key=event_key, defaults=values)
            elif InternationalActivity.objects.filter(visit_hash=values['visit_hash'],created_at__date=timezone.localdate()).count()<300:
                InternationalActivity.objects.create(**values)
    except DatabaseError:
        logging.getLogger(__name__).warning('International activity storage unavailable', exc_info=True)
