"""Generate offline downloads and limited public demos from the same editor."""
import json
from pathlib import Path
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_GET
from .journal_editions import EDITIONS
from .journal_content import worksheets
from .stationery import STATIONERY
from .planning_editors import PLANNERS
from .online_workbooks import WORKBOOKS, worksheets as workbook_sheets

ROOT = Path(__file__).resolve().parent / 'bundled_products'
CALENDAR = 'physio-wall-calendar-2027'
JOURNALS = {('paediatric-physio-journal' if track == 'paediatric' else f'{track}-physio-journal'): entry for track, entry in EDITIONS.items()}
GUEST_RESUME = "canadian-resume"

TEMPLATES = {**{key: (spec["title"], ()) for key, spec in PLANNERS.items()},**{key: (spec[0], ()) for key, spec in WORKBOOKS.items()}, **{key: (spec["title"], ()) for key, spec in STATIONERY.items()}, CALENDAR: ('2027 Physiotherapy Photo Wall Calendar', ()), **{
    key: (name + ' Journal', topics + ('Practice reflection and learning',)) for key, (name, topics) in JOURNALS.items()
}}


def document(key, *, demo=False, overrides=None):
    name, sections = ("Canadian physiotherapy résumé", ()) if key == GUEST_RESUME else TEMPLATES[key]
    config = {'id':key, 'title':name, 'sections':sections, 'type': 'calendar' if key == CALENDAR else 'resume' if key == GUEST_RESUME else 'journal', 'demo':demo}
    if key in PLANNERS:
        config.update(type='planner', planner=PLANNERS[key])
    if key in STATIONERY:
        config.update(type='stationery', stationery=STATIONERY[key])
    if key in WORKBOOKS:
        config.update(worksheets=workbook_sheets(key), coverSeries='WORKBOOK', subtitle='Complete the pages you need and keep a copy for reference.', tracker=key=='exercise-tracker')
    elif config['type'] == 'journal':
        track = key.removesuffix('-physio-journal')
        config['worksheets'] = worksheets(track)
    if overrides:
        config.update(overrides)
    encoded = json.dumps(config).replace('<', '\\u003c')
    if key in PLANNERS:
        return (ROOT/'planning_editor.html').read_text(encoding='utf-8').replace('__CONFIG__', encoded)
    if key == 'appointment-card-designs':
        return (ROOT/'appointment_editor.html').read_text(encoding='utf-8').replace('__CONFIG__', encoded)
    if key in STATIONERY:
        return (ROOT/'stationery_editor.html').read_text(encoding='utf-8').replace('__CONFIG__', encoded)
    if key == CALENDAR:
        template = (ROOT/'physio-wall-calendar-2027.html').read_text(encoding='utf-8')
        start = '<script id="config" type="application/json">'
        head, rest = template.split(start, 1)
        _, tail = rest.split('</script>', 1)
        return head + start + encoded + '</script>' + tail
    return (ROOT/'editable_layout.html').read_text(encoding='utf-8').replace('__CONFIG__', encoded)


def configured_document(key, *, demo=False, extra=None):
    from .models import JournalTemplate
    settings = JournalTemplate.objects.filter(key=key).first() if key in JOURNALS else None
    overrides = {}
    if settings:
        overrides = {"title": settings.title, "subtitle": settings.subtitle, "defaultDesign": settings.default_design, "defaultColour": settings.default_colour}
        if settings.content:
            overrides["worksheets"] = settings.content
    return document(key, demo=demo, overrides={**overrides, **(extra or {})})


@require_GET
def demo(request, key):
    if key == GUEST_RESUME:
        return redirect('ptjc_canadian_resumes:canadian_start')
    if key not in TEMPLATES:
        raise Http404
    return editor_response(request, key, embedded=request.GET.get("editor_frame") == "1", shop_page=True)


CALENDAR_LAYOUTS = {'year': 'editorial', 'planner': 'minimal', 'photo': 'photo'}


def editor_response(request, key, *, embedded=False, shop_page=False):
    from django.urls import reverse
    from django.template.loader import render_to_string
    from .pricing import pricing_audience
    from .store_eligibility import account_requirement
    checkout_panel = ''
    design = CALENDAR_LAYOUTS.get(request.GET.get('layout', ''))
    extra = {'embedded': True} if embedded else {}
    if key == CALENDAR:
        if design:
            extra['defaultDesign'] = design
        if request.GET.get('preview') == 'letter':
            extra['letterPreview'] = True
    audience = 'international' if request.GET.get('audience') == 'international' else 'canadian'
    shop_url = reverse('mobility_shop')
    if request.GET.get('audience') == 'international':
        from django.urls import NoReverseMatch
        try:
            shop_url = reverse('mobility_international_shop')
        except NoReverseMatch:
            pass
    public_query = request.GET.copy()
    public_query.pop('editor_frame', None)
    public_path = request.path + ('?' + public_query.urlencode() if public_query else '')
    slug = request.GET.get('product')
    appointment = key == 'appointment-card-designs'
    if appointment:
        from django.utils.http import urlencode
        audience = 'international' if request.GET.get('audience') == 'international' else 'canadian'
        suffix = '?' + urlencode({'next': public_path})
        extra.update(signedIn=request.user.is_authenticated, loginUrl=reverse('mobility_international_login' if audience == 'international' else 'login') + suffix,
                     signupUrl=reverse('mobility_international_signup' if audience == 'international' else 'jobseeker_signup') + suffix)
    if not slug:
        from .models import DigitalProduct
        audience = 'international' if request.GET.get('audience') == 'international' else 'canadian'
        slug = DigitalProduct.objects.filter(slug__in=(key, 'ptjc-'+key), is_published=True,
            audience__in=(audience, 'both'), preview_editor__in=('',key)).values_list('slug', flat=True).first()
    if slug:
        from .models import DigitalProduct
        from .shop_gallery import editor_key
        audience = 'international' if request.GET.get('audience') == 'international' else 'canadian'
        product = DigitalProduct.objects.filter(
            slug=slug, is_published=True, audience__in=(audience, 'both'),
        ).first()
        if not product or editor_key(product) != key:
            raise Http404
        if product.slug.startswith('pt-v6-'):
            extra['title'] = product.title
        if request.user.is_authenticated:
            from .store_access import has_access
            extra['canExport'] = has_access(request.user, product)
        if key != 'appointment-card-designs':
            from django.middleware.csrf import get_token
            from .starter import remaining
            starter = remaining(request.user, product)
            extra.update(activityUrl=reverse('mobility_design_activity', args=[product.pk]), csrf=get_token(request), starter=starter)
            if extra.get('canExport') or starter:
                extra['exportUrl'] = extra['activityUrl']
        if key == 'appointment-card-designs':
            from django.middleware.csrf import get_token
            from django.shortcuts import get_object_or_404
            from django.utils.http import urlencode
            from .models import ProductDraft
            from .store_eligibility import account_type
            extra.update(activity=reverse('mobility_design_activity', args=[product.pk]), csrf=get_token(request))
            if account_type(request.user) and not account_requirement(request.user, product):
                from django.utils.crypto import salted_hmac
                extra['ownerScope'] = salted_hmac('appointment-editor-storage', str(request.user.pk)).hexdigest()
                from .starter import remaining
                extra['remaining'] = remaining(request.user, product)
                extra['saveUrl'] = reverse('mobility_save_design', args=[product.pk])
                if request.GET.get('draft'):
                    draft_id = request.GET['draft']
                    if not (draft_id.isascii() and draft_id.isdecimal() and len(draft_id) <= 18):
                        raise Http404
                    draft = get_object_or_404(ProductDraft, pk=draft_id, product=product, owner=request.user)
                    extra.update(draft=draft.pk, savedData=draft.data)
            elif not request.user.is_authenticated:
                extra['loginUrl'] = reverse('mobility_international_login' if audience == 'international' else 'login') + '?' + urlencode({'next': public_path})
            extra['libraryUrl'] = reverse('mobility_resource_library')
        extra['storageScope'] = reverse('mobility_product_detail', args=[product.slug]) + '?audience=' + audience
        price = product.price_for(pricing_audience(request.user, product, audience))
        if appointment:
            extra.update(price=str(price) if price > 0 else None, starterQuantity=product.starter_quantity)
        if price > 0 and not extra.get('canExport') and (not request.user.is_authenticated or not account_requirement(request.user, product)):
            extra.update(productUrl='#editor-checkout', purchaseLabel='Print and export')
            login_route = 'mobility_international_login' if audience == 'international' else 'login'
            checkout_panel = render_to_string('career_mobility/editor_checkout.html', {
                'product': product, 'price': price, 'login_route': login_route, 'return_path': public_path,
            }, request=request)
        from .product_activity import record
        if not shop_page or embedded:
            record(product, 'opened', request=request)
    from .templatetags.related_digital_products import product_links
    if shop_page and not embedded:
        from django.shortcuts import render
        frame_query = public_query.copy()
        frame_query['editor_frame'] = '1'
        from board.seo_config import SITE
        from .shop_gallery import editor_link
        title = product.title if slug else TEMPLATES[key][0]
        canonical = SITE.rstrip('/') + (editor_link(product, audience) if slug else reverse('mobility_editable_preview', args=[key]))
        description = (product.short_description if slug else '') or f'Customize {title} at Physiotherapy Jobs Canada.'
        response = render(request, 'career_mobility/shop_editor.html', {
            'editor_base': 'career_mobility/standalone.html' if audience == 'international' else 'base.html',
            'editor_title': title, 'shop_url': shop_url, 'related': product_links(audience, editor=key),
            'editor_intro': (product.short_description if slug else '') or ('Design both sides and preview them on a US Letter sheet.' if appointment else ''),
            'editor_canonical': canonical, 'editor_description': description,
            'editor_frame': request.path + '?' + frame_query.urlencode(),
        })
        response['Cache-Control'] = 'private, no-store'
        if request.GET.get('draft') or not slug:
            response['X-Robots-Tag'] = 'noindex'
        return response

    extra['shopUrl'] = shop_url
    html = configured_document(key, demo=True, extra=extra).replace(
        "https://www.physiotherapyjobscanada.ca/career-resources/shop/", shop_url)
    if appointment:
        panel = render_to_string('career_mobility/appointment_shop_panel.html', {
            'shop_url': shop_url, 'signup_url': extra['signupUrl'], 'login_url': extra['loginUrl'],
            'price': extra.get('price'), 'starter_quantity': extra.get('starterQuantity', 0),
            'remaining': extra.get('remaining', 0), 'can_save': bool(extra.get('saveUrl')),
            'employer_signup_url': reverse('employer_signup') + suffix if audience == 'canadian' else '',
        }, request=request)
        html = html.replace('<!-- APPOINTMENT_SHOP_PANEL -->', panel)
    elif not shop_page:
        related_navigation = render_to_string('career_mobility/builder_product_nav.html', {'shop_url': shop_url, 'related': product_links(audience, editor=key)})
        html = html.replace('</body>', related_navigation + '</body>', 1)

    from django.utils.html import format_html
    from board.seo_config import SITE
    from .shop_gallery import editor_link
    if slug and not request.GET.get('draft') and not embedded:
        canonical = SITE.rstrip('/') + editor_link(product, audience)
        head = format_html('<link rel="canonical" href="{}"><meta name="description" content="{}">',
                           canonical, product.short_description or ('Customize ' + product.title + ' at Physiotherapy Jobs Canada.'))
        html = html.replace('</head>', str(head) + '</head>', 1)
    if extra.get('activityUrl'):
        controls = (ROOT / 'metered_editor_controls.html').read_text(encoding='utf-8')
        html = html.replace('</body>', controls + '</body>', 1)
    if checkout_panel:
        html = html.replace('</body>', checkout_panel + '</body>', 1)
    if shop_page and embedded:
        frame_style = render_to_string('career_mobility/shop_editor_embedded_style.html')
        html = html.replace('</head>', frame_style + '</head>', 1)
        frame_navigation = """<script>
        document.addEventListener('click', event => {
            const link = event.target.closest('a[href]');
            if (!link || link.target || link.hasAttribute('download')) return;
            const href = link.getAttribute('href');
            if (href.startsWith('/')) link.target = '_top';
        });
        </script>"""
        html = html.replace('</body>', frame_navigation + '</body>', 1)
    response = HttpResponse(html, content_type='text/html; charset=utf-8')
    ancestors = "'self'" if embedded else "'none'"
    response['Content-Security-Policy'] = f"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; connect-src 'self'; form-action 'self' https://checkout.stripe.com; base-uri 'none'; frame-ancestors {ancestors}"
    response['Cache-Control'] = 'private, no-store'
    if embedded or request.GET.get('draft') or not slug:
        response['X-Robots-Tag'] = 'noindex'
    if embedded:
        response['X-Frame-Options'] = 'SAMEORIGIN'
    return response


@login_required
@require_GET
def jobseeker_calendar(request, *, embedded=False):
    profile = getattr(request.user, 'jobseeker', None)
    if not (profile and profile.is_approved and profile.login_active):
        raise PermissionDenied
    if embedded:
        return editor_response(request, CALENDAR, embedded=True)
    return render(request, 'career_mobility/jobseeker_calendar.html')


@require_GET
def choose_journal(request):
    from django.urls import reverse
    international = request.GET.get('audience') == 'international'
    key = request.GET.get('edition')
    if key not in JOURNALS:
        if international:
            from django.urls import NoReverseMatch
            try:
                return redirect(reverse('mobility_international_shop'))
            except NoReverseMatch:
                pass
        return redirect('mobility_shop')
    url = reverse('mobility_editable_preview', kwargs={'key':key})
    return redirect(url + ('?audience=international' if international else ''))
