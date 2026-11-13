"""Email ownership confirmation for international accounts; no nationality rules."""
import logging
import time
from smtplib import SMTPResponseException
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from .models import InternationalProfile
log=logging.getLogger(__name__)
class VerificationToken(PasswordResetTokenGenerator):
    key_salt='ptjc.international.email.verification'
    def _make_hash_value(self,user,timestamp):
        profile=user.international_pt_profile
        return f'{user.pk}|{user.password}|{user.email}|{profile.email_verified_at}|{timestamp}'
tokens=VerificationToken()

def send_verification(request,profile):
    now=timezone.now()
    # A database condition enforces resend cooldown across sessions and tabs.
    from django.db.models import Q
    updated=InternationalProfile.objects.filter(pk=profile.pk).filter(Q(email_verified_at__isnull=True)|~Q(email_verified_address=profile.user.email)).filter(Q(verification_sent_at__isnull=True)|Q(verification_sent_at__lt=now-timedelta(minutes=2))).update(verification_sent_at=now)
    if not updated:return False
    url=request.build_absolute_uri(reverse('mobility_verify_email',args=[urlsafe_base64_encode(force_bytes(profile.user_id)),tokens.make_token(profile.user)]))
    from board.notification_mail import email_frame
    from django.utils.html import format_html
    body=format_html('<p>Confirm your email address to open your international planning dashboard.</p><p><a href="{}">Verify my email address</a></p><p>If you did not create this account, ignore this email.</p>',url)
    msg=EmailMultiAlternatives('Verify your PTJC International email',f'Confirm your email address to open your international planning dashboard:\n\n{url}\n\nIf you did not create this account, ignore this email.',settings.DEFAULT_FROM_EMAIL,[profile.user.email])
    try:
        msg.attach_alternative(email_frame('Verify your email address',body),'text/html')
        for attempt in range(3):
            try:
                sent=msg.send(fail_silently=False)
                break
            except SMTPResponseException as error:
                if not (400 <= error.smtp_code < 500) or attempt == 2:
                    raise
                time.sleep(attempt + 1)
        if sent != 1:
            raise RuntimeError('The configured email backend did not accept the verification message')
    except Exception:
        InternationalProfile.objects.filter(pk=profile.pk).update(verification_sent_at=None)
        log.exception('International verification email could not be sent')
        return False
    return True

@never_cache
@login_required(login_url='mobility_international_login')
def pending(request):
    profile=getattr(request.user,'international_pt_profile',None)
    if profile is None:return redirect('mobility_international')
    if profile.email_is_verified:return redirect('mobility_international_dashboard')
    local_console = settings.DEBUG and (settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend' or (
        settings.EMAIL_BACKEND == 'board.email_audit_backend.EmailBackend' and
        settings.PTJC_EMAIL_TRANSPORT == 'django.core.mail.backends.console.EmailBackend'))
    if request.method=='GET' and not profile.verification_sent_at:
        if not send_verification(request,profile):messages.warning(request,'Your verification email could not be sent. Try resending or contact PTJC.')
    if request.method=='POST':
        sent=send_verification(request,profile)
        profile.refresh_from_db()
        if sent:messages.success(request,'Verification link printed in the runserver terminal.' if local_console else 'Verification email submitted for delivery. Check your inbox and spam folder.')
        elif profile.verification_sent_at:messages.info(request,'Please wait two minutes before requesting another email.')
        else:messages.error(request,'The verification email could not be sent. Please try again. Your account and saved plan are safe.')
    profile.refresh_from_db()
    return render(request,'career_mobility/verify_email.html',{'profile':profile,'local_console':local_console})

@never_cache
def confirm(request,uidb64,token):
    try:uid=force_str(urlsafe_base64_decode(uidb64));profile=InternationalProfile.objects.select_related('user').get(user_id=uid)
    except (ValueError,TypeError,OverflowError,UnicodeDecodeError,InternationalProfile.DoesNotExist):profile=None
    if profile and not profile.email_is_verified and tokens.check_token(profile.user,token):
        InternationalProfile.objects.filter(pk=profile.pk).update(email_verified_at=timezone.now(),email_verified_address=profile.user.email)
        messages.success(request,'Email verified. Your international dashboard is ready.')
        if request.user.is_authenticated and request.user.pk==profile.user_id:
            from django.utils.http import url_has_allowed_host_and_scheme
            next_url=request.session.pop('international_verified_next','')
            if not url_has_allowed_host_and_scheme(next_url,allowed_hosts={request.get_host()},require_https=request.is_secure()):next_url=''
            return redirect(next_url or 'mobility_international_dashboard')
        return redirect('mobility_international_login')
    return render(request,'career_mobility/verify_email.html',{'invalid':True},status=400)

class InternationalVerificationMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):return self.get_response(request)
    def process_view(self,request,view,args,kwargs):
        if not request.user.is_authenticated:return None
        match=request.resolver_match
        if not match:return None
        protected={'mobility_international_dashboard','mobility_international_profile_update','mobility_checklist_toggle','mobility_personalized_checklist','mobility_country_guide','mobility_product_success','mobility_international_save','mobility_international_capture','mobility_resource_library','mobility_product_checkout','mobility_product_download'}
        public_resume={'start','public_step','public_save','public_preview'}
        if 'ptjc_resumes' in match.namespaces and match.url_name in public_resume:return None
        if match.url_name not in protected and 'ptjc_resumes' not in match.namespaces:return None
        profile=getattr(request.user,'international_pt_profile',None)
        if profile and not profile.email_is_verified:
            return redirect('mobility_verify_pending')
        return None
urlpatterns=[path('international/verify/',pending,name='mobility_verify_pending'),path('international/verify/<uidb64>/<token>/',confirm,name='mobility_verify_email')]
