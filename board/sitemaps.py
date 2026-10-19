from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Job
from django.db.models import Q
from django.utils import timezone
from types import SimpleNamespace
from urllib.parse import urlsplit
from .seo_config import SITE


class CanonicalSitemap(Sitemap):
    protocol = "https"

    def get_urls(self, page=1, site=None, protocol=None):
        canonical_site = SimpleNamespace(domain=urlsplit(SITE).netloc, name="Physiotherapy Jobs Canada")
        return super().get_urls(page=page, site=canonical_site, protocol="https")


class StaticViewSitemap(CanonicalSitemap):
    protocol = "https"
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        from .seo_pages import PAGES
        return ["home", "job_list", "career_hub"] + list(PAGES)

    def location(self, item):
        from .seo_pages import PAGES
        return reverse("career_landing", args=[item]) if item in PAGES else reverse(item)


class ProvinceSitemap(CanonicalSitemap):
    protocol = "https"
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return [
            "province_ontario",
            "province_bc",
            "province_alberta",
            "province_saskatchewan",
            "province_manitoba",
            "province_quebec",
            "province_nova_scotia",
            "province_new_brunswick",
            "province_newfoundland",
            "province_pei",
        ]

    def location(self, item):
        return reverse(item)


class JobSitemap(CanonicalSitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return Job.objects.filter(is_active=True).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.localdate())
        )

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)