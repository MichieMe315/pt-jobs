from django.urls import path
from . import views

urlpatterns = [
    path("health/", views.health, name="store_health"),
    path("webhook/", views.webhook_placeholder, name="stripe_webhook"),
]
