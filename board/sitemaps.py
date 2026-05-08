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


class JobSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return Job.objects.filter(is_active=True)

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)