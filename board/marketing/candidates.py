from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from board.models import CandidateCampaign, CandidateCampaignDelivery, JobSeeker, MarketingSuppression

SALT = 'board.candidate-campaign-unsubscribe'
AUDIENCES = dict(CandidateCampaign.AUDIENCES)
BATCH_SIZE = 25


def eligible_addresses(audience):
    from career_mobility.models import InternationalProfile

    def addresses():
        if audience in ('all', 'jobseekers'):
            yield from JobSeeker.objects.filter(
                marketing_consent=True, login_active=True, is_approved=True, user__is_active=True,
            ).values_list('user__email', flat=True).iterator()
        if audience in ('all', 'international'):
            profiles = InternationalProfile.objects.filter(
                marketing_consent=True, email_verified_at__isnull=False, user__is_active=True,
            ).select_related('user')
            for profile in profiles.iterator():
                if profile.email_is_verified:
                    yield profile.user.email

    blocked = {email.strip().lower() for email in MarketingSuppression.objects.values_list('email', flat=True)}
    result = set()
    for raw in addresses():
        email = (raw or '').strip().lower()
        if email in blocked or email in result:
            continue
        try:
            validate_email(email)
        except ValidationError:
            continue
        result.add(email)
    return result


@require_http_methods(['GET', 'POST'])
def unsubscribe(request, token):
    try:
        email = signing.loads(token, salt=SALT)
        validate_email(email)
    except (signing.BadSignature, ValidationError):
        return render(request, 'board/candidate_unsubscribe.html', {'invalid': True}, status=400)
    if request.method == 'POST':
        MarketingSuppression.objects.get_or_create(email=email, defaults={'reason': 'unsubscribed'})
        JobSeeker.objects.filter(user__email__iexact=email).update(marketing_consent=False)
        from career_mobility.models import InternationalProfile
        InternationalProfile.objects.filter(user__email__iexact=email).update(marketing_consent=False)
    return render(request, 'board/candidate_unsubscribe.html', {'done': request.method == 'POST'})


@login_required
@require_POST
def preferences(request):
    profile = get_object_or_404(JobSeeker, user=request.user, login_active=True)
    profile.marketing_consent = request.POST.get('marketing_consent') == 'yes'
    profile.save(update_fields=['marketing_consent'])
    messages.success(request, 'Email preference saved.')
    return redirect('jobseeker_dashboard')


def send_batch(campaign, base_url):
    eligible = eligible_addresses(campaign.audience)
    queue = campaign.deliveries.filter(status='pending')
    rows = list(queue.order_by('pk')[:BATCH_SIZE])
    if not rows:
        return 0, 0, 0
    # Open the transport before claiming any recipient. A setup failure leaves the batch pending.
    sent = failed = skipped = 0
    with get_connection() as connection:
        for row in rows:
            if not queue.filter(pk=row.pk).update(status='sending', updated_at=timezone.now()):
                continue
            if row.email not in eligible or MarketingSuppression.objects.filter(email__iexact=row.email).exists():
                status = 'skipped'
                skipped += 1
            else:
                token = signing.dumps(row.email, salt=SALT)
                link = base_url + reverse('candidate_marketing_unsubscribe', args=[token])
                email = EmailMessage(
                    campaign.subject,
                    f'{campaign.body}\n\nPhysiotherapy Jobs Canada\n{base_url}\nUnsubscribe: {link}',
                    settings.DEFAULT_FROM_EMAIL, [row.email], connection=connection,
                    headers={'List-Unsubscribe': f'<{link}>'},
                )
                try:
                    status = 'sent' if email.send() == 1 else 'failed'
                except Exception:
                    status = 'failed'
                sent += status == 'sent'
                failed += status == 'failed'
            CandidateCampaignDelivery.objects.filter(pk=row.pk).update(status=status, updated_at=timezone.now())
    return sent, failed, skipped


@admin.register(CandidateCampaign)
class CandidateCampaignAdmin(admin.ModelAdmin):
    change_list_template = 'admin/marketing/campaign_list.html'
    list_display = ('name', 'audience', 'subject', 'created_at', 'queued_at', 'preview_link')
    list_filter = ('audience',)
    search_fields = ('name', 'subject')
    fields = ('name', 'audience', 'subject', 'body')
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return self.fields if obj and obj.queued_at else ()

    @admin.display(description='Delivery')
    def preview_link(self, obj):
        from django.utils.html import format_html
        return format_html('<a href="{}">Preview & delivery</a>',
                           reverse('admin:candidate_campaign_preview', args=[obj.pk]))

    def get_urls(self):
        return [path('<int:pk>/preview/', self.admin_site.admin_view(self.preview),
                     name='candidate_campaign_preview')] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        counts = [(label, len(eligible_addresses(key))) for key, label in AUDIENCES.items()]
        return super().changelist_view(request, {'audiences': counts, **(extra_context or {})})

    def save_model(self, request, obj, form, change):
        if change and CandidateCampaign.objects.select_for_update().get(pk=obj.pk).queued_at:
            raise PermissionDenied
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        if '_save' in request.POST:
            return redirect('admin:candidate_campaign_preview', obj.pk)
        return super().response_add(request, obj, post_url_continue)

    def preview(self, request, pk):
        campaign = get_object_or_404(self.get_queryset(request), pk=pk)
        if not self.has_view_or_change_permission(request, campaign):
            raise PermissionDenied
        can_send = self.has_change_permission(request, campaign)
        if request.method == 'POST':
            if not can_send:
                raise PermissionDenied
            action = request.POST.get('action')
            if action == 'queue':
                with transaction.atomic():
                    campaign = CandidateCampaign.objects.select_for_update().get(pk=pk)
                    if not campaign.queued_at:
                        emails = eligible_addresses(campaign.audience)
                        if emails:
                            CandidateCampaignDelivery.objects.bulk_create(
                                [CandidateCampaignDelivery(campaign=campaign, email=email) for email in sorted(emails)],
                                ignore_conflicts=True)
                            campaign.queued_at = timezone.now()
                            campaign.save(update_fields=['queued_at'])
                            self.message_user(request, f'{len(emails)} recipients queued. No email sent.')
                        else:
                            self.message_user(request, 'No eligible recipients.', messages.WARNING)
            elif action == 'send' and campaign.queued_at:
                location = urlsplit(request.build_absolute_uri('/'))
                base = f'{location.scheme}://{location.netloc}'
                try:
                    sent, failed, skipped = send_batch(campaign, base)
                except Exception:
                    self.message_user(request, 'The email transport did not complete this batch. Check delivery counts before continuing.', messages.ERROR)
                else:
                    self.message_user(request, f'{sent} accepted by the email service, {failed} failed, {skipped} skipped.')
            return redirect('admin:candidate_campaign_preview', pk)
        if request.method != 'GET':
            from django.http import HttpResponseNotAllowed
            return HttpResponseNotAllowed(['GET', 'POST'])
        counts = [(label, campaign.deliveries.filter(status=key).count())
                  for key, label in CandidateCampaignDelivery._meta.get_field('status').choices] if campaign.queued_at else []
        return render(request, 'admin/marketing/campaign_preview.html', {
            **self.admin_site.each_context(request), 'title': campaign.name, 'campaign': campaign,
            'counts': counts, 'can_send': can_send,
            'eligible_count': len(eligible_addresses(campaign.audience)) if not campaign.queued_at else None,
            'pending': campaign.deliveries.filter(status='pending').exists(),
        })
