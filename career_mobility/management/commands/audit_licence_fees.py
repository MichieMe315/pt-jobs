from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from career_mobility.models import ProvincialLicenceFee

class Command(BaseCommand):
    help = "Report missing, stale and expired provincial licence fee evidence; does not change published data."
    def handle(self, *args, **options):
        today = timezone.localdate()
        count = 0
        for fee in ProvincialLicenceFee.objects.all():
            issues = []
            if not fee.has_publishable_evidence: issues.append("missing evidence")
            if fee.verified_on and fee.verified_on < today - timedelta(days=90): issues.append("verification older than 90 days")
            if fee.expires_on and fee.expires_on < today: issues.append("expired")
            if issues:
                count += 1
                self.stdout.write(f"{fee.pk} | {fee.province} | {fee.description}: {', '.join(issues)}")
        self.stdout.write(f"{count} fee records need review.")
