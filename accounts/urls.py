from django.urls import path
from . import views

urlpatterns = [
    path("signup/employer/", views.employer_signup, name="employer_signup"),
    path("signup/jobseeker/", views.jobseeker_signup, name="jobseeker_signup"),
]
