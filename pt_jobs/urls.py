from career_mobility.usage import usage_report
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from board.views import admin_dashboard
from board.posting_monitor import paid_postings
from board.sitemaps import JobSitemap, ProvinceSitemap, StaticViewSitemap

sitemaps = {
    "static": StaticViewSitemap,
    "provinces": ProvinceSitemap,
    "jobs": JobSitemap,
}

urlpatterns = [
    path('admin/paid-postings/',paid_postings,name='paid_postings_report'),
    path('admin/calculator-usage/',admin.site.admin_view(usage_report),name='calculator_usage_report'),

    path("admin/dashboard/", admin_dashboard, name="admin_dashboard"),
    path("admin/", admin.site.urls),

    # Existing app
    path("", include("board.urls")),

    path("", include("province_pages.urls")),

    # New apps (kept separate from board)
    path("marketplace/", include("marketplace.urls")),
    path("career-resources/", include("career_mobility.urls" if settings.CAREER_TOOLS_PREVIEW else "career_mobility.release_urls")),
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
# Keep all unfinished planners, shop routes and shop admin in the local preview.
if settings.CAREER_TOOLS_PREVIEW:
    from career_mobility.views import shop as ptjc_shop_view, shop_admin as ptjc_shop_admin_view
    urlpatterns = [
        path("admin/ptjc-shop/", ptjc_shop_admin_view, name="ptjc_shop_admin"),
        path("shop/", ptjc_shop_view, name="ptjc_shop"),
    ] + urlpatterns
