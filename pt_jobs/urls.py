from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from board.sitemaps import StaticViewSitemap, JobSitemap

sitemaps = {
    "static": StaticViewSitemap,
    "jobs": JobSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),

    # Existing app
    path("", include("board.urls")),

    # New apps (kept separate from board)
    path("marketplace/", include("marketplace.urls")),
    path("sponsor-an-international-candidate/", include("international_candidates.urls")),

    # Sitemap and Robots
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
        ),
    ),
]

# Serve uploaded media in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)