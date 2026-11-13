"""Public watermarked design examples. No candidate data or paid export access."""
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET
from .schema import normalize, EXAMPLE, CANADIAN_EXAMPLE, REGISTRATION
from .pdf import render_pdf
from .specialties import EXAMPLES


IEPT_PREVIEW = {
    **EXAMPLE,
    'profile_url': 'https://example.com/morgan-ellis',
    'destination': 'Ontario', 'show_assessment_details': True, 'pathway': 'Comparability',
    'assessment': 'Decision received — describe exact outcome',
    'assessment_detail': 'Credential review completed in this fictional example.',
    'pet': 'Comparable', 'pet_detail': 'Outcome confirmed in the example assessment file.',
    'exam': 'Passed', 'exam_date': '2026-08-15',
    'canadian_registration': REGISTRATION[2], 'regulator': 'Sample provincial regulator',
    'registration_class': 'Sample independent practice class', 'registration_number': 'EXAMPLE-001',
    'registration_conditions': 'No conditions listed in this fictional example.',
    'canadian_experience': [{
        'role': 'Rehabilitation assistant', 'employer': 'Sample Canadian rehabilitation centre',
        'location': 'Ottawa, ON', 'dates': '2025–2026', 'setting': 'Outpatient care',
        'bullets': 'Supported exercise set-up, patient education and visit documentation under the supervising clinician.',
    }],
    'placements': [{
        'institution': 'Sample teaching hospital', 'country': 'United Kingdom', 'location': 'Leeds',
        'dates': '2019–2020', 'setting': 'Acute and community rehabilitation', 'hours': '320',
        'contribution': 'Completed supervised mobility assessments, discharge preparation and home exercise education.',
    }],
    'home_registration': 'United Kingdom · Sample physiotherapy registration · EXAMPLE-UK-01',
    'development': [
        {'course': 'Motivational interviewing', 'provider': 'Sample education provider', 'completed': '2024'},
        {'course': 'Clinical exercise and outcome measures', 'provider': 'Sample rehabilitation institute', 'completed': '2025'},
    ],
    'languages': [{'language': 'English', 'proficiency': 'Professional working proficiency', 'evidence': 'Clinical and academic use'}],
    'show_availability': True, 'work_authorization': 'Example: authorized to work in Canada',
    'relocation': 'Available in Ottawa; open to relocation within Ontario.',
}


@require_GET
def preview(request, layout):
    if layout not in ('classic', 'clinical', 'editorial', 'sidebar'):
        raise Http404('Resume design not found')
    canadian = request.GET.get("audience") == "canadian"
    data = normalize(CANADIAN_EXAMPLE if canadian else IEPT_PREVIEW)
    if canadian and (sample := EXAMPLES.get(request.GET.get('focus'))):
        for key in ('target_role', 'specialties', 'summary'):
            data[key] = sample[key]
        data['canadian_experience'][0].update(setting=sample['setting'], bullets=sample['bullets'])
    if canadian and not data.get('target_role'):
        data['target_role'] = 'Physiotherapist'
    data['layout'] = layout
    response = HttpResponse(render_pdf(data, preview=True, example=True, canadian=canadian), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ptjc-{layout}-resume-preview.pdf"'
    response['Cache-Control'] = 'public, max-age=3600'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
