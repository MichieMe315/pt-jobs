"""First-party, anonymous calculator counts, independent of Google Analytics."""
import json
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import DatabaseError
from django.http import JsonResponse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import CalculatorUsageEvent

COOKIE = 'ptjc_calculator_session'
SALT = 'ptjc.calculator.usage.v1'
ONCE = {'salary_calculator_view', 'salary_calculator_start', 'salary_comparison_complete'}
EVENTS = {name for name, label in CalculatorUsageEvent.EVENTS}
logger = logging.getLogger(__name__)


@never_cache
@require_POST
def record_usage(request):
    # Respect browser privacy signals and keep staff testing out of public totals.
    if request.user.is_staff or request.headers.get('DNT') == '1' or request.headers.get('Sec-GPC') == '1':
        return JsonResponse({'recorded': False})
    if len(request.body) > 512:
        return JsonResponse({'error': 'Invalid event'}, status=400)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {'event', 'page_id', 'event_id'} or data['event'] not in EVENTS:
            raise ValueError
        page_id, event_id = uuid.UUID(data['page_id']), uuid.UUID(data['event_id'])
    except (ValueError, TypeError, KeyError, AttributeError):
        return JsonResponse({'error': 'Invalid event'}, status=400)
    try:
        session_id = request.get_signed_cookie(COOKIE, salt=SALT, max_age=1800)
        uuid.UUID(session_id)
    except (KeyError, signing.BadSignature, ValueError):
        session_id = str(uuid.uuid4())
    from .geolocation import visitor_country
    country=visitor_country(request)
    session_hash = salted_hmac(SALT, session_id, algorithm='sha256').hexdigest()
    # View/start/complete count once per page load, including retried requests.
    if data['event'] in ONCE:
        event_id = uuid.uuid5(page_id, data['event'])
    try:
        if CalculatorUsageEvent.objects.filter(session_hash=session_hash, created_at__gte=timezone.now()-timedelta(days=1)).count() >= 120:
            return JsonResponse({'recorded': False}, status=429)
        _, created = CalculatorUsageEvent.objects.get_or_create(event_id=event_id, defaults={
            'page_id': page_id, 'session_hash': session_hash, 'event': data['event'], 'country': country,
        })
    except DatabaseError:
        logger.warning('Calculator usage storage unavailable', exc_info=True)
        return JsonResponse({'recorded': False}, status=503)
    response = JsonResponse({'recorded': created})
    response.set_signed_cookie(COOKIE, session_id, salt=SALT, max_age=1800,
        httponly=True, secure=not settings.DEBUG, samesite='Lax', path='/career-resources/')
    return response


def usage_report(request):
    from django.contrib import admin
    from django.http import Http404
    model_admin=admin.site._registry.get(CalculatorUsageEvent)
    if model_admin is None:raise Http404
    return model_admin.changelist_view(request)
