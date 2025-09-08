from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("employers/", views.employer_list, name="employer_list"),
    path("packages/", views.package_list, name="package_list"),
    path("checkout/start/<int:package_id>/", views.checkout_start, name="checkout_start"),
]
