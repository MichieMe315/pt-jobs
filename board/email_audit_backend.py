"""Audit Django mail submissions without changing the configured transport."""
import logging

from django.conf import settings
from django.core.mail import get_connection
from django.core.mail.backends.base import BaseEmailBackend
from django.db import transaction

logger = logging.getLogger(__name__)


class EmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.transport = get_connection(settings.PTJC_EMAIL_TRANSPORT, fail_silently=fail_silently, **kwargs)

    def open(self):
        return self.transport.open()

    def close(self):
        return self.transport.close()

    def send_messages(self, email_messages):
        messages = list(email_messages or ())
        if not messages:
            return 0
        try:
            count = self.transport.send_messages(messages)
        except Exception as exc:
            self.log_messages(messages, "unknown" if len(messages) > 1 else "failed", type(exc).__name__)
            raise
        eligible = [message for message in messages if message.recipients()]
        if eligible:
            outcome = "submitted" if count == len(eligible) else "failed" if not count else "unknown"
            self.log_messages(eligible, outcome, "Partial batch" if outcome == "unknown" else "")
        return count

    @staticmethod
    def log_messages(messages, outcome, detail):
        from .admin_section_models import EmailDeliveryLog
        try:
            # A missing table during rollout must not interrupt email or the caller.
            with transaction.atomic():
                EmailDeliveryLog.objects.bulk_create([
                    EmailDeliveryLog(recipients=", ".join(map(str, message.recipients()))[:1000],
                        subject=str(message.subject)[:255], outcome=outcome, detail=detail)
                    for message in messages if message.recipients()
                ])
        except Exception:
            logger.warning("Email audit rows could not be saved.", exc_info=True)
