from django.urls import path
from . import views

urlpatterns = [
    # Custom login that enforces approval and routes based on role
    path("login/", views.ApprovedLoginView.as_view(), name="login"),

    # Signups + pending
    path("signup/employer/", views.employer_signup, name="employer_signup"),
    path("signup/jobseeker/", views.jobseeker_signup, name="jobseeker_signup"),
    path("pending/", views.account_pending, name="account_pending"),

    # Dashboards
    path("employer/dashboard/", views.employer_dashboard, name="employer_dashboard"),
    path("jobseeker/dashboard/", views.jobseeker_dashboard, name="jobseeker_dashboard"),
]
