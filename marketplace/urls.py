from django.urls import path
from . import views

urlpatterns = [
    path("", views.marketplace_home, name="marketplace_home"),
]