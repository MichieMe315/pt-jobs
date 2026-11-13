from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .international_activity import record

@receiver(user_logged_in,dispatch_uid='ptjc_international_login_activity')
def logged_in(sender,request,user,**kwargs):
    if request and hasattr(user,'international_pt_profile'):
        record(request,'signed_in',profile=user.international_pt_profile)

@receiver(user_logged_out,dispatch_uid='ptjc_international_logout_activity')
def logged_out(sender,request,user,**kwargs):
    if request and user and hasattr(user,'international_pt_profile'):
        record(request,'signed_out',profile=user.international_pt_profile)
