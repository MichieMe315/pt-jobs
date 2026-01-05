# board/context.py
from django.conf import settings

def branding(request):
    """
    Exposes branding + Mapbox token to every template.
    """
    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "physiotherapyjobscanada.ca"),
        "MAPBOX_TOKEN": getattr(settings, "MAPBOX_PUBLIC_TOKEN", ""),
    }
