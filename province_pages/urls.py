"""
Province SEO Pages URL Configuration
Add to your main urls.py: path("", include("province_pages.urls")),
"""
from django.urls import path
from . import views

# Province slugs mapped to their view names
PROVINCE_SLUGS = [
    ("ontario", "Ontario"),
    ("british-columbia", "British Columbia"),
    ("alberta", "Alberta"),
    ("saskatchewan", "Saskatchewan"),
    ("manitoba", "Manitoba"),
    ("quebec", "Quebec"),
    ("nova-scotia", "Nova Scotia"),
    ("new-brunswick", "New Brunswick"),
    ("newfoundland-and-labrador", "Newfoundland and Labrador"),
    ("prince-edward-island", "Prince Edward Island"),
]

urlpatterns = [
    path("physiotherapy-jobs-ontario/", views.ontario_view, name="province_ontario"),
    path("physiotherapy-jobs-british-columbia/", views.british_columbia_view, name="province_bc"),
    path("physiotherapy-jobs-alberta/", views.alberta_view, name="province_alberta"),
    path("physiotherapy-jobs-saskatchewan/", views.saskatchewan_view, name="province_saskatchewan"),
    path("physiotherapy-jobs-manitoba/", views.manitoba_view, name="province_manitoba"),
    path("physiotherapy-jobs-quebec/", views.quebec_view, name="province_quebec"),
    path("physiotherapy-jobs-nova-scotia/", views.nova_scotia_view, name="province_nova_scotia"),
    path("physiotherapy-jobs-new-brunswick/", views.new_brunswick_view, name="province_new_brunswick"),
    path("physiotherapy-jobs-newfoundland-and-labrador/", views.newfoundland_view, name="province_newfoundland"),
    path("physiotherapy-jobs-prince-edward-island/", views.prince_edward_island_view, name="province_pei"),
]
