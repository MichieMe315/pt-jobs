"""Publish only the completed job explicitly linked to a new paid checkout."""
import hashlib,json,logging
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import F,Q
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.utils import timezone
from django.urls import reverse
from .models import Employer,Job,JobPublicationRequest,PurchasedPackage
logger=logging.getLogger(__name__)
PENDING=('waiting','ready','review')

def fingerprint(job):
    fields=('title','description','job_type','compensation_type','compensation_min','compensation_max','location','apply_via','apply_email','apply_url','relocation_assistance','source')
    data={f:getattr(job,f) for f in fields}
    return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()

@transaction.atomic
def request_publication(job,*,reuse=False):
    Employer.objects.select_for_update().get(pk=job.employer_id)
    if reuse:
        current=JobPublicationRequest.objects.filter(job=job,status='waiting',fingerprint=fingerprint(job)).first()
        if current:return current
    JobPublicationRequest.objects.filter(job=job,status__in=PENDING).update(status='cancelled',last_error='Replaced by a newer publication request.')
    return JobPublicationRequest.objects.create(job=job,employer_id=job.employer_id,fingerprint=fingerprint(job))

def cancel_requests(job):
    JobPublicationRequest.objects.filter(job=job,status__in=PENDING).update(status='cancelled',last_error='Job saved as a draft or published separately.')

def pending_for(employer,token=None):
    rows=JobPublicationRequest.objects.filter(employer=employer,status__in=PENDING,job__is_active=False).select_related('job')
    if token:
        try:return rows.filter(pk=token).first()
        except (ValueError,TypeError,ValidationError):return None
    return rows.first()

def checkout_request(request,employer):
    # Only this explicit field can select a different saved job. Never take arbitrary job IDs from Stripe metadata.
    if 'publish_job_id' in request.POST:
        raw=request.POST.get('publish_job_id','')
        if not raw:return None
        try:job=Job.objects.get(pk=int(raw),employer=employer,is_active=False)
        except (ValueError,TypeError,Job.DoesNotExist):raise ValueError('Choose one of your saved jobs, or buy credits only.')
        return request_publication(job,reuse=True)
    token=request.POST.get('publication') or request.GET.get('publication')
    intent=pending_for(employer,token)
    if token and not intent:raise ValueError('This publication request is no longer available. Review your saved job before continuing.')
    return intent

def duration_for(package):
    return max(1,int(package.duration_days or package.package.duration_days or 30))

def refresh_window(job,duration):
    job.posting_date=timezone.localdate()
    job.expiry_date=job.posting_date+timedelta(days=duration-1)
    job.expiry_email_sent=False

def finish_direct(job,package):
    if package:
        refresh_window(job,duration_for(package))
        job.save(update_fields=['posting_date','expiry_date','expiry_email_sent'])
    cancel_requests(job)

def notify_publication(job_id):
    from .views import send_templated_email,_admin_emails
    try:
        job=Job.objects.select_related('employer__user').get(pk=job_id)
        base=getattr(settings,'SITE_URL','https://physiotherapyjobscanada.ca').rstrip('/')
        context={'job_title':job.title,'email':job.employer.email or job.employer.user.email,'employer_email':job.employer.email,'job_id':job.pk,'dashboard_url':base+reverse('employer_dashboard'),'next_step':'Your job is published. View it on the job board.','next_step_url':base+reverse('job_detail',args=[job.pk]),'review_url':base+reverse('admin:board_job_change',args=[job.pk])}
        send_templated_email('job_posting_confirmation',[context['email']] if context['email'] else [],context)
        send_templated_email('admin_job_posted',_admin_emails(),context)
    except Exception:logger.exception('Publication notification failed for job %s',job_id)

@transaction.atomic
def publish_paid_request(intent_id,employer_id,purchase,invoice):
    """Fulfil a new checkout's explicit job instruction; never search old jobs."""
    from .views import _sync_employer_credits
    employer=Employer.objects.select_for_update().select_related('user').get(pk=employer_id)
    try:intent=JobPublicationRequest.objects.select_for_update().get(pk=intent_id,employer=employer)
    except (JobPublicationRequest.DoesNotExist,ValueError,TypeError,ValidationError):
        logger.warning('Paid checkout has an invalid saved-job reference for employer %s',employer_id)
        return None
    # Older paid/review requests are not retroactively executed.
    if intent.status!='waiting':return intent
    job=Job.objects.select_for_update().get(pk=intent.job_id,employer=employer)
    error=''
    if not employer.is_approved or not employer.login_active or not employer.user.is_active:
        error='Employer approval is required before publication. Your posting credit is available.'
    elif job.is_active:
        intent.status='cancelled'
        error='This job is already published. Your purchased credit remains available.'
    elif fingerprint(job)!=intent.fingerprint:
        error='Your saved job changed after checkout began. Review it and publish using your available credit.'
    else:
        from .forms import JobForm
        data=model_to_dict(job,fields=JobForm.Meta.fields)
        data['expiry_date']=timezone.localdate()+timedelta(days=duration_for(purchase)-1)
        data['relocation_assistance']='yes' if job.relocation_assistance else 'no'
        if not JobForm(data,instance=job,max_expiry_date=data['expiry_date']).is_valid():
            error='Complete the required job details, then click Publish. Your posting credit is available.'
    if not error:
        consumed=PurchasedPackage.objects.filter(pk=purchase.pk,employer=employer,credits_remaining__gt=0).filter(Q(expires_at__isnull=True)|Q(expires_at__gte=timezone.now())).update(credits_remaining=F('credits_remaining')-1)
        if not consumed:error='Your posting credit is unavailable. No job was published.'
    intent.invoice=invoice
    intent.purchased_package=purchase
    if error:
        if intent.status!='cancelled':intent.status='review'
        intent.last_error=error
        intent.save(update_fields=['status','last_error','invoice','purchased_package'])
        return intent
    job.is_active=True
    refresh_window(job,duration_for(purchase))
    job.save(update_fields=['is_active','posting_date','expiry_date','expiry_email_sent'])
    intent.status='published';intent.published_at=timezone.now();intent.last_error=''
    intent.save(update_fields=['status','published_at','last_error','invoice','purchased_package'])
    _sync_employer_credits(employer)
    transaction.on_commit(lambda:notify_publication(job.pk))
    return intent

def checkout_idempotency_key(request,package,amount,publication,discount_code=""):
    import uuid
    if publication:token=str(publication.pk)
    else:
        token=request.session.get('credit_checkout_token')
        if not token:token=str(uuid.uuid4());request.session['credit_checkout_token']=token
    terms=f'publish-v2|{package.pk}|{package.name}|{package.credits}|{package.duration_days}|{package.package_expires_days}|{amount}|{discount_code}|{token}'
    return 'ptjc-posting-'+hashlib.sha256(terms.encode()).hexdigest()
