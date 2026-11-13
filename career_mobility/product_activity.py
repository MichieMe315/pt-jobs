"""Record product milestones without draft data, artwork or personal details."""
from django.db import DatabaseError, transaction

from .models import ProductActivity
from .store_eligibility import account_type


def record(product, event, *, request=None, order=None):
    if request and (request.user.is_staff or request.headers.get('DNT') == '1' or request.headers.get('Sec-GPC') == '1'):
        return
    user = order.user if order else request.user
    if user.is_staff:
        return
    defaults = {'product': product, 'event': event, 'account': account_type(user) or 'guest'}
    try:
        with transaction.atomic():
            if order:
                ProductActivity.objects.get_or_create(order=order, event=event, defaults=defaults)
            else:
                ProductActivity.objects.create(**defaults)
    except DatabaseError:
        import logging
        logging.getLogger(__name__).warning('Digital product activity could not be recorded')
