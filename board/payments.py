"""One fulfilment path for signed Stripe events and verified browser returns."""
import logging
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Employer, Invoice, PostingPackage, PurchasedPackage

logger = logging.getLogger(__name__)


class InvalidCheckout(ValueError):
    pass


def field(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def positive(value):
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidCheckout('Invalid purchase terms') from exc
    if result < 1:
        raise InvalidCheckout('Invalid purchase terms')
    return result


def notify_order(employer, package, invoice):
    # Notification failures must not turn a committed payment into a retry/500.
    from .views import send_templated_email, _admin_emails
    try:
        send_templated_email('admin_new_order', _admin_emails(), {
            'package_name': package.name, 'employer_email': employer.email, 'invoice_id': invoice.pk,
        })
        email = (employer.email or employer.user.email or '').strip()
        send_templated_email('order_confirmation', [email] if email else [], {
            'email': email, 'package_name': package.name,
        })
    except Exception:
        logger.exception('Order notification failed for invoice %s', invoice.pk)


@transaction.atomic
def fulfill_checkout(session, *, session_id=None, expected_employer_id=None):
    from .views import _sync_employer_credits
    if field(session, 'payment_status') != 'paid':
        raise InvalidCheckout('Payment is not paid')
    reference = field(session, 'id') or session_id
    if not isinstance(reference, str) or not reference or len(reference) > 120:
        raise InvalidCheckout('Missing session reference')
    metadata = field(session, 'metadata', {}) or {}
    employer_id = positive(metadata.get('employer_id'))
    package_id = positive(metadata.get('package_id'))
    if expected_employer_id is not None and employer_id != expected_employer_id:
        raise InvalidCheckout('Payment belongs to another employer')
    try:
        employer = Employer.objects.select_for_update().select_related('user').get(pk=employer_id)
        # A paid checkout must still be honoured after the package is retired.
        package = PostingPackage.objects.get(pk=package_id)
    except (Employer.DoesNotExist, PostingPackage.DoesNotExist) as exc:
        raise InvalidCheckout('Purchase account or package missing') from exc
    existing = Invoice.objects.filter(processor='stripe', processor_reference=reference).first()
    if existing:
        if existing.employer_id != employer_id:
            raise InvalidCheckout('Payment reference already belongs to another account')
        return existing, package, False
    amount = field(session, 'amount_total')
    if amount is None:
        raise InvalidCheckout('Missing payment amount')
    try:
        amount = int(amount)
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidCheckout('Invalid amount') from exc
    currency = str(field(session, 'currency', 'cad')).lower()
    if amount < 0 or currency != 'cad':
        raise InvalidCheckout('Unexpected payment amount or currency')
    if metadata.get('terms_version') == '1':
        credits = positive(metadata.get('credits'))
        duration = positive(metadata.get('duration_days'))
        expiry_days = positive(metadata.get('package_expires_days'))
        try:
            expected_amount = int(metadata['amount_cents'])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidCheckout('Missing amount snapshot') from exc
        if amount != expected_amount:
            raise InvalidCheckout('Payment does not match checkout amount')
    elif metadata.get('terms_version'):
        raise InvalidCheckout('Unknown checkout terms version')
    else:
        # Backwards compatibility for sessions created before this repair.
        credits, duration, expiry_days = int(package.credits), int(package.duration_days), int(package.package_expires_days)
        logger.warning('Fulfilling pre-snapshot checkout %s using legacy package terms', reference)
    # Preserve genuine legacy-only credits when this is the first tracked purchase.
    if employer.credits and not PurchasedPackage.objects.filter(employer=employer).exists():
        legacy = PurchasedPackage.objects.create(
            employer=employer, package=package, credits_granted=employer.credits,
            credits_remaining=employer.credits, source='legacy', duration_days=duration,
        )
        # No historical expiry is known; do not invent one for legacy balances.
        PurchasedPackage.objects.filter(pk=legacy.pk).update(expires_at=None)
    invoice = Invoice.objects.create(
        employer=employer, amount=amount, currency='CAD', processor='stripe', status='paid',
        processor_reference=reference, discount_code=(metadata.get('discount_code') or '')[:40],
    )
    PurchasedPackage.objects.create(
        employer=employer, package=package, credits_granted=credits, credits_remaining=credits,
        duration_days=duration, expires_at=timezone.now() + timedelta(days=expiry_days), source='stripe',
    )
    _sync_employer_credits(employer)
    transaction.on_commit(lambda: notify_order(employer, package, invoice))
    return invoice, package, True
