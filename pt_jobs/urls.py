from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # login/logout/password
    path('accounts/', include('accounts.urls')),
    path('', include('board.urls')),
    path('', RedirectView.as_view(pattern_name='board:home', permanent=False)),
]
