from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import re
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


PROVINCES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
    "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia", "NT": "Northwest Territories", "NU": "Nunavut",
    "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "SK": "Saskatchewan", "YT": "Yukon",
}
PROVINCE_ALIASES = {**{k.lower(): k for k in PROVINCES}, **{v.lower(): k for k, v in PROVINCES.items()}}


@dataclass
class EmployerCard:
    name: str
    location: str
    logo: object
    active_jobs: int
    created_at: object


def split_location(value: str) -> tuple[str, str]:
    value = (value or "").strip()
    if not value:
        return "", ""
    parts = [part.strip() for part in re.split(r",|\s+-\s+", value) if part.strip()]
    city = parts[0] if parts else ""
    province = ""
    for part in reversed(parts[1:] or parts):
        cleaned = re.sub(r"\s+Canada$", "", part, flags=re.I).strip()
        key = PROVINCE_ALIASES.get(cleaned.lower())
        if key:
            province = key
            break
    return city, province


def _font(size: int, bold: bool = False):
    candidates = (
        ["DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf"] if bold
        else ["DejaVuSans.ttf", "Arial.ttf", "arial.ttf"]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_text(draw, text, max_width, start_size, bold=False, min_size=13):
    size = start_size
    while size > min_size:
        font = _font(size, bold)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return font
        size -= 1
    return _font(min_size, bold)


def _open_logo(field):
    try:
        field.open("rb")
        image = Image.open(field).convert("RGBA")
        image.load()
        field.close()
        return image
    except Exception:
        try:
            field.close()
        except Exception:
            pass
        return None


def render_graphic(cards: Iterable[EmployerCard], title: str, subtitle: str, output_format: str) -> bytes:
    sizes = {"portrait": (1080, 1350), "square": (1080, 1080), "landscape": (1200, 630)}
    width, height = sizes.get(output_format, sizes["portrait"])
    cards = list(cards)

    navy, blue, pale, border, grey = "#123A5A", "#2E80C5", "#F5F8FB", "#DDE7EF", "#5B7083"
    canvas = Image.new("RGB", (width, height), pale)
    draw = ImageDraw.Draw(canvas)

    margin = int(width * 0.055)
    header_h = 190 if height >= 1000 else 115
    footer_h = 145 if height >= 1000 else 85

    draw.rounded_rectangle((margin, 35, width-margin, header_h), radius=28, fill="white")
    title_font = _fit_text(draw, title.upper(), width-2*margin-60, 60 if height >= 1000 else 40, True)
    draw.text((width/2, 72 if height >= 1000 else 51), title.upper(), font=title_font, fill=navy, anchor="ma")
    subtitle_font = _fit_text(draw, subtitle, width-2*margin-70, 25 if height >= 1000 else 18)
    draw.text((width/2, 143 if height >= 1000 else 91), subtitle, font=subtitle_font, fill=grey, anchor="ma")

    grid_top = header_h + 45
    grid_bottom = height - footer_h - 30
    count = max(1, len(cards))
    if output_format == "landscape":
        cols = min(6, max(3, count))
    elif count <= 12:
        cols = 3
    else:
        cols = 4
    rows = (count + cols - 1) // cols
    gap = 18
    card_w = int((width - 2*margin - gap*(cols-1)) / cols)
    card_h = int((grid_bottom-grid_top-gap*(rows-1)) / max(rows, 1))

    for idx, card in enumerate(cards):
        row, col = divmod(idx, cols)
        x = margin + col*(card_w+gap)
        y = grid_top + row*(card_h+gap)
        draw.rounded_rectangle((x, y, x+card_w, y+card_h), radius=18, fill="white", outline=border, width=2)
        text_space = 52 if card_h >= 140 else 36
        logo_box = (x+18, y+14, x+card_w-18, y+card_h-text_space)
        logo = _open_logo(card.logo)
        if logo:
            contained = ImageOps.contain(logo, (max(1, logo_box[2]-logo_box[0]), max(1, logo_box[3]-logo_box[1])))
            px = logo_box[0] + (logo_box[2]-logo_box[0]-contained.width)//2
            py = logo_box[1] + (logo_box[3]-logo_box[1]-contained.height)//2
            canvas.paste(contained, (px, py), contained)
        name_font = _fit_text(draw, card.name, card_w-24, 18 if height >= 1000 else 13, True, 10)
        draw.text((x+card_w/2, y+card_h-34 if card_h >= 140 else y+card_h-23), card.name, font=name_font, fill=navy, anchor="mm")
        if card_h >= 150:
            jobs = f"{card.active_jobs} active job" + ("s" if card.active_jobs != 1 else "")
            draw.text((x+card_w/2, y+card_h-14), jobs, font=_font(12), fill=grey, anchor="mm")

    footer_y = height-footer_h
    draw.text((width/2, footer_y+30), "PHYSIOTHERAPY  •  OT  •  RMT  •  SLP  •  CHIRO", font=_fit_text(draw, "PHYSIOTHERAPY  •  OT  •  RMT  •  SLP  •  CHIRO", width-2*margin, 27 if height >= 1000 else 18, True), fill=navy, anchor="ma")
    draw.rounded_rectangle((margin, footer_y+67 if height >= 1000 else footer_y+44, width-margin, height-25), radius=22, fill=blue)
    draw.text((width/2, height-61 if height >= 1000 else height-39), "PhysiotherapyJobsCanada.ca", font=_fit_text(draw, "PhysiotherapyJobsCanada.ca", width-2*margin-40, 34 if height >= 1000 else 23, True), fill="white", anchor="mm")

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
