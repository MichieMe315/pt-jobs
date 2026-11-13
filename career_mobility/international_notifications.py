import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.urls import NoReverseMatch, reverse
from django.utils.html import escape
from board.notification_mail import email_frame
from board.models import SiteSettings
from .models import ProductOrder, InternationalActivity


def send(subject,text,to,html,reply_to=None):
    if not to:return
    try:
        mail=EmailMultiAlternatives(subject,text,settings.DEFAULT_FROM_EMAIL,to,reply_to=reply_to)
        mail.attach_alternative(email_frame(subject,html),'text/html');mail.send(fail_silently=False)
    except Exception:
        logging.getLogger(__name__).exception('International account email could not be sent')


def new_account_mail(request,profile):
    ss=SiteSettings.objects.first();admin_email=getattr(ss,'contact_email','')
    review=request.build_absolute_uri(reverse('admin:career_mobility_internationalprofile_change',args=[profile.pk]))
    text=f'{profile.user.email} created an international planning account. Education: {profile.country_of_education}. Residence: {profile.residence_country}. Destination: {profile.destination_province or "Undecided"}. Review: {review}'
    send('[PTJC] New international account',text,[admin_email] if admin_email else [],'<p>'+escape(text)+'</p><p><a href="'+escape(review)+'">Review international profile</a></p>',[profile.user.email])
    url=request.build_absolute_uri(reverse('mobility_international_dashboard'))
    send('[PTJC] Your international planning account',f'Your account is ready. Open your checklist and resources: {url}',[profile.user.email],'<p>Your international planning account is ready.</p><p><a href="'+escape(url)+'">Open your checklist and resources</a></p><p>This is separate from the Canadian job seeker directory. It does not establish Canadian registration or work authorization.</p>')


def confirm_purchase(order_id,site_base):
    from django.db import DatabaseError
    try:
        return _confirm_purchase(order_id,site_base)
    except DatabaseError:
        logging.getLogger(__name__).exception('Purchase saved; international activity or receipt lookup failed')


def _confirm_purchase(order_id,site_base):
    order=ProductOrder.objects.select_related('user','product').get(pk=order_id)
    from urllib.parse import urljoin
    try:
        download=urljoin(site_base,reverse('mobility_resource_library'))
    except NoReverseMatch:
        # Fulfil and record payments even when the customer pages are offline.
        download=None
    profile=getattr(order.user,'international_pt_profile',None)
    if not profile:
        if download:
            send('[PTJC] Your download is ready',f'{order.product.title} is ready: {download}',[order.user.email],'<p>'+escape(order.product.title)+'</p><p><a href="'+escape(download)+'">Download purchased resource</a></p>')
        return
    checkout=InternationalActivity.objects.filter(event_key='checkout:'+order.stripe_session_id).first()
    event,created=InternationalActivity.objects.get_or_create(event_key=f'paid:{order.pk}',defaults={
        'profile':profile,'action':'purchase_confirmed','visitor_country':checkout.visitor_country if checkout else '', 'education_country':profile.country_of_education,
        'residence_country':profile.residence_country,'subject':order.product.slug})

    if created and download:
        text=f'{order.product.title} is ready in your resource library. Sign in to download: {download}'
        send('[PTJC] Your download is ready',text,[order.user.email],'<p>'+escape(order.product.title)+'</p><p><a href="'+escape(download)+'">Download purchased resource</a></p>')
        ss=SiteSettings.objects.first();to=getattr(ss,'contact_email','')
        review=urljoin(site_base,reverse('admin:career_mobility_productorder_change',args=[order.pk]))
        text=f'{order.user.email} purchased {order.product.title}. Education: {profile.country_of_education}. Residence: {profile.residence_country}. Review: {review}'
        send('[PTJC] Digital resource purchased',text,[to] if to else [],'<p>'+escape(text)+'</p><p><a href="'+escape(review)+'">Review purchase</a></p>',[order.user.email])
