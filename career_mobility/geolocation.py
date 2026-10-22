"""Approximate visitor country from a local IP database; never persist the IP."""
import ipaddress
import logging
import os
from functools import lru_cache
from pathlib import Path
from django.conf import settings

DATABASE = Path(__file__).parent/'data/dbip-country-lite-2026-10.mmdb'


def client_ip(request):
    # Railway documents X-Real-IP as its client address. Trust it only on Railway,
    # never on a direct local/public Django server accepting arbitrary headers.
    on_railway = bool(os.environ.get('RAILWAY_PROJECT_ID') or os.environ.get('RAILWAY_ENVIRONMENT_ID'))
    address = request.META.get('HTTP_X_REAL_IP') if on_railway else None
    address = address or request.META.get('REMOTE_ADDR', '')
    try:
        parsed=ipaddress.ip_address(address.strip())
        parsed=getattr(parsed,'ipv4_mapped',None) or parsed
        return str(parsed) if parsed.is_global else None
    except (ValueError,AttributeError):
        return None


@lru_cache(maxsize=1)
def _reader(path,modified):
    import maxminddb
    return maxminddb.open_database(path)


def visitor_country(request):
    address=client_ip(request)
    if not address:return ''
    try:
        path=Path(getattr(settings,'PTJC_GEOIP_DATABASE',DATABASE))
        record=_reader(str(path),path.stat().st_mtime_ns).get(address) or {}
        return (record.get('country',{}).get('names',{}).get('en') or '')[:100]
    except (ImportError,OSError,ValueError):
        # Lookup failures must not stop account creation, calculations or payments.
        logging.getLogger(__name__).warning('Visitor country lookup unavailable')
        return ''
