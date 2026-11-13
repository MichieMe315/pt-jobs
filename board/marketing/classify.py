"""Classify existing employers without changing public profiles or outreach consent."""
import re
import unicodedata
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from django.db import transaction

from board.models import Employer, EmployerMarketingProfile
from .generator import PROVINCES


def key(value):
    return " ".join(re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKD", value.casefold()).encode("ascii", "ignore").decode()))


@lru_cache(maxsize=1)
def communities():
    path = Path(__file__).resolve().parents[2] / "career_mobility/data/community_economic_regions_2021.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {(key(r["city"]), r["province"]): r["city"] for r in data["records"]}


def suggest(employer):
    result = {}
    parts = [p.strip() for p in (employer.location or "").split(",") if p.strip()]
    if parts and parts[-1].casefold() == "canada":
        parts.pop()
    if len(parts) >= 2:
        province = next((code for code, name in PROVINCES.items() if key(parts[-1]) in (key(code), key(name))), None)
        if province:
            result["province"] = province
            city = communities().get((key(parts[-2]), PROVINCES[province]))
            if city:
                result["city"] = city
    name = key(employer.company_name or "")
    description = key(" ".join([employer.company_description or "", employer.description or ""]))
    if re.search(r"\b(university|college|association|supplier|equipment)\b", name) and not re.search(r"\b(hospital|hopital)\b", name):
        pass
    elif re.search(r"\b(health authority|health region|alberta health services|ontario health)\b", name):
        result["organization_type"] = "health_authority"
    elif re.search(r"\b(hospital|hopital)\b", name) and not re.search(r"\b(near|opposite|across from)\b", name):
        result["organization_type"] = "hospital"
    elif re.search(r"\b(clinic|clinique|physiotherapy|physical therapy|physiotherapie)\b", name):
        result["organization_type"] = "clinic"
    # Accept an employer's explicit location claim, not a claim about patients served.
    match = re.search(r"\b(?:based|located) in (?:a |an |the )?(remote|rural|urban)\b", description)
    if match:
        result["settlement"] = match[1]
    return result


def classify_employers(*, apply=False):
    counts = Counter()
    for employer in Employer.objects.select_related("marketing_profile").order_by("pk").iterator(chunk_size=300):
        counts["scanned"] += 1
        profile = getattr(employer, "marketing_profile", None)
        suggestions = suggest(employer)
        updates = {k: v for k, v in suggestions.items() if not profile or getattr(profile, k) in ("", "unknown")}
        if profile and profile.province and updates.get("province", profile.province) != profile.province:
            updates.pop("province", None)
            updates.pop("city", None)
        if profile and "city" in updates and profile.province and suggestions.get("province") != profile.province:
            updates.pop("city")
        if updates:
            counts["matched"] += 1
            counts.update(updates.keys())
            if apply:
                with transaction.atomic():
                    current, _ = EmployerMarketingProfile.objects.select_for_update().get_or_create(employer=employer)
                    changed = []
                    for field, value in updates.items():
                        if getattr(current, field) in ("", "unknown"):
                            setattr(current, field, value)
                            changed.append(field)
                    if changed:
                        current.save(update_fields=changed + ["updated_at"])
        if not updates.get("settlement") and (not profile or profile.settlement == "unknown"):
            counts["community_review"] += 1
    return counts
