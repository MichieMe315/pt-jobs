from django.core.management.base import BaseCommand
from career_mobility.models import ProvincialLicenceFee

# Review placeholders, not asserted fees. Provincial rules may differ by applicant category.
JURISDICTIONS = [
    ("Alberta", "College of Physiotherapists of Alberta"),
    ("British Columbia", "College of Health and Care Professionals of BC"),
    ("Manitoba", "College of Physiotherapists of Manitoba"),
    ("New Brunswick", "College of Physiotherapists of New Brunswick"),
    ("Newfoundland and Labrador", "Newfoundland and Labrador College of Physiotherapists"),
    ("Nova Scotia", "Nova Scotia College of Physiotherapists"),
    ("Ontario", "College of Physiotherapists of Ontario"),
    ("Prince Edward Island", "Prince Edward Island College of Physiotherapists"),
    ("Quebec", "Ordre professionnel de la physiothérapie du Québec"),
    ("Saskatchewan", "Saskatchewan College of Physical Therapists"),
]

class Command(BaseCommand):
    help = "Create unpublished provincial fee research placeholders; never invent or overwrite fee amounts."

    def handle(self, *args, **options):
        created = 0
        for province, regulator in JURISDICTIONS:
            for fee_type, description in (("application", "Application / assessment fee — verify"), ("initial", "Initial registration fee — verify"), ("renewal", "Annual renewal fee — verify")):
                _, was_created = ProvincialLicenceFee.objects.get_or_create(
                    province=province, fee_type=fee_type, description=description,
                    defaults={"regulator": regulator, "is_published": False, "notes": "Research placeholder only. Confirm fee, applicant eligibility, tax, effective date and official URL."},
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Created {created} unpublished research records."))
