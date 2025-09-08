from django.conf import settings

def maps_api_key(request):
    """
    Adds GOOGLE_MAPS_API_KEY into every template as GOOGLE_MAPS_API_KEY.
    """
    return {"GOOGLE_MAPS_API_KEY": getattr(settings, "GOOGLE_MAPS_API_KEY", "")}
