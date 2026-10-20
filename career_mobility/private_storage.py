from pathlib import Path
from django.conf import settings
from django.core.files.storage import FileSystemStorage

class PrivateMobilityStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", str(Path(getattr(settings,"PT_MOBILITY_PRIVATE_ROOT",settings.BASE_DIR / "private_mobility_guides"))))
        kwargs.setdefault("base_url", None)
        super().__init__(*args, **kwargs)
    def url(self, name):
        raise ValueError("Private mobility downloads have no public URL")
