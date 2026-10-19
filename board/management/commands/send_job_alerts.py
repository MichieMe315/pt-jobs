from datetime import timedelta
from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from board.alerts import unsubscribe_url
from board.models import JobAlert, JobAlertDelivery, Job


class Command(BaseCommand):
    help = 'Preview new matching job alerts; --send enables delivery. Run hourly after validation.'

    def add_arguments(self, parser):
        parser.add_argument('--send', action='store_true')
        parser.add_argument('--hours', type=int, default=24)

    def handle(self, *args, **options):
        if options['hours'] < 1:
            raise CommandError('--hours must be positive')
        since = timezone.now() - timedelta(hours=options['hours'])
        base = getattr(settings, 'SITE_URL', 'https://physiotherapyjobscanada.ca').rstrip('/')
        sent = 0
        failed = 0
        for alert_id in JobAlert.objects.filter(active=True).values_list('pk', flat=True).iterator():
            # Serialize overlapping scheduled runs for this subscription.
            with transaction.atomic():
                alert = JobAlert.objects.select_for_update().get(pk=alert_id)
                if not alert.active:
                    continue
                qs = Job.objects.filter(is_active=True, created_at__gte=max(since, alert.created_at)).filter(
                    Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.localdate())
                ).exclude(pk__in=JobAlertDelivery.objects.filter(alert=alert).values('job_id'))
                if alert.q:
                    qs = qs.filter(Q(title__icontains=alert.q) | Q(description__icontains=alert.q))
                if alert.location:
                    qs = qs.filter(location__icontains=alert.location)
                jobs = list(qs.order_by('-created_at', '-pk')[:25])
                if not jobs:
                    continue
                if not options['send']:
                    self.stdout.write(f'Alert {alert.pk}: {len(jobs)} matching jobs (preview only)')
                    continue
                body = 'New jobs matching your alert:\n\n' + '\n\n'.join(
                    f'{j.title} — {j.location}\n{base}{reverse("job_detail", args=[j.pk])}' for j in jobs
                ) + '\n\nUnsubscribe: ' + unsubscribe_url(alert)
                try:
                    message = EmailMessage('New jobs · Physiotherapy Jobs Canada', body, settings.DEFAULT_FROM_EMAIL, [alert.email])
                    if message.send(fail_silently=False) != 1:
                        raise RuntimeError('Email backend did not accept the message')
                except Exception:
                    failed += 1
                    self.stderr.write(f'Alert {alert.pk}: delivery failed; no jobs marked sent')
                    continue
                JobAlertDelivery.objects.bulk_create([JobAlertDelivery(alert=alert, job=j) for j in jobs])
                sent += 1
        self.stdout.write(f'{sent} alert emails sent; {failed} failed')
        if failed:
            raise CommandError('Some alerts failed; rerun to retry unsent jobs')
