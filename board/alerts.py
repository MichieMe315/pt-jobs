from django.conf import settings
from django.core import signing
from django.urls import reverse


def unsubscribe_token(alert):
    return signing.dumps({'id': alert.pk, 'email': alert.email}, salt='board.job-alert-unsubscribe')


def unsubscribe_url(alert):
    base = getattr(settings, 'SITE_URL', 'https://physiotherapyjobscanada.ca').rstrip('/')
    return base + reverse('job_alert_unsubscribe', args=[unsubscribe_token(alert)])
