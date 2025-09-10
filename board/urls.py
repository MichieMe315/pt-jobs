from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Public
    path("", views.home, name="home"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),

    # Employers (public)
    path("employers/", views.employer_list, name="employer_list"),
    path("employers/<int:pk>/", views.employer_public_profile, name="employer_public_profile"),

    # Packages & checkout stub
    path("packages/", views.package_list, name="package_list"),
    path("checkout/<slug:code>/", views.checkout_start, name="checkout_start"),

    # Signups
    path("signup/employer/", views.employer_signup, name="employer_signup"),
    path("signup/jobseeker/", views.jobseeker_signup, name="jobseeker_signup"),

    # Alerts
    path("alerts/signup/", views.job_alert_signup, name="job_alert_signup"),

    # Auth
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("post-login/", views.post_login_redirect, name="post_login_redirect"),

    # Password reset (use Django auth views)
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password_reset_complete",
    ),

    # Employer dashboards/actions
    path("employer/dashboard/", views.employer_dashboard, name="employer_dashboard"),
    path("employer/post-job/", views.post_job, name="post_job"),
    path("employer/applications/<int:job_id>/", views.applications_list, name="applications_list"),
    path("employer/profile/edit/", views.employer_profile_edit, name="employer_profile_edit"),
    path("employer/purchases/", views.purchased_products, name="purchased_products"),
    path("employer/invoices/", views.invoices_list, name="invoices_list"),

    # Jobseeker dashboard
    path("jobseeker/dashboard/", views.jobseeker_dashboard, name="jobseeker_dashboard"),
]
