from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Job


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return ["home", "job_list"]

    def location(self, item):
        return reverse(item)


class ProvinceSitemap(Sitemap):
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


class JobSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return Job.objects.filter(is_active=True)

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)