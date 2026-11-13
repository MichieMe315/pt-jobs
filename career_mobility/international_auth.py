"""Password recovery within the separate international account shell."""
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.views import PasswordResetView,PasswordResetDoneView,PasswordResetConfirmView,PasswordResetCompleteView
from django.urls import path,reverse_lazy
class InternationalPasswordResetForm(PasswordResetForm):
    def get_users(self,email):return (u for u in super().get_users(email) if hasattr(u,'international_pt_profile'))
urlpatterns=[
 path('international/password-reset/',PasswordResetView.as_view(form_class=InternationalPasswordResetForm,template_name='career_mobility/password_reset.html',email_template_name='career_mobility/password_reset_email.txt',subject_template_name='career_mobility/password_reset_subject.txt',success_url=reverse_lazy('mobility_international_password_reset_done')),name='mobility_international_password_reset'),
 path('international/password-reset/sent/',PasswordResetDoneView.as_view(template_name='career_mobility/password_reset_done.html'),name='mobility_international_password_reset_done'),
 path('international/reset/<uidb64>/<token>/',PasswordResetConfirmView.as_view(template_name='career_mobility/password_reset_confirm.html',success_url=reverse_lazy('mobility_international_password_reset_complete')),name='mobility_international_password_reset_confirm'),
 path('international/reset/complete/',PasswordResetCompleteView.as_view(template_name='career_mobility/password_reset_complete.html'),name='mobility_international_password_reset_complete'),
]
