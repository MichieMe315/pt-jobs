# pt_jobs/urls.py
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),

    # Existing app
    path("", include("board.urls")),

    # New apps (kept separate from board)
    path("marketplace/", include("marketplace.urls")),
    path("sponsor-an-international-candidate/", include("international_candidates.urls")),
]

# Serve uploaded media in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)