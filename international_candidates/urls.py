from django.urls import path
from . import views

urlpatterns = [
    path("", views.public_teaser, name="international_candidates_teaser"),
]