from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Count
from board.models import Invoice


class Command(BaseCommand):
    help = 'Read-only checks before applying the production repair migrations.'

    def handle(self, *args, **options):
        tables = set(connection.introspection.table_names())
        applied = MigrationRecorder(connection).applied_migrations()
        for table, migration in [
            ('board_careerfitlead', '0004_careerfitlead'),
            ('board_jobalertdelivery', '0005_jobalertdelivery'),
        ]:
            if table in tables and ('board', migration) not in applied:
                raise CommandError(f'{table} already exists without its migration record. Reconcile schema/history before deploying; do not fake migrations blindly.')
        if 'board_invoice' in tables:
            duplicates = Invoice.objects.filter(processor='stripe').exclude(processor_reference='').values('processor_reference').annotate(n=Count('pk')).filter(n__gt=1).count()
            if duplicates:
                raise CommandError(f'{duplicates} duplicate Stripe payment references exist. Review existing fulfilments before rollout.')
        self.stdout.write(self.style.SUCCESS('Repair migration preflight passed (read-only).'))
