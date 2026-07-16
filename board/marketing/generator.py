from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
from typing import Iterable

from django.contrib.staticfiles import finders
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter


PROVINCES = {
    "AB": "Alberta",
    "BC": "British Columbia",
    "MB": "Manitoba",
    "NB": "New Brunswick",
    "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia",
    "NT": "Northwest Territories",
    "NU": "Nunavut",
    "ON": "Ontario",
    "PE": "Prince Edward Island",
    "QC": "Quebec",
    "SK": "Saskatchewan",
    "YT": "Yukon",
}
PROVINCE_ALIASES = {
    **{key.lower(): key for key in PROVINCES},
    **{value.lower(): key for key, value in PROVINCES.items()},
}

HEADLINES = {
    "top_real": ("TOP EMPLOYERS.", "REAL OPPORTUNITIES."),
    "leading_clinics": ("CANADA'S LEADING", "CLINICS."),
    "clinics_hiring": ("CLINICS", "HIRING NOW."),
    "featured": ("FEATURED", "EMPLOYERS."),
    "careers": ("PHYSIOTHERAPY", "CAREERS."),
}


@dataclass
class EmployerCard:
    name: str
    location: str
    logo: object
    active_jobs: int
    created_at: object


def headline_text(key: str) -> str:
    first, second = HEADLINES.get(key, HEADLINES["top_real"])
    return f"{first} {second}"


def split_location(value: str) -> tuple[str, str]:
    value = (value or "").strip()
    if not value:
        return "", ""

    parts = [
        part.strip()
        for part in re.split(r",|\s+-\s+", value)
        if part.strip()
    ]
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
        [
            "DejaVuSansCondensed-Bold.ttf",
            "DejaVuSans-Bold.ttf",
            "Arial Bold.ttf",
            "arialbd.ttf",
        ]
        if bold
        else [
            "DejaVuSans.ttf",
            "Arial.ttf",
            "arial.ttf",
        ]
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_text(draw, text, max_width, start_size, bold=False, min_size=12):
    size = start_size
    while size > min_size:
        font = _font(size, bold)
        box = draw.textbbox((0, 0), text, font=font)
        if box[2] - box[0] <= max_width:
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


def _brand_logo():
    path = finders.find("board/marketing/brand-logo.jpg")
    if not path:
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _rounded_shadow(canvas, box, radius, fill, shadow=(0, 0, 0, 28), offset=5):
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.rounded_rectangle(
        (x1, y1 + offset, x2, y2 + offset),
        radius=radius,
        fill=shadow,
    )
    layer = layer.filter(ImageFilter.GaussianBlur(8))
    canvas.paste(layer, (0, 0), layer)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def _draw_background(draw, width, height):
    draw.rectangle((0, 0, width, height), fill="#F7F7F5")
    # restrained diagonal texture similar to the approved mock-up
    for offset in range(-height, width, 34):
        draw.line(
            (offset, 0, offset + height, height),
            fill="#ECECE9",
            width=1,
        )


def _format_config(output_format):
    if output_format == "portrait":
        return {
            "size": (1080, 1350),
            "margin": 58,
            "header_h": 345,
            "footer_h": 205,
            "cols": 4,
            "gap": 15,
        }
    if output_format == "landscape":
        return {
            "size": (1200, 630),
            "margin": 42,
            "header_h": 170,
            "footer_h": 105,
            "cols": 6,
            "gap": 12,
        }
    return {
        "size": (1080, 1080),
        "margin": 58,
        "header_h": 315,
        "footer_h": 190,
        "cols": 4,
        "gap": 14,
    }


def render_graphic(
    cards: Iterable[EmployerCard],
    headline_key: str,
    headline: str,
    region: str,
    output_format: str,
) -> bytes:
    cards = list(cards)
    cfg = _format_config(output_format)
    width, height = cfg["size"]
    margin = cfg["margin"]

    navy = "#071F36"
    red = "#C91427"
    white = "#FFFFFF"
    charcoal = "#172433"
    light_grey = "#E4E6E8"

    canvas = Image.new("RGB", (width, height), "#F7F7F5")
    draw = ImageDraw.Draw(canvas)
    _draw_background(draw, width, height)

    # ----- Brand logo -----
    brand = _brand_logo()
    if brand:
        if output_format == "landscape":
            brand_box = (width // 2 - 140, 15, width // 2 + 140, 76)
        else:
            brand_box = (width // 2 - 180, 20, width // 2 + 180, 116)

        bx1, by1, bx2, by2 = brand_box
        contained = ImageOps.contain(
            brand,
            (bx2 - bx1, by2 - by1),
            Image.Resampling.LANCZOS,
        )
        px = bx1 + (bx2 - bx1 - contained.width) // 2
        py = by1 + (by2 - by1 - contained.height) // 2
        canvas.paste(contained, (px, py))

    # ----- Headline -----
    first, second = HEADLINES.get(headline_key, HEADLINES["top_real"])
    if output_format == "landscape":
        title_size = 48
        title_y1 = 70
        title_gap = 48
    else:
        title_size = 78 if output_format == "square" else 82
        title_y1 = 122
        title_gap = 78

    title_font_1 = _fit_text(
        draw,
        first,
        width - 2 * margin,
        title_size,
        True,
        34,
    )
    title_font_2 = _fit_text(
        draw,
        second,
        width - 2 * margin,
        title_size,
        True,
        34,
    )
    draw.text(
        (width / 2, title_y1),
        first,
        font=title_font_1,
        fill=navy,
        anchor="ma",
    )
    draw.text(
        (width / 2, title_y1 + title_gap),
        second,
        font=title_font_2,
        fill=red,
        anchor="ma",
    )

    # ----- Employer count line -----
    count_y = cfg["header_h"] - (30 if output_format == "landscape" else 42)
    line_width = 120 if output_format != "landscape" else 78
    draw.line(
        (margin, count_y, margin + line_width, count_y),
        fill=red,
        width=2,
    )
    draw.line(
        (width - margin - line_width, count_y, width - margin, count_y),
        fill=red,
        width=2,
    )

    region_text = region.upper() if region else "CANADA"
    count_text = f"{len(cards)} EMPLOYERS  CURRENTLY HIRING IN {region_text}"
    count_font = _fit_text(
        draw,
        count_text,
        width - 2 * margin - 2 * line_width - 36,
        24 if output_format != "landscape" else 15,
        True,
        12,
    )
    draw.text(
        (width / 2, count_y),
        count_text,
        font=count_font,
        fill=charcoal,
        anchor="mm",
    )

    # ----- Logo grid -----
    footer_top = height - cfg["footer_h"]
    grid_top = cfg["header_h"]
    grid_bottom = footer_top - 10
    cols = min(cfg["cols"], max(1, len(cards)))
    rows = max(1, (len(cards) + cols - 1) // cols)
    gap = cfg["gap"]

    card_w = int((width - 2 * margin - gap * (cols - 1)) / cols)
    card_h = int((grid_bottom - grid_top - gap * (rows - 1)) / rows)
    card_h = max(card_h, 72)

    for index, card in enumerate(cards):
        row, col = divmod(index, cols)
        x = margin + col * (card_w + gap)
        y = grid_top + row * (card_h + gap)
        box = (x, y, x + card_w, y + card_h)

        _rounded_shadow(
            canvas,
            box,
            radius=14 if output_format == "landscape" else 17,
            fill=white,
        )

        logo = _open_logo(card.logo)
        if logo:
            padding_x = 18 if output_format == "landscape" else 20
            padding_y = 12 if output_format == "landscape" else 15
            contained = ImageOps.contain(
                logo,
                (
                    max(1, card_w - padding_x * 2),
                    max(1, card_h - padding_y * 2),
                ),
                Image.Resampling.LANCZOS,
            )
            px = x + (card_w - contained.width) // 2
            py = y + (card_h - contained.height) // 2
            canvas.paste(contained, (px, py), contained)

    # ----- Footer -----
    footer_y = footer_top
    draw.rectangle((0, footer_y, width, height), fill=navy)

    if output_format == "landscape":
        cta_w = 260
        top_band_h = 62
    else:
        cta_w = 330
        top_band_h = 104

    # Red angled CTA panel
    draw.polygon(
        [
            (width - cta_w - 52, footer_y),
            (width, footer_y),
            (width, footer_y + top_band_h),
            (width - cta_w, footer_y + top_band_h),
        ],
        fill=red,
    )

    professions = [
        "PHYSIOTHERAPY",
        "OT",
        "RMT",
        "OT",
        "CHIROPRACTIC",
        "KINESIOLOGY",
    ]
    usable_w = width - cta_w - 76
    step = usable_w / len(professions)
    profession_font = _font(17 if output_format != "landscape" else 11, True)

    for i, label in enumerate(professions):
        cx = 28 + step * i + step / 2
        draw.text(
            (cx, footer_y + top_band_h / 2),
            label,
            font=profession_font,
            fill=white,
            anchor="mm",
        )
        if i < len(professions) - 1:
            sx = 28 + step * (i + 1)
            draw.line(
                (sx, footer_y + 18, sx, footer_y + top_band_h - 18),
                fill=red,
                width=2,
            )

    cta_font = _fit_text(
        draw,
        "FIND YOUR NEXT\nCAREER MOVE.",
        cta_w - 45,
        28 if output_format != "landscape" else 18,
        True,
        14,
    )
    cta_x = width - cta_w / 2
    cta_y = footer_y + top_band_h / 2
    draw.multiline_text(
        (cta_x, cta_y),
        "FIND YOUR NEXT\nCAREER MOVE.",
        font=cta_font,
        fill=white,
        anchor="mm",
        align="center",
        spacing=3,
    )

    # Website bar: one colour, all white, as requested.
    website_y = footer_y + top_band_h
    draw.line((0, website_y, width, website_y), fill="#34495D", width=2)
    site_text = "PHYSIOTHERAPYJOBSCANADA.CA"
    site_font = _fit_text(
        draw,
        site_text,
        width - 2 * margin,
        29 if output_format != "landscape" else 19,
        True,
        16,
    )
    draw.text(
        (width / 2, website_y + (height - website_y) / 2),
        site_text,
        font=site_font,
        fill=white,
        anchor="mm",
    )

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
