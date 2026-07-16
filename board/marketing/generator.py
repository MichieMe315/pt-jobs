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


def _draw_centered_lines(draw, lines, center_x, start_y, line_gap, font, fill):
    for index, line in enumerate(lines):
        draw.text((center_x, start_y + index * line_gap), line, font=font, fill=fill, anchor="ma")


def render_graphic(cards: Iterable[EmployerCard], title: str, subtitle: str, output_format: str) -> bytes:
    sizes = {"portrait": (1080, 1350), "square": (1080, 1080), "landscape": (1200, 630)}
    width, height = sizes.get(output_format, sizes["portrait"])
    cards = list(cards)

    navy = "#123A5A"
    blue = "#2E80C5"
    pale = "#F4F8FB"
    border = "#D5E2EC"
    grey = "#5B7083"
    white = "#FFFFFF"

    canvas = Image.new("RGB", (width, height), pale)
    draw = ImageDraw.Draw(canvas)
    margin = int(width * 0.055)

    if output_format == "landscape":
        header_bottom = 132
        footer_top = height - 94
        title_size = 44
        subtitle_size = 18
        cols = min(6, max(3, len(cards)))
        gap = 16
        card_radius = 16
        logo_padding = 18
    else:
        header_bottom = 235 if output_format == "portrait" else 205
        footer_top = height - (190 if output_format == "portrait" else 170)
        title_size = 64 if output_format == "portrait" else 55
        subtitle_size = 24 if output_format == "portrait" else 21
        cols = 4 if len(cards) > 9 else 3
        gap = 18
        card_radius = 20
        logo_padding = 22

    # Header: strong hierarchy, no oversized empty box.
    draw.rounded_rectangle((margin, 34, width - margin, header_bottom), radius=30, fill=white)
    draw.rounded_rectangle((margin + 34, 55, margin + 46, header_bottom - 20), radius=6, fill=blue)

    normalized_title = (title or "NOW HIRING ACROSS CANADA").upper().strip()
    if " ACROSS " in normalized_title:
        first, second = normalized_title.split(" ACROSS ", 1)
        title_lines = [first, f"ACROSS {second}"]
    else:
        title_lines = [normalized_title]

    max_title_width = width - 2 * margin - 145
    title_font = _fit_text(draw, max(title_lines, key=len), max_title_width, title_size, True, 30)
    title_y = 61 if len(title_lines) == 2 else 84
    title_gap = int(title_font.size * 0.92) if hasattr(title_font, "size") else 48
    _draw_centered_lines(draw, title_lines, width / 2, title_y, title_gap, title_font, navy)

    subtitle_font = _fit_text(draw, subtitle, max_title_width, subtitle_size, False, 14)
    subtitle_y = header_bottom - 43
    draw.text((width / 2, subtitle_y), subtitle, font=subtitle_font, fill=grey, anchor="ma")

    # Tight logo-only grid. Logos are the artwork; no names or job counts.
    grid_top = header_bottom + (28 if output_format != "landscape" else 18)
    grid_bottom = footer_top - (25 if output_format != "landscape" else 16)
    count = max(1, len(cards))
    rows = max(1, (count + cols - 1) // cols)
    card_w = int((width - 2 * margin - gap * (cols - 1)) / cols)
    card_h = int((grid_bottom - grid_top - gap * (rows - 1)) / rows)

    for idx, card in enumerate(cards):
        row, col = divmod(idx, cols)
        x = margin + col * (card_w + gap)
        y = grid_top + row * (card_h + gap)
        draw.rounded_rectangle(
            (x, y, x + card_w, y + card_h),
            radius=card_radius,
            fill=white,
            outline=border,
            width=2,
        )

        logo = _open_logo(card.logo)
        if logo:
            max_logo_w = max(1, card_w - logo_padding * 2)
            max_logo_h = max(1, card_h - logo_padding * 2)
            contained = ImageOps.contain(logo, (max_logo_w, max_logo_h), Image.Resampling.LANCZOS)
            px = x + (card_w - contained.width) // 2
            py = y + (card_h - contained.height) // 2
            canvas.paste(contained, (px, py), contained)

    # Footer: strong CTA and readable site address.
    if output_format == "landscape":
        profession_y = footer_top + 16
        banner_y1 = footer_top + 44
        banner_y2 = height - 20
        profession_size = 17
        site_size = 24
        cta = "EXPLORE CURRENT OPPORTUNITIES"
    else:
        profession_y = footer_top + 18
        banner_y1 = footer_top + 58
        banner_y2 = height - 24
        profession_size = 23 if output_format == "portrait" else 20
        site_size = 36 if output_format == "portrait" else 31
        cta = "EXPLORE CURRENT OPPORTUNITIES"

    profession = "PHYSIOTHERAPY  •  OT  •  RMT  •  SLP  •  CHIROPRACTIC"
    profession_font = _fit_text(draw, profession, width - 2 * margin, profession_size, True, 13)
    draw.text((width / 2, profession_y), profession, font=profession_font, fill=navy, anchor="ma")

    draw.rounded_rectangle((margin, banner_y1, width - margin, banner_y2), radius=24, fill=blue)
    cta_font = _fit_text(draw, cta, width - 2 * margin - 70, 17 if output_format != "landscape" else 13, True, 11)
    site_font = _fit_text(draw, "PhysiotherapyJobsCanada.ca", width - 2 * margin - 70, site_size, True, 20)
    banner_mid = (banner_y1 + banner_y2) / 2
    draw.text((width / 2, banner_mid - (22 if output_format != "landscape" else 13)), cta, font=cta_font, fill=white, anchor="mm")
    draw.text((width / 2, banner_mid + (25 if output_format != "landscape" else 13)), "PhysiotherapyJobsCanada.ca", font=site_font, fill=white, anchor="mm")

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
