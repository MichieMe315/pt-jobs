from pathlib import Path
from django.conf import settings
from django.core.files.storage import FileSystemStorage

from .editable_products import TEMPLATES
from .recovered_products import FILES
from .print_palettes import PRINTABLE_FILES, PALETTES

BUNDLED_FILES = frozenset({
    "bundled/exercise-tracker.pdf",
    "bundled/appointment-notes.pdf",
    "bundled/practice-planner-2027.pdf",
    "bundled/paediatric-physio-journal.pdf",
    "bundled/physio-wall-calendar-2027.pdf",
}) | frozenset("bundled/"+name for name in FILES.values()) | frozenset(f"bundled/{key}.html" for key in TEMPLATES) | frozenset(
    f"bundled/{name.removesuffix('.pdf')}-{theme}.pdf"
    for name in PRINTABLE_FILES for theme in PALETTES
)


class PrivateMobilityStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", str(Path(getattr(settings,"PT_MOBILITY_PRIVATE_ROOT",__import__("os").environ.get("PT_MOBILITY_PRIVATE_ROOT") or settings.BASE_DIR / "private_mobility_guides"))))
        kwargs.setdefault("base_url", None)
        super().__init__(*args, **kwargs)
    def path(self, name):
        if name in BUNDLED_FILES:
            return str(Path(__file__).resolve().parent / "bundled_products" / name.split("/")[-1])
        return super().path(name)

    def url(self, name):
        raise ValueError("Private mobility downloads have no public URL")
