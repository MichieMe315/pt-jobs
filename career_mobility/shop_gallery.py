"""Public sample pages, kept separate from paid downloads."""
from .editable_products import CALENDAR, TEMPLATES

SAMPLES = {
    'exercise-tracker': ((1, 'Weekly exercise log'),),
    'appointment-notes': ((1, 'Questions to bring'), (2, 'Notes and next steps')),
    'practice-planner-2027': ((1, 'Year index'), (2, 'Monthly calendar'), (14, 'Weekly priorities'), (16, 'Learning and renewal')),
    'paediatric-physio-journal': ((1, 'Journal cover'), (2, 'Goals and participation'), (3, 'Plan a visit'), (6, 'Practice reflection')),
}


def editor_key(product):
    if product.preview_editor:
        return product.preview_editor if product.preview_editor in TEMPLATES else ''
    slug = product.slug
    key = slug.removeprefix('ptjc-')
    if key in TEMPLATES:
        return key
    if slug.startswith('pt-v6-'):
        edition = slug.removeprefix('pt-v6-')
        if edition[:2].isdigit():
            return 'resume-cover-letter-workspace'
        return {
            'pt_application_studio': 'application-workspace',
            'annotated_pt_resume_examples': 'resume-review-workspace',
            'pt_resume_writing_and_personalization': 'resume-review-workspace',
            'pt_personal_brand_graphics': 'practice-brand-assets',
            'pt_resume_complete_collection': 'resume-cover-letter-workspace',
        }.get(edition, '')
    return ''


def editor_link(product, audience):
    from django.urls import reverse
    from urllib.parse import urlencode

    key = editor_key(product)
    if not key:
        return ''
    return reverse('mobility_editable_preview', args=[key]) + '?' + urlencode({
        'audience': audience, 'product': product.slug,
    })


def resource_link(product, audience):
    """Resolve the actual tool without sending people to a catalogue detail page."""
    from django.urls import NoReverseMatch, reverse

    if product.is_card_design_pack or product.includes_card_builder:
        return reverse('mobility_try_cards') + '?audience=' + audience
    if product.kind == 'bundle' and product.starter_quantity:
        return reverse('mobility_product_detail', args=[product.slug])
    route = None
    if product.kind == 'workbook':
        route = 'mobility_personalized_checklist'
    elif product.includes_resume_builder:
        route = ('ptjc_canadian_resumes:canadian_start' if audience == 'canadian'
                 else 'ptjc_resumes:start')
    if route:
        try:
            return reverse(route)
        except NoReverseMatch:
            return ''
    return editor_link(product, audience) or (reverse('mobility_product_detail', args=[product.slug]) if product.starter_quantity and product.download else '')


def gallery(product):
    from django.templatetags.static import static
    from django.urls import reverse
    custom = [
        {'url': reverse('mobility_product_gallery_image', args=[product.pk, page.pk]), 'caption': page.caption}
        for page in product.gallery_images.all()
    ]
    key = editor_key(product) or product.slug.removeprefix('ptjc-')
    if key == CALENDAR:
        demo = reverse('mobility_editable_preview', args=[CALENDAR])
        return [
            {'url': static(f'career_mobility/product-previews/pages/{CALENDAR}-{layout}.jpg'),
             'caption': label, 'editor_url': f'{demo}?layout={layout}'}
            for layout, label in (('year','Year overview'), ('planner','Monthly planner with notes'), ('photo','Monthly calendar with optional photos'))
        ] + custom, False
    if custom:
        return custom, True
    key = product.slug.removeprefix('ptjc-')
    from .editable_products import JOURNALS
    if key in JOURNALS:
        return [
            {'url': static(f'career_mobility/product-previews/journals/{key}/{name}.jpg'), 'caption': caption}
            for name,caption in (('cover','Editable cover'),('worksheet','Specialty worksheet'),('review','Additional worksheet'))
        ], False
    return [{'url': static(f'career_mobility/product-previews/pages/{key}-{page}.jpg'), 'caption': caption} for page, caption in SAMPLES.get(key, ())], False
