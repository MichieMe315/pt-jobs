from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),

    # Django auth (login, logout, password reset/change)
    path("accounts/", include("django.contrib.auth.urls")),

    # Your accounts app (signup etc.)
    path("accounts/", include("accounts.urls")),

    # Board app
    path("", include("board.urls")),
]
