# board/context_processors.py
from django.db.utils import OperationalError, ProgrammingError
from django.core.exceptions import ImproperlyConfigured

def site_settings(request):
    """
    Inject a singleton SiteSettings as `sitesettings` everywhere, but NEVER crash
    if the DB table/columns don't exist yet (pre- or mid-migration).
    """
    # lightweight fallback object with the attributes your templates/admin expect
    class Empty:
        google_analytics_id = ""
        seo_meta_title = ""
        seo_meta_description = ""
        share_facebook = False
        share_instagram = False
        share_reddit = False
        side_banner_html = ""
        bottom_banner_html = ""
        mapbox_token = ""
        def __bool__(self): return False  # so `{% if sitesettings %}` is falsey

    try:
        # Import inside the function so import of models itself doesn't blow up during migrations
        from .models import SiteSettings  # noqa
    except Exception:
        # Model import itself failed (e.g., during migrations) — return safe empty
        return {"sitesettings": Empty()}

    try:
        # Try to fetch the first row; any missing column/table will raise OperationalError/ProgrammingError
        obj = SiteSettings.objects.first()
        return {"sitesettings": obj or Empty()}
    except (OperationalError, ProgrammingError, ImproperlyConfigured):
        # Table/column missing or not ready — return safe empty
        return {"sitesettings": Empty()}
