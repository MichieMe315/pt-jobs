"""
Province SEO Pages Views
-------------------------
Each view renders province-specific content with:
- Unique H1, title, and meta description
- Province-specific career information
- Links to jobs filtered by province/keywords
"""
from django.shortcuts import render


def get_province_context(province_name, major_cities, work_settings, description):
    """
    Build common context for province pages.
    """
    return {
        "province": province_name,
        "major_cities": major_cities,
        "work_settings": work_settings,
        "description": description,
        "page_type": "province_landing",
    }


def ontario_view(request):
    major_cities = [
        "Toronto", "Ottawa", "Mississauga", "Brampton", "Hamilton",
        "Kitchener", "London", "Markham", "Vaughan", "Windsor"
    ]
    work_settings = [
        "Private orthopedic clinics",
        "Hospital rehabilitation departments",
        "Home care and community health",
        "Sports medicine facilities",
        "Long-term care homes",
        "University health centres",
    ]
    context = get_province_context(
        province_name="Ontario",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in Ontario.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in Ontario | Find PT Careers",
        "meta_description": "Find physiotherapy jobs in Ontario. Opportunities in Toronto, Ottawa, Hamilton, and across the province.",
        "h1": "Physiotherapy Jobs in Ontario",
        "intro": "Find physiotherapy positions in Ontario, from major cities to growing communities. Practice settings include hospitals, private clinics, and home care.",
        "certification_note": "Register with the College of Physiotherapists of Ontario.",
        "job_board_slug": "ontario",
        "search_keywords": ["Toronto", "Ottawa", "Hamilton", "London", "Kitchener"],
    })
    return render(request, "province_pages/province_base.html", context)


def british_columbia_view(request):
    major_cities = [
        "Vancouver", "Surrey", "Burnaby", "Richmond", "Victoria",
        "Kelowna", "Abbotsford", "Coquitlam", "Langley", "Nanaimo"
    ]
    work_settings = [
        "Coastal private practices",
        "Regional hospitals",
        "Rural health settings",
        "Sport rehabilitation centres",
        "Workplace wellness programs",
        "Active aging facilities",
    ]
    context = get_province_context(
        province_name="British Columbia",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in British Columbia.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in British Columbia | Vancouver & Beyond",
        "meta_description": "Explore physiotherapy careers in BC. Jobs in Vancouver, Victoria, Kelowna, and throughout the province.",
        "h1": "Physiotherapy Jobs in British Columbia",
        "intro": "Find physiotherapy roles in BC, from coastal cities to rural communities. Practice settings include private clinics, hospitals, and rehabilitation centres.",
        "certification_note": "Register with the College of Physical Therapists of British Columbia.",
        "job_board_slug": "british-columbia",
        "search_keywords": ["Vancouver", "Victoria", "Kelowna", "Surrey", "Burnaby"],
    })
    return render(request, "province_pages/province_base.html", context)


def alberta_view(request):
    major_cities = [
        "Calgary", "Edmonton", "Red Deer", "Lethbridge", "St. Albert",
        "Medicine Hat", "Grande Prairie", "Airdrie", "Spruce Grove", "Fort McMurray"
    ]
    work_settings = [
        "Oil and gas industrial rehab",
        "Teaching hospitals",
        "Rural health centres",
        "Sports performance clinics",
        "Workers compensation facilities",
        "Remote postings",
    ]
    context = get_province_context(
        province_name="Alberta",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in Alberta.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in Alberta | Calgary & Edmonton",
        "meta_description": "Find physiotherapy jobs in Alberta. Opportunities in Calgary, Edmonton, and across the province.",
        "h1": "Physiotherapy Jobs in Alberta",
        "intro": "Find physiotherapy positions in Alberta, spanning urban centres to rural communities. Settings include hospitals, clinics, and industrial rehab.",
        "certification_note": "Register with the College of Physiotherapists of Alberta.",
        "job_board_slug": "alberta",
        "search_keywords": ["Calgary", "Edmonton", "Red Deer", "Lethbridge", "Medicine Hat"],
    })
    return render(request, "province_pages/province_base.html", context)


def saskatchewan_view(request):
    major_cities = [
        "Saskatoon", "Regina", "Prince Albert", "Moose Jaw", "Lloydminster",
        "North Battleford", "Yorkton", "Swift Current", "Estevan", "Weyburn"
    ]
    work_settings = [
        "Hospitals",
        "Rural health centres",
        "Agricultural injury rehab",
        "University clinics",
        "Remote postings",
        "Multi-service community health",
    ]
    context = get_province_context(
        province_name="Saskatchewan",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in Saskatchewan.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in Saskatchewan | Saskatoon & Regina",
        "meta_description": "Discover physiotherapy careers in Saskatchewan. Jobs in Saskatoon, Regina, and rural communities.",
        "h1": "Physiotherapy Jobs in Saskatchewan",
        "intro": "Find physiotherapy roles in Saskatchewan, with opportunities in urban centres and rural communities. Settings include hospitals and community clinics.",
        "certification_note": "Register with the Saskatchewan College of Physical Therapists.",
        "job_board_slug": "saskatchewan",
        "search_keywords": ["Saskatoon", "Regina", "Prince Albert", "Moose Jaw", "Lloydminster"],
    })
    return render(request, "province_pages/province_base.html", context)


def manitoba_view(request):
    major_cities = [
        "Winnipeg", "Brandon", "Steinbach", "Thompson", "Portage la Prairie",
        "Winkler", "Selkirk", "Morden", "Dauphin", "The Pas"
    ]
    work_settings = [
        "Hospitals",
        "Remote nursing stations",
        "Chronic disease management",
        "Indigenous community health",
        "Regional health centre",
        "Private orthopaedic clinics",
    ]
    context = get_province_context(
        province_name="Manitoba",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in Manitoba.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in Manitoba | Winnipeg & Rural Area",
        "meta_description": "Find physiotherapy jobs in Manitoba. Opportunities in Winnipeg, Brandon, and rural communities.",
        "h1": "Physiotherapy Jobs in Manitoba",
        "intro": "Find physiotherapy positions in Manitoba, with roles in urban hospitals and remote community clinics. Work with diverse populations across the province.",
        "certification_note": "Register with the College of Physiotherapists of Manitoba.",
        "job_board_slug": "manitoba",
        "search_keywords": ["Winnipeg", "Brandon", "Steinbach", "Thompson", "Portage la Prairie"],
    })
    return render(request, "province_pages/province_base.html", context)


def quebec_view(request):
    major_cities = [
        "Montreal", "Quebec City", "Laval", "Gatineau", "Longueuil",
        "Sherbrooke", "Saguenay", "Trois-Rivieres", "Terrebonne", "Saint-Jean-sur-Richelieu"
    ]
    work_settings = [
        "Hospitals",
        "Private francophone clinics",
        "Rehabilitation centres",
        "University-affiliated facilities",
        "Bilingual rural health",
        "Long-term care facilities",
    ]
    context = get_province_context(
        province_name="Quebec",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in Quebec.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in Quebec | Montreal & Quebec City",
        "meta_description": "Find physiotherapy jobs in Quebec. Opportunities in Montreal, Quebec City, and across the province.",
        "h1": "Physiotherapy Jobs in Quebec",
        "intro": "Find physiotherapy roles in Quebec, particularly for those with French language skills. Practice settings include hospitals, clinics, and rehabilitation centres.",
        "certification_note": "Register with the Ordre professionnel de la physiotherapie du Quebec.",
        "job_board_slug": "quebec",
        "search_keywords": ["Montreal", "Quebec City", "Laval", "Gatineau", "Sherbrooke"],
    })
    return render(request, "province_pages/province_base.html", context)


def nova_scotia_view(request):
    major_cities = [
        "Halifax", "Dartmouth", "Sydney", "Truro", "New Glasgow",
        "Glace Bay", "Kentville", "Amherst", "Bridgewater", "Yarmouth"
    ]
    work_settings = [
        "Hospitals",
        "Regional hospitals",
        "Private practices",
        "Seniors' residential care",
        "University clinics",
        "Home care",
    ]
    context = get_province_context(
        province_name="Nova Scotia",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in Nova Scotia.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in Nova Scotia | Halifax & Maritime",
        "meta_description": "Explore physiotherapy careers in Nova Scotia. Jobs in Halifax, Sydney, Truro, and across the Maritimes.",
        "h1": "Physiotherapy Jobs in Nova Scotia",
        "intro": "Find physiotherapy positions in Nova Scotia, from the Halifax area to rural communities. Practice settings include hospitals, clinics, and home care.",
        "certification_note": "Register with the Nova Scotia College of Physiotherapists.",
        "job_board_slug": "nova-scotia",
        "search_keywords": ["Halifax", "Dartmouth", "Sydney", "Truro", "New Glasgow"],
    })
    return render(request, "province_pages/province_base.html", context)


def new_brunswick_view(request):
    major_cities = [
        "Moncton", "Saint John", "Fredericton", "Dieppe", "Miramichi",
        "Edmundston", "Bathurst", "Campbellton", "Oromocto", "Grand Falls"
    ]
    work_settings = [
        "Hospitals",
        "Private francophone clinics",
        "Rural community health centres",
        "Nursing home rehabilitation",
        "Multi-service health clinics",
    ]
    context = get_province_context(
        province_name="New Brunswick",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in New Brunswick.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in New Brunswick | Bilingual",
        "meta_description": "Find physiotherapy jobs in New Brunswick. Opportunities in Moncton, Saint John, Fredericton, and bilingual communities.",
        "h1": "Physiotherapy Jobs in New Brunswick",
        "intro": "Find physiotherapy roles in New Brunswick, a bilingual province. Practice settings include hospitals, clinics, and nursing homes.",
        "certification_note": "Register with the College of Physiotherapists of New Brunswick.",
        "job_board_slug": "new-brunswick",
        "search_keywords": ["Moncton", "Saint John", "Fredericton", "Dieppe", "Miramichi"],
    })
    return render(request, "province_pages/province_base.html", context)


def newfoundland_view(request):
    major_cities = [
        "St. John's", "Mount Pearl", "Corner Brook", "Conception Bay South",
        "Grand Falls-Windsor", "Paradise", "Gander", "Happy Valley-Goose Bay",
        "Labrador City", "Stephenville"
    ]
    work_settings = [
        "Hospitals",
        "Rural positions",
        "Community clinics",
        "Remote nursing stations",
        "Long-term care homes",
        "Fly-in/fly-out arrangements",
    ]
    context = get_province_context(
        province_name="Newfoundland and Labrador",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in Newfoundland and Labrador.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in Newfoundland and Labrador | St. John's & Rural",
        "meta_description": "Discover physiotherapy careers in Newfoundland and Labrador. Jobs in St. John's, Corner Brook, Labrador, and remote communities.",
        "h1": "Physiotherapy Jobs in Newfoundland and Labrador",
        "intro": "Find physiotherapy positions in Newfoundland and Labrador, from coastal towns to remote communities. Settings include hospitals and community clinics.",
        "certification_note": "Register with the Newfoundland and Labrador College of Physiotherapists.",
        "job_board_slug": "newfoundland",
        "search_keywords": ["St. John's", "Corner Brook", "Grand Falls", "Labrador", "Gander"],
    })
    return render(request, "province_pages/province_base.html", context)


def prince_edward_island_view(request):
    major_cities = [
        "Charlottetown", "Summerside", "Stratford", "Cornwall",
        "Montague", "Kensington", "Alberton", "Souris", "Tignish"
    ]
    work_settings = [
        "Hospitals",
        "Community care centres",
        "Home care services",
        "Long-term care facilities",
        "Rural coverage",
    ]
    context = get_province_context(
        province_name="Prince Edward Island",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Physiotherapy jobs in Prince Edward Island.",
    )
    context.update({
        "page_title": "Physiotherapy Jobs in Prince Edward Island | Charlottetown",
        "meta_description": "Find physiotherapy jobs in Prince Edward Island. Opportunities in Charlottetown, Summerside, and across the island.",
        "h1": "Physiotherapy Jobs in Prince Edward Island",
        "intro": "Find physiotherapy roles on Prince Edward Island, a small province where practitioners often know patients personally. Settings include hospitals, clinics, and home care.",
        "certification_note": "Register with the College of Physiotherapists of Prince Edward Island.",
        "job_board_slug": "prince-edward-island",
        "search_keywords": ["Charlottetown", "Summerside", "Stratford", "Cornwall", "Montague"],
    })
    return render(request, "province_pages/province_base.html", context)