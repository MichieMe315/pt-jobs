from django.core.management.base import BaseCommand
from board.models import WidgetTemplate

WIDGETS = [
    {
        "slug": "recent_jobs_embed",
        "title": "Recent Jobs (Embeddable)",
        "html": """<iframe src="https://YOUR_DOMAIN/embed/recent-jobs" style="width:100%;height:520px;border:0;" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>""",
    }
]

class Command(BaseCommand):
    help = "Seed default widget templates (safe upsert)."

    def handle(self, *args, **options):
        created, updated = 0, 0
        for w in WIDGETS:
            obj, was_created = WidgetTemplate.objects.update_or_create(
                slug=w["slug"],
                defaults={"title": w["title"], "html": w["html"]},
            )
            created += 1 if was_created else 0
            updated += 0 if was_created else 1
        self.stdout.write(self.style.SUCCESS(f"WidgetTemplates — created: {created}, updated: {updated}"))
