from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = "Fix Postgres sequences"

    def handle(self, *args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT setval('board_invoice_id_seq', (SELECT MAX(id) FROM board_invoice));
            """)
            cursor.execute("""
                SELECT setval('board_purchasedpackage_id_seq', (SELECT MAX(id) FROM board_purchasedpackage));
            """)

        self.stdout.write(self.style.SUCCESS("Sequences repaired"))
