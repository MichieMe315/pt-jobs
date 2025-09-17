from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Public
    path("", views.home, name="home"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/apply/", views.job_apply, name="job_apply"),
    path("jobs/<int:pk>/save/", views.save_job, name="save_job"),
    path("jobs/<int:pk>/unsave/", views.unsave_job, name="unsave_job"),

    # Employers (public directory + profile)
    path("employers/", views.employer_list, name="employer_list"),
    path("employers/<int:pk>/", views.employer_public_profile, name="employer_public_profile"),

    # Signups & alerts
    path("signup/employer/", views.employer_signup, name="employer_signup"),
    path("signup/jobseeker/", views.jobseeker_signup, name="jobseeker_signup"),
    path("alerts/signup/", views.job_alert_signup, name="job_alert_signup"),

    # Auth
    path("login/", auth_views.LoginView.as_view(
        template_name="registration/login.html",
        redirect_authenticated_user=True
    ), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("post-login/", views.post_login_redirect, name="post_login_redirect"),

    # Employer dashboard + actions
    path("employer/dashboard/", views.employer_dashboard, name="employer_dashboard"),
    path("employer/post-job/", views.post_job, name="post_job"),
    path("employer/jobs/<int:pk>/edit/", views.edit_job, name="edit_job"),
    path("employer/jobs/<int:job_id>/applications/", views.applications_list, name="applications_list"),
    path("employer/profile/edit/", views.employer_profile_edit, name="employer_profile_edit"),
    path("employer/purchases/", views.purchased_products, name="purchased_products"),
    path("employer/invoices/", views.invoices_list, name="invoices_list"),
    path("employer/invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),

    # Jobseeker dashboard
    path("jobseeker/dashboard/", views.jobseeker_dashboard, name="jobseeker_dashboard"),
    path("jobseeker/upload-resume/", views.upload_resume, name="upload_resume"),

    # Packages (listing + checkouts)
    path("packages/", views.package_list, name="package_list"),

    # Stripe checkout (unchanged; discount via ?discount=CODE)
    path("packages/<str:code>/checkout/", views.checkout_start, name="checkout_start"),

    # PayPal: page + server APIs for order create/capture
    path("packages/<str:code>/paypal/", views.checkout_paypal, name="checkout_paypal"),
    path("api/paypal/create-order/<str:code>/", views.paypal_create_order, name="paypal_create_order"),
    path("api/paypal/capture-order/<str:code>/", views.paypal_capture_order, name="paypal_capture_order"),
]
