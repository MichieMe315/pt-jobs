from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from board.models import Job


PROVINCES = {
    "ontario": {
        "name": "Ontario",
        "cities": ["Toronto", "Ottawa", "Mississauga", "Brampton", "Hamilton", "London", "Kitchener", "Waterloo", "Guelph", "Windsor"],
        "h1": "Physiotherapy Jobs in Ontario",
        "title": "Physiotherapy Jobs in Ontario | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in Ontario, including roles in private practice, rehabilitation, community care, and home care.",
        "intro": "Ontario has a broad physiotherapy employment landscape, with opportunities across large urban centres, suburban communities, regional cities, and smaller northern communities.\n\nPhysiotherapists may find roles in private practice, rehabilitation centres, community-based care, long-term care, sports rehabilitation, workplace injury recovery, post-operative rehabilitation, and home care services.",
        "regional": "Ontario job searches often include the Greater Toronto Area, Ottawa and Eastern Ontario, Hamilton and Niagara, Southwestern Ontario, Waterloo Region, London, Windsor, Barrie, Kingston, Sudbury, and Thunder Bay.",
    },
    "british-columbia": {
        "name": "British Columbia",
        "cities": ["Vancouver", "Victoria", "Surrey", "Burnaby", "Richmond", "Kelowna", "Abbotsford", "Nanaimo", "Kamloops", "Prince George"],
        "h1": "Physiotherapy Jobs in British Columbia",
        "title": "Physiotherapy Jobs in British Columbia | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in British Columbia, including clinic, rehabilitation, community care, and home care roles.",
        "intro": "British Columbia offers physiotherapy career opportunities across major coastal cities, interior communities, island communities, and northern regions.\n\nJob seekers may find roles in private practice, rehabilitation centres, home care, community-based care, sports rehabilitation, active aging programs, and interdisciplinary care environments.",
        "regional": "Common BC job searches include Metro Vancouver, Vancouver Island, the Fraser Valley, the Okanagan, Kamloops, northern communities, and smaller coastal communities.",
    },
    "alberta": {
        "name": "Alberta",
        "cities": ["Calgary", "Edmonton", "Red Deer", "Lethbridge", "Medicine Hat", "Grande Prairie", "Airdrie", "Fort McMurray"],
        "h1": "Physiotherapy Jobs in Alberta",
        "title": "Physiotherapy Jobs in Alberta | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in Alberta, including clinic, rehabilitation, workplace injury, and community care roles.",
        "intro": "Alberta has physiotherapy opportunities across large cities, regional centres, and northern communities.\n\nPhysiotherapists may find work in private practice, rehabilitation centres, workplace injury programs, sports rehabilitation, community care, home care, and regional practice settings.",
        "regional": "Alberta job searches often include Calgary, Edmonton, Red Deer, Lethbridge, Medicine Hat, Grande Prairie, Airdrie, and Fort McMurray.",
    },
    "saskatchewan": {
        "name": "Saskatchewan",
        "cities": ["Saskatoon", "Regina", "Prince Albert", "Moose Jaw", "Lloydminster", "Swift Current", "Yorkton", "North Battleford"],
        "h1": "Physiotherapy Jobs in Saskatchewan",
        "title": "Physiotherapy Jobs in Saskatchewan | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in Saskatchewan across private practice, rehabilitation, community care, and regional settings.",
        "intro": "Saskatchewan offers physiotherapy opportunities across urban centres, smaller cities, rural communities, and northern regions.\n\nRoles may include private practice, community care, home care, long-term care, and rehabilitation-focused work.",
        "regional": "Common Saskatchewan job searches include Saskatoon, Regina, Prince Albert, Moose Jaw, Lloydminster, Swift Current, Yorkton, and North Battleford.",
    },
    "manitoba": {
        "name": "Manitoba",
        "cities": ["Winnipeg", "Brandon", "Steinbach", "Thompson", "Portage la Prairie", "Winkler", "Selkirk", "Morden"],
        "h1": "Physiotherapy Jobs in Manitoba",
        "title": "Physiotherapy Jobs in Manitoba | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in Manitoba, including private practice, rehabilitation, community care, and regional roles.",
        "intro": "Manitoba offers physiotherapy opportunities in Winnipeg, regional centres, smaller communities, and northern areas.\n\nPhysiotherapists may work in private practice, rehabilitation, community-based care, long-term care, home care, and broader regional practice settings.",
        "regional": "Common Manitoba job searches include Winnipeg, Brandon, Steinbach, Thompson, Portage la Prairie, Winkler, Selkirk, and Morden.",
    },
    "quebec": {
        "name": "Quebec",
        "cities": ["Montreal", "Quebec City", "Laval", "Gatineau", "Longueuil", "Sherbrooke", "Trois-Rivieres", "Saguenay"],
        "h1": "Physiotherapy Jobs in Quebec",
        "title": "Physiotherapy Jobs in Quebec | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in Quebec, including private practice, rehabilitation, community care, and home care roles.",
        "intro": "Quebec offers physiotherapy opportunities across large urban centres, suburban communities, regional cities, and smaller communities.\n\nFrench language ability may be important for many roles, although requirements vary by position and setting.",
        "regional": "Common Quebec job searches include Montreal, Quebec City, Laval, Gatineau, Longueuil, Sherbrooke, Trois-Rivieres, and Saguenay.",
    },
    "nova-scotia": {
        "name": "Nova Scotia",
        "cities": ["Halifax", "Sydney", "Dartmouth", "Truro", "New Glasgow", "Kentville", "Bridgewater", "Yarmouth"],
        "h1": "Physiotherapy Jobs in Nova Scotia",
        "title": "Physiotherapy Jobs in Nova Scotia | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in Nova Scotia, including clinic, rehabilitation, home care, and community care roles.",
        "intro": "Nova Scotia offers physiotherapy opportunities across Halifax, regional towns, coastal communities, and rural areas.\n\nPhysiotherapists may find roles in private practice, rehabilitation centres, home care, long-term care, community-based care, and regional practice settings.",
        "regional": "Common Nova Scotia job searches include Halifax, Dartmouth, Sydney, Truro, New Glasgow, Kentville, Bridgewater, and Yarmouth.",
    },
    "new-brunswick": {
        "name": "New Brunswick",
        "cities": ["Moncton", "Saint John", "Fredericton", "Dieppe", "Miramichi", "Bathurst", "Edmundston", "Campbellton"],
        "h1": "Physiotherapy Jobs in New Brunswick",
        "title": "Physiotherapy Jobs in New Brunswick | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in New Brunswick across clinic, rehabilitation, home care, and community settings.",
        "intro": "New Brunswick offers physiotherapy opportunities across bilingual urban centres, smaller cities, rural communities, and coastal regions.\n\nLanguage requirements may vary by role and location, so job seekers should review each posting carefully.",
        "regional": "Common New Brunswick job searches include Moncton, Saint John, Fredericton, Dieppe, Miramichi, Bathurst, Edmundston, and Campbellton.",
    },
    "newfoundland-and-labrador": {
        "name": "Newfoundland and Labrador",
        "cities": ["St. John's", "Corner Brook", "Mount Pearl", "Conception Bay South", "Grand Falls-Windsor", "Paradise", "Gander", "Happy Valley-Goose Bay"],
        "h1": "Physiotherapy Jobs in Newfoundland and Labrador",
        "title": "Physiotherapy Jobs in Newfoundland and Labrador | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in Newfoundland and Labrador across clinic, rehabilitation, community, and regional settings.",
        "intro": "Newfoundland and Labrador offers physiotherapy opportunities across coastal communities, regional centres, and remote areas.\n\nPhysiotherapists may work in private practice, rehabilitation centres, home care, community-based care, long-term care, and regional practice settings.",
        "regional": "Common job searches include St. John's, Corner Brook, Mount Pearl, Conception Bay South, Grand Falls-Windsor, Gander, and Happy Valley-Goose Bay.",
    },
    "prince-edward-island": {
        "name": "Prince Edward Island",
        "cities": ["Charlottetown", "Summerside", "Stratford", "Cornwall", "Montague", "Kensington", "Souris", "Alberton"],
        "h1": "Physiotherapy Jobs in Prince Edward Island",
        "title": "Physiotherapy Jobs in Prince Edward Island | PT Jobs Canada",
        "description": "Explore physiotherapy jobs in Prince Edward Island across clinic, rehabilitation, home care, and community settings.",
        "intro": "Prince Edward Island offers physiotherapy opportunities in a smaller provincial market with community-focused practice settings.\n\nPhysiotherapists may find roles in private practice, rehabilitation centres, home care, long-term care, community-based care, and generalist practice environments.",
        "regional": "Common PEI job searches include Charlottetown, Summerside, Stratford, Cornwall, Montague, Kensington, Souris, and Alberton.",
    },
}


WORK_SETTINGS = [
    "Private practice settings",
    "Rehabilitation centres",
    "Community care",
    "Home care services",
    "Long-term care",
    "Sports rehabilitation",
]


def active_jobs_for_province(province_name, cities):
    today = timezone.localdate()

    qs = Job.objects.filter(is_active=True).filter(
        Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)
    ).select_related("employer")

    location_q = Q(location__icontains=province_name)

    province_abbr = {
        "Ontario": "ON",
        "British Columbia": "BC",
        "Alberta": "AB",
        "Saskatchewan": "SK",
        "Manitoba": "MB",
        "Quebec": "QC",
        "Nova Scotia": "NS",
        "New Brunswick": "NB",
        "Newfoundland and Labrador": "NL",
        "Prince Edward Island": "PE",
    }.get(province_name)

    if province_abbr:
        location_q |= Q(location__icontains=f", {province_abbr}")
        location_q |= Q(location__icontains=f" {province_abbr}")

    for city in cities:
        location_q |= Q(location__icontains=city)

    return qs.filter(location_q).order_by("-posting_date", "-id")[:8]


def render_province(request, slug):
    data = PROVINCES[slug]
    live_jobs = active_jobs_for_province(data["name"], data["cities"])

    context = {
        "province": data["name"],
        "page_title": data["title"],
        "meta_description": data["description"],
        "h1": data["h1"],
        "description": data["description"],
        "intro": data["intro"],
        "regional_context": data["regional"],
        "practice_settings_text": (
            f"Physiotherapy roles in {data['name']} may appear in private practice, "
            "rehabilitation centres, home care, community-based care, long-term care, "
            "sports rehabilitation, workplace injury programs, and interdisciplinary care settings."
        ),
        "registration_note": (
            f"Physiotherapists planning to work in {data['name']} should confirm current registration "
            "requirements with the appropriate provincial physiotherapy regulator before applying. "
            "This is especially important for internationally educated physiotherapists and applicants "
            "moving from another province."
        ),
        "work_settings": WORK_SETTINGS,
        "cities": data["cities"],
        "live_jobs": live_jobs,
    }
    return render(request, "province_pages/province_base.html", context)


def ontario_view(request):
    return render_province(request, "ontario")


def british_columbia_view(request):
    return render_province(request, "british-columbia")


def alberta_view(request):
    return render_province(request, "alberta")


def saskatchewan_view(request):
    return render_province(request, "saskatchewan")


def manitoba_view(request):
    return render_province(request, "manitoba")


def quebec_view(request):
    return render_province(request, "quebec")


def nova_scotia_view(request):
    return render_province(request, "nova-scotia")


def new_brunswick_view(request):
    return render_province(request, "new-brunswick")


def newfoundland_view(request):
    return render_province(request, "newfoundland-and-labrador")


def prince_edward_island_view(request):
    return render_province(request, "prince-edward-island")