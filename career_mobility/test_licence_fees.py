from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.core.management import call_command
from .models import ProvincialLicenceFee

class ProvincialFeeTests(TestCase):
    def test_cannot_publish_without_official_evidence(self):
        fee = ProvincialLicenceFee(province="Ontario", regulator="Regulator", fee_type="initial", description="Registration", amount_cad=Decimal("100"), is_published=True)
        with self.assertRaises(ValidationError):
            fee.save()

    def test_complete_evidence_can_publish(self):
        fee = ProvincialLicenceFee(province="Ontario", regulator="Regulator", fee_type="initial", description="Registration", amount_cad=Decimal("100"), source_url="https://example.org/fees", effective_on=date(2026, 1, 1), verified_on=date(2026, 10, 1), is_published=True)
        fee.save()
        self.assertEqual(ProvincialLicenceFee.objects.filter(is_published=True).count(), 1)

    def test_seed_is_idempotent_and_unpublished(self):
        call_command("seed_licence_fee_review", verbosity=0)
        count = ProvincialLicenceFee.objects.count()
        call_command("seed_licence_fee_review", verbosity=0)
        self.assertEqual(ProvincialLicenceFee.objects.count(), count)
        self.assertEqual(ProvincialLicenceFee.objects.filter(is_published=True).count(), 0)


from django.test import SimpleTestCase
from .private_storage import PrivateMobilityStorage
class PrivateGuideStorageTests(SimpleTestCase):
    def test_private_guides_have_no_public_url(self):
        with self.assertRaises(ValueError):
            PrivateMobilityStorage().url("career_mobility/products/guide.pdf")
