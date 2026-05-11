"""
Province SEO Pages Views
------------------------
Each view renders province-specific content with:
- Unique H1, title, and meta description
- Province-specific career information
- Links to jobs filtered by province/keywords
"""
from django.shortcuts import render
from django.urls import reverse


def get_province_context(province_name, major_cities, work_settings, description):
    """
    Build common context for province pages.
    Assumes Job model exists in board app with fields:
    - title, location, employer, posting_date, is_active
    """
    context = {
        "province": province_name,
        "major_cities": major_cities,
        "work_settings": work_settings,
        "description": description,
        "page_type": "province_landing",
    }
    return context


def ontario_view(request):
    """Physiotherapy Jobs Ontario"""
    major_cities = [
        "Toronto", "Ottawa", "Mississauga", "Brampton", "Hamilton",
        "Kitchener", "London", "Markham", "Vaughan", "Windsor"
    ]
    work_settings = [
        "Private orthopedic clinics", "Hospital rehabilitation departments",
        "Home care and community health", "Sports medicine facilities",
        "Long-term care homes", "University health centres"
    ]
    
    context = get_province_context(
        province_name="Ontario",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Ontario offers the largest physiotherapy job market in Canada."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in Ontario | Find PT Careers Across the Province",
        "meta_description": "Find physiotherapy jobs in Ontario. Opportunities in Toronto, Ottawa, Hamilton, London, and across the province. Hospitals, clinics, and home care settings hiring now.",
        "h1": "Physiotherapy Jobs in Ontario",
        "intro": """Ontario represents Canada's largest physiotherapy job market, with opportunities spanning major urban centres like Toronto and Ottawa to growing communities across the province. The diversity of practice settings—from acute care hospitals in downtown Toronto to community clinics in Northern Ontario—makes this province attractive for physiotherapists at all career stages.

The Ontario healthcare system continues to expand access to physiotherapy services, particularly for seniors and post-surgical patients. This expansion has created steady demand for qualified physiotherapists in hospitals, private practice, home care, and long-term care facilities.""",
        "registration_note": "Physiotherapists in Ontario are regulated by the <a href=\"https://www.cpoh.org\" target=\"_blank\">College of Physiotherapists of Ontario</a>. Candidates should confirm current registration requirements directly with the regulator, especially if educated outside Canada or moving from another province. Requirements can change, so verify before applying.",
        "job_market": """Ontario’s physiotherapy job market is the largest in Canada, driven by a growing and aging population that requires rehabilitation services. Major urban centres such as Toronto and Ottawa host large hospital networks, private orthopaedic clinics, and academic health centres, offering a wide range of roles from acute care to specialised outpatient services. Rural and northern communities also rely on physiotherapists for community‑based care, creating diverse opportunities across the province. Demand is especially high in areas like seniors’ care, post‑operative rehabilitation, and chronic disease management, ensuring a steady flow of openings throughout the year.""",
        "practice_settings": """Common practice settings in Ontario include:

* Hospital acute care and rehabilitation units
* Private orthopaedic and sports medicine clinics
* Community health centres and public health programs
* Home‑care and community‑based visiting therapist services
* Long‑term care facilities and seniors’ housing
* Academic and research institutions affiliated with universities""",
        "tips_for_applying": """Tips for applying to physiotherapy jobs in Ontario:

1. **Check registration** – Ensure you are registered with the College of Physiotherapists of Ontario before applying. Internationally educated therapists should verify credential assessment.
2. **Tailor your CV** – Highlight experience in the specific practice setting (e.g., acute care, sports rehab) that the job advertises.
3. **Network locally** – Attend provincial PT association events and connect with hiring managers at hospitals.
4. **Showcase competencies** – Emphasise skills in patient assessment, treatment planning, and multidisciplinary teamwork.
5. **Prepare for interviews** – Be ready to discuss case studies, especially involving seniors or post‑surgical patients, which are common in Ontario.
6. **Stay updated** – Follow the College’s continuing education requirements to keep your licence current.
""",
        "job_board_slug": "ontario",
        "search_keywords": ["Toronto", "Ottawa", "Hamilton", "London", "Kitchener"],
    })
    
    return render(request, "province_pages/province_base.html", context)


def british_columbia_view(request):
    """Physiotherapy Jobs British Columbia"""
    major_cities = [
        "Vancouver", "Surrey", "Burnaby", "Richmond", "Victoria",
        "Kelowna", "Abbotsford", "Coquitlam", "Langley", "Nanaimo"
    ]
    work_settings = [
        "Coastal private practices", "Island Health authority hospitals",
        "Interior Health rural positions", "Sport rehabilitation centres",
        "Workplace wellness programs", "Active aging facilities"
    ]
    
    context = get_province_context(
        province_name="British Columbia",
        major_cities=major_cities,
        work_settings=work_settings,
        description="BC offers diverse physiotherapy opportunities from Vancouver to rural communities."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in British Columbia | Vancouver & Beyond",
        "meta_description": "Explore physiotherapy careers in British Columbia. Jobs in Vancouver, Victoria, Kelowna, and throughout BC. Urban hospitals, coastal clinics, and rural health opportunities.",
        "h1": "Physiotherapy Jobs in British Columbia",
        "intro": """British Columbia combines urban opportunities in Vancouver with unique rural and coastal positions that attract physiotherapists seeking variety in their practice. The province's health authorities—Vancouver Coastal, Fraser, Interior, Island, and Northern—offer structured career paths with competitive benefits.

BC's outdoor lifestyle and mild climate draw physiotherapists interested in sports medicine and active rehabilitation. From ski injury clinics in Whistler to senior care in Victoria, the province offers practice settings that align with diverse professional interests.""",
        "registration_note": "Physiotherapists in British Columbia are regulated by the <a href=\"https://www.cpsbc.org\" target=\"_blank\">College of Physical Therapists of British Columbia</a>. Confirm current registration requirements with the college, especially if educated outside Canada or moving from another province. Requirements may change, so verify before applying.",
        "job_market": "British Columbia’s physiotherapy job market benefits from a mix of urban hospital networks, private clinics, and a growing focus on community‑based care. Major centres such as Vancouver and Victoria host large acute‑care facilities, while smaller cities like Kelowna and Nanaimo provide opportunities in outpatient and sports‑medicine settings. The province’s emphasis on preventive health and aging populations drives demand for therapists across the public and private sectors.",
        "practice_settings": "Common practice settings in British Columbia include hospital acute care, private orthopaedic and sports medicine clinics, community health centres, home‑care services, and long‑term care facilities.",
        "tips_for_applying": "Tips for applying in BC: 1) Verify registration with the college; 2) Highlight experience in both urban and rural settings; 3) Emphasise any work with Indigenous communities; 4) Network through the BCPTA; 5) Showcase competencies in musculoskeletal and geriatric care.",
        "job_board_slug": "british-columbia",
        "search_keywords": ["Vancouver", "Victoria", "Kelowna", "Surrey", "Burnaby"],
    })
    
    return render(request, "province_pages/province_base.html", context)


def alberta_view(request):
    """Physiotherapy Jobs Alberta"""
    major_cities = [
        "Calgary", "Edmonton", "Red Deer", "Lethbridge", "St. Albert",
        "Medicine Hat", "Grande Prairie", "Airdrie", "Spruce Grove", "Fort McMurray"
    ]
    work_settings = [
        "Oil and gas industrial rehab", "Major teaching hospitals",
        "Rural health centres", "Sports performance clinics",
        "Workers compensation facilities", "Northern remote postings"
    ]
    
    context = get_province_context(
        province_name="Alberta",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Alberta offers competitive salaries and diverse practice settings."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in Alberta | Calgary & Edmonton Opportunities",
        "meta_description": "Find physiotherapy jobs in Alberta. Opportunities in Calgary, Edmonton, and across the province. Hospitals, industrial rehab, sports clinics, and rural health positions available.",
        "h1": "Physiotherapy Jobs in Alberta",
        "intro": """Alberta offers some of the most competitive physiotherapy compensation in Canada, combined with a lower cost of living than Toronto or Vancouver. The province's strong economy and growing population have created sustained demand for physiotherapy services across all practice areas.

Alberta Health Services (AHS) is the province's single health authority, offering standardized salaries and benefits across urban and rural positions. Private practice thrives in Calgary and Edmonton, with particular strength in sports medicine and occupational rehabilitation serving the energy sector.""",
        "certification_note": "Physiotherapists should confirm current registration requirements with the provincial regulatory college.",
        "job_board_slug": "alberta",
        "search_keywords": ["Calgary", "Edmonton", "Red Deer", "Lethbridge", "Medicine Hat"],
    })
    
    return render(request, "province_pages/province_base.html", context)


def saskatchewan_view(request):
    """Physiotherapy Jobs Saskatchewan"""
    major_cities = [
        "Saskatoon", "Regina", "Prince Albert", "Moose Jaw", "Lloydminster",
        "North Battleford", "Yorkton", "Swift Current", "Estevan", "Weyburn"
    ]
    work_settings = [
        "Saskatoon City Hospital", "Rural health centres", "Agricultural injury rehab",
        "University of Saskatchewan clinics", "Northern remote postings",
        "Multi-service community health"
    ]
    
    context = get_province_context(
        province_name="Saskatchewan",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Saskatchewan offers strong rural opportunities and growing urban centres."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in Saskatchewan | Saskatoon & Regina",
        "meta_description": "Discover physiotherapy careers in Saskatchewan. Jobs in Saskatoon, Regina, Prince Albert, and rural communities. Urban hospitals and rural health opportunities available.",
        "h1": "Physiotherapy Jobs in Saskatchewan",
        "intro": """Saskatchewan offers physiotherapists the opportunity to practice with significant autonomy, particularly in rural settings where professionals often work as the primary rehabilitation provider. The Saskatchewan Health Authority provides stable employment with comprehensive benefits.

The province's growing cities—Saskatoon and Regina—offer urban practice opportunities while maintaining a lower cost of living than major Canadian centres. Rural positions often include housing allowances and retention bonuses to attract practitioners to underserved communities.""",
        "certification_note": "Physiotherapists should confirm current registration requirements with the provincial regulatory college.",
        "job_board_slug": "saskatchewan",
        "search_keywords": ["Saskatoon", "Regina", "Prince Albert", "Moose Jaw", "Lloydminster"],
    })
    
    return render(request, "province_pages/province_base.html", context)


def manitoba_view(request):
    """Physiotherapy Jobs Manitoba"""
    major_cities = [
        "Winnipeg", "Brandon", "Steinbach", "Thompson", "Portage la Prairie",
        "Winkler", "Selkirk", "Morden", "Dauphin", "The Pas"
    ]
    work_settings = [
        "Winnipeg Health Sciences Centre", "Northern remote nursing stations",
        "Chronic disease management", "Indigenous community health",
        "Brandon Regional Health Centre", "Private orthopaedic clinics"
    ]
    
    context = get_province_context(
        province_name="Manitoba",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Manitoba offers unique northern and Indigenous health opportunities."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in Manitoba | Winnipeg & Northern Opportunities",
        "meta_description": "Find physiotherapy jobs in Manitoba. Opportunities in Winnipeg, Brandon, and Northern communities. Urban hospitals, rural health centres, and Indigenous health positions.",
        "h1": "Physiotherapy Jobs in Manitoba",
        "intro": """Manitoba offers physiotherapists unique opportunities to work with diverse populations, including Indigenous communities in Northern Manitoba. The province's Shared Health system coordinates care delivery across urban and remote settings.

Winnipeg serves as the primary hub, with major teaching hospitals offering complex case exposure. Rural and Northern positions provide comprehensive scopes of practice and often include fly-in/fly-out arrangements or live-in positions for remote communities.""",
        "certification_note": "Physiotherapists should confirm current registration requirements with the provincial regulatory college.",
        "job_board_slug": "manitoba",

        "search_keywords": ["Winnipeg", "Brandon", "Steinbach", "Thompson", "Portage la Prairie"],
    })
    
    return render(request, "province_pages/province_base.html", context)


def quebec_view(request):
    """Physiotherapy Jobs Quebec (Physiotherapie)"""
    major_cities = [
        "Montreal", "Quebec City", "Laval", "Gatineau", "Longueuil",
        "Sherbrooke", "Saguenay", "Trois-Rivieres", "Terrebonne", "Saint-Jean-sur-Richelieu"
    ]
    work_settings = [
        "CISSS/CIUSS hospitals", "Private francophone clinics",
        "Montreal rehabilitation institutes", "University-affiliated centres",
        "Bilingual rural health", "Long-term care (CHSLD) facilities"
    ]
    
    context = get_province_context(
        province_name="Quebec",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Quebec offers bilingual opportunities in Canada's largest francophone province."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in Quebec | Montreal & Quebec City Opportunities",
        "meta_description": "Find physiotherapy jobs in Quebec. Opportunities in Montreal, Quebec City, and across the province. Bilingual positions in hospitals, clinics, and rehabilitation centres.",
        "h1": "Physiotherapy Jobs in Quebec",
        "intro": """Quebec presents unique opportunities for physiotherapists, particularly those with French language skills. The province's distinct healthcare system, organized around CISSS and CIUSS health authorities, offers stable public sector employment with strong benefits.

Montreal serves as the primary hub with major teaching hospitals like CHUM and McGill University Health Centre. Quebec City, Sherbrooke, and regional centres offer growing opportunities. Bilingual physiotherapists are in high demand, with some positions available for English-only speakers in specific settings.""",
        "certification_note": "Physiotherapists should confirm current registration requirements with the provincial regulatory college.",
        "job_board_slug": "quebec",
        "search_keywords": ["Montreal", "Quebec City", "Laval", "Gatineau", "Sherbrooke"],
    })
    
    return render(request, "province_pages/province_base.html", context)


def nova_scotia_view(request):
    """Physiotherapy Jobs Nova Scotia"""
    major_cities = [
        "Halifax", "Dartmouth", "Sydney", "Truro", "New Glasgow",
        "Glace Bay", "Kentville", "Amherst", "Bridgewater", "Yarmouth"
    ]
    work_settings = [
        "QEII Health Sciences Centre", "Cape Breton regional hospitals",
        "Valley Health private practices", "Seniors' residential care",
        "Dalhousie University clinics", "Home care Nova Scotia"
    ]
    
    context = get_province_context(
        province_name="Nova Scotia",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Nova Scotia offers coastal living with growing healthcare opportunities."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in Nova Scotia | Halifax & Maritime Opportunities",
        "meta_description": "Explore physiotherapy careers in Nova Scotia. Jobs in Halifax, Sydney, Truro, and across the Maritimes. Urban hospitals, coastal clinics, and rural health opportunities.",
        "h1": "Physiotherapy Jobs in Nova Scotia",
        "intro": """Nova Scotia offers physiotherapists an attractive combination of coastal lifestyle and professional opportunity. The Nova Scotia Health Authority oversees care delivery across the province, with Halifax serving as the major centre for specialized rehabilitation.

The province's aging population has increased demand for physiotherapy in long-term care and home settings. Rural positions often include incentives to attract practitioners to underserved communities. The expanding Dalhousie University health programs contribute to a dynamic professional environment.""",
        "certification_note": "Physiotherapists should confirm current registration requirements with the provincial regulatory college.",
        "job_board_slug": "nova-scotia",
        "search_keywords": ["Halifax", "Dartmouth", "Sydney", "Truro", "New Glasgow"],
    })
    
    return render(request, "province_pages/province_base.html", context)


def new_brunswick_view(request):
    """Physiotherapy Jobs New Brunswick"""
    major_cities = [
        "Moncton", "Saint John", "Fredericton", "Dieppe", "Miramichi",
        "Edmundston", "Bathurst", "Campbellton", "Oromocto", "Grand Falls"
    ]
    work_settings = [
        "Horizon Health Network hospitals", "Vitalite Health Network",
        "Private francophone clinics", "Rural community health centres",
        "Nursing home rehabilitation", "Multi-service health clinics"
    ]
    
    context = get_province_context(
        province_name="New Brunswick",
        major_cities=major_cities,
        work_settings=work_settings,
        description="New Brunswick offers bilingual practice in Canada's only officially bilingual province."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in New Brunswick | Bilingual Opportunities",
        "meta_description": "Find physiotherapy jobs in New Brunswick. Opportunities in Moncton, Saint John, Fredericton, and bilingual communities. Horizon and Vitalite Health networks hiring now.",
        "h1": "Physiotherapy Jobs in New Brunswick",
        "intro": """New Brunswick offers physiotherapists a unique bilingual practice environment—Canada's only officially bilingual province. Both Horizon Health Network and Vitalite Health Network provide stable public sector employment across the province.

The province's aging demographics have driven investment in senior care and rehabilitation services. Rural opportunities are plentiful, with many communities actively recruiting to address healthcare gaps. Bilingual physiotherapists have expanded opportunities, particularly in Vitalite's francophone regions.""",
        "certification_note": "Physiotherapists should confirm current registration requirements with the provincial regulatory college.",
        "job_board_slug": "new-brunswick",
        "search_keywords": ["Moncton", "Saint John", "Fredericton", "Dieppe", "Miramichi"],
    })
    
    return render(request, "province_pages/province_base.html", context)


def newfoundland_view(request):
    """Physiotherapy Jobs Newfoundland and Labrador"""
    major_cities = [
        "St. John's", "Mount Pearl", "Corner Brook", "Conception Bay South",
        "Grand Falls-Windsor", "Paradise", "Gander", "Happy Valley-Goose Bay",
        "Labrador City", "Stephenville"
    ]
    work_settings = [
        "Eastern Health hospitals", "Labrador-Grenfell rural positions",
        "Central Health community clinics", "Remote nursing stations",
        "Long-term care homes", "Fly-in/fly-out arrangements"
    ]
    
    context = get_province_context(
        province_name="Newfoundland and Labrador",
        major_cities=major_cities,
        work_settings=work_settings,
        description="Newfoundland offers adventurous rural practice with competitive recruitment packages."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in Newfoundland and Labrador | St. John's & Rural",
        "meta_description": "Discover physiotherapy careers in Newfoundland and Labrador. Jobs in St. John's, Corner Brook, Labrador, and remote communities. Eastern Health and rural opportunities with incentives.",
        "h1": "Physiotherapy Jobs in Newfoundland and Labrador",
        "intro": """Newfoundland and Labrador offers physiotherapists unique opportunities for adventurous practice in spectacular coastal and northern settings. The province's four health regions—Eastern, Central, Western, and Labrador-Grenfell—offer diverse practice environments.

St. John's provides urban opportunities with the major teaching hospitals. Rural and Labrador positions often include substantial recruitment incentives, including relocation assistance, housing supports, and loan forgiveness programs. The scope of practice in rural settings can be expansive, with physiotherapists functioning as primary rehabilitation providers.""",
        "certification_note": "Physiotherapists should confirm current registration requirements with the provincial regulatory college.",
        "job_board_slug": "newfoundland",
        "search_keywords": ["St. John's", "Corner Brook", "Grand Falls", "Labrador", "Gander"],
    })
    
    return render(request, "province_pages/province_base.html", context)


def prince_edward_island_view(request):
    """Physiotherapy Jobs Prince Edward Island"""
    major_cities = [
        "Charlottetown", "Summerside", "Stratford", "Cornwall",
        "Montague", "Kensington", "Alberton", "Souris", "Tignish"
    ]
    work_settings = [
        "Queen Elizabeth Hospital", "Prince County Hospital",
        "Community care centres", "Home care services",
        "Long-term care facilities", "Multi-site rural coverage"
    ]
    
    context = get_province_context(
        province_name="Prince Edward Island",
        major_cities=major_cities,
        work_settings=work_settings,
        description="PEI offers intimate community practice with island lifestyle."
    )
    
    context.update({
        "page_title": "Physiotherapy Jobs in Prince Edward Island | Charlottetown Opportunities",
        "meta_description": "Find physiotherapy jobs in Prince Edward Island. Opportunities in Charlottetown, Summerside, and across the island. Community health, hospital, and rural positions available.",
        "h1": "Physiotherapy Jobs in Prince Edward Island",
        "intro": """Prince Edward Island offers physiotherapists a unique opportunity to practice in an intimate community setting where professionals often know their patients personally. Health PEI manages all public healthcare delivery across the island.

With only two major hospitals—Queen Elizabeth Hospital in Charlottetown and Prince County Hospital in Summerside—physiotherapists often work across multiple settings. The island's growing seasonal population and aging residents create year-round demand for rehabilitation services.""",
        "certification_note": "Physiotherapists should confirm current registration requirements with the provincial regulatory college.",
        "job_board_slug": "prince-edward-island",
        "search_keywords": ["Charlottetown", "Summerside", "Stratford", "Cornwall", "Montague"],
    })
    
    return render(request, "province_pages/province_base.html", context)
