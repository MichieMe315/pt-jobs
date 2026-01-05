from django.urls import path
from django.contrib.auth import views as auth_views

from . import views as v

urlpatterns = [
    # Public
    path("", v.home, name="home"),
    path("about/", v.about, name="about"),
    path("contact/", v.contact, name="contact"),
    path("terms/", v.terms, name="terms"),

    # Auth
    path("login/", v.login_view, name="login"),
    path("logout/", v.logout_view, name="logout"),

    # Password reset (restores your "Forgot password" flow)
    path("password-reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),

    # Job Alerts (footer expects this exact name)
    path("job-alerts/signup/", v.job_alert_signup, name="job_alert_signup"),

    # Employers
    path("employers/", v.employer_list, name="employer_list"),
    path("employers/signup/", v.employer_signup, name="employer_signup"),
    path("employers/<int:employer_id>/", v.employer_detail, name="employer_detail"),
    path("employer/dashboard/", v.employer_dashboard, name="employer_dashboard"),
    path("employer/profile/", v.employer_profile_edit, name="employer_profile_edit"),

    # Job Seekers
    path("jobseekers/signup/", v.jobseeker_signup, name="jobseeker_signup"),
    path("jobseeker/dashboard/", v.jobseeker_dashboard, name="jobseeker_dashboard"),
    path("jobseeker/profile/", v.jobseeker_profile_edit, name="jobseeker_profile_edit"),

    # Jobs
    path("jobs/", v.job_list, name="job_list"),
    path("jobs/new/", v.job_create, name="job_create"),
    path("jobs/<int:job_id>/", v.job_detail, name="job_detail"),
    path("jobs/<int:job_id>/edit/", v.job_edit, name="job_edit"),
    path("jobs/<int:job_id>/duplicate/", v.job_duplicate, name="job_duplicate"),
    path("jobs/<int:job_id>/apply/", v.job_apply, name="apply_to_job"),

    # Packages
    path("packages/", v.package_list, name="package_list"),
    path("packages/<int:package_id>/buy/", v.buy_package, name="buy_package"),
    path("packages/<int:package_id>/buy/select/", v.checkout_select, name="checkout_select"),

    # Checkout (restored)
    path("checkout/start/<int:package_id>/", v.checkout_start, name="checkout_start"),
    path("checkout/success/", v.checkout_success, name="checkout_success"),
    path("checkout/paypal/success/", v.paypal_success, name="paypal_success"),

    # Stripe session creation (required by checkout.html template)
    path("stripe/create-session/<int:package_id>/", v.stripe_create_session, name="stripe_create_session"),

    # Invoices
    path("invoices/<int:invoice_id>/", v.invoice_detail, name="invoice_detail"),
    path("invoices/<int:invoice_id>/download/", v.invoice_download, name="invoice_download"),

    # Admin dashboard (embedded in templates/admin/index.html)
    path("admin/dashboard/", v.admin_dashboard, name="admin_dashboard"),
]
