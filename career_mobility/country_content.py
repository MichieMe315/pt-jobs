import json
from pathlib import Path
from functools import lru_cache

@lru_cache(maxsize=1)
def countries():
    return json.loads((Path(__file__).parent/'data/international_countries.json').read_text(encoding='utf-8'))

def get_country(value):
    aliases={'usa':'united-states','united-states-of-america':'united-states','uk':'united-kingdom','republic-of-ireland':'ireland'}
    from django.utils.text import slugify
    slug=slugify(str(value).strip())
    slug=aliases.get(slug,slug)
    found=next((p for p in countries() if p['slug']==slug),None)
    if found:
        actions=json.loads((Path(__file__).parent/'data/country_actions_2026_11_04.json').read_text(encoding='utf-8'))
        return dict(found,action_guide=actions.get(found['name']))
    from .countries import COUNTRIES
    from django.utils.text import slugify
    name=next((n for n in COUNTRIES if slugify(n)==slug),None)
    if not name:return None
    sample=countries()[0]
    return dict(sample,name=name,slug=slug,preapproved=False,language_education_exemption=False,school_internship_required=False,specific_note=('A Canadian physiotherapy qualification follows the destination regulator’s Canadian-educated route.' if name=='Canada' else name+' is not on CAPR’s published pre-approved education-country list. For a new file, this page uses the comparability requirements. WES document delivery depends on your exact school and qualification.'),generic=True,reviewed_on='2026-10-28',guidance_basis='Published assessor pathway rules; institution-specific requirements are determined by the receiving assessor.')
