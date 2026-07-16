from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
import re
from typing import Iterable

from django.contrib.staticfiles import finders
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter


PROVINCES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
    "NB": "New Brunswick", "NL": "Newfoundland and Labrador",
    "NS": "Nova Scotia", "NT": "Northwest Territories", "NU": "Nunavut",
    "ON": "Ontario", "PE": "Prince Edward Island", "QC": "Quebec",
    "SK": "Saskatchewan", "YT": "Yukon",
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
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSansCondensed-Bold.ttf",
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        if bold
        else
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans.ttf",
            "C:/Windows/Fonts/arial.ttf",
        ]
    )

    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size=size)

    try:
        return ImageFont.truetype(
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
            size=size,
        )
    except OSError:
        return ImageFont.load_default(size=size)


def _fit(draw, text, max_width, start_size, bold=True, minimum=12):
    for size in range(start_size, minimum - 1, -1):
        font = _font(size, bold)
        box = draw.textbbox((0, 0), text, font=font, stroke_width=1 if bold else 0)
        if box[2] - box[0] <= max_width:
            return font
    return _font(minimum, bold)


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
    path = finders.find("board/marketing/brand-logo.png")
    if not path:
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def _shadow_card(canvas, box, radius):
    x1, y1, x2, y2 = box
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer_draw = ImageDraw.Draw(layer)
    layer_draw.rounded_rectangle(
        (x1, y1 + 5, x2, y2 + 5),
        radius=radius,
        fill=(0, 0, 0, 34),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(9))
    canvas.paste(layer, (0, 0), layer)
    ImageDraw.Draw(canvas).rounded_rectangle(
        box,
        radius=radius,
        fill="#FFFFFF",
        outline="#ECECEC",
        width=1,
    )


def _resolve_call(args, kwargs):
    cards = kwargs.get("cards")
    if cards is None and args:
        cards = args[0]

    output_format = kwargs.get("output_format")
    if not output_format:
        output_format = args[3] if len(args) >= 4 else "square"

    headline_key = kwargs.get("headline_key", "top_real")
    region = kwargs.get("region", "Canada")

    if len(args) >= 2 and isinstance(args[1], str):
        old_title = args[1].strip()
        lower = old_title.lower()
        if lower.startswith("hiring in "):
            region = old_title[10:].strip()
        elif "canada" in lower:
            region = "Canada"

    return list(cards or []), headline_key, region, output_format


def _config(output_format):
    if output_format == "portrait":
        return {
            "size": (1080, 1350),
            "max_cards": 20,
            "cols": 4,
            "margin": 56,
            "brand_y": 18,
            "brand_size": (350, 100),
            "headline_y": 138,
            "headline_gap": 80,
            "count_y": 324,
            "grid_top": 360,
            "footer_top": 1120,
        }

    if output_format == "landscape":
        return {
            "size": (1200, 630),
            "max_cards": 12,
            "cols": 6,
            "margin": 40,
            "brand_y": 8,
            "brand_size": (260, 66),
            "headline_y": 72,
            "headline_gap": 48,
            "count_y": 158,
            "grid_top": 182,
            "footer_top": 515,
        }

    return {
        "size": (1080, 1080),
        "max_cards": 16,
        "cols": 4,
        "margin": 58,
        "brand_y": 14,
        "brand_size": (350, 100),
        "headline_y": 128,
        "headline_gap": 78,
        "count_y": 295,
        "grid_top": 330,
        "footer_top": 820,
    }


def render_graphic(*args, **kwargs) -> bytes:
    cards, headline_key, region, output_format = _resolve_call(args, kwargs)
    cfg = _config(output_format)
    cards = cards[: cfg["max_cards"]]

    width, height = cfg["size"]
    margin = cfg["margin"]

    navy = "#061E35"
    red = "#C9162B"
    white = "#FFFFFF"
    charcoal = "#192636"
    background = "#F8F7F4"

    canvas = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(canvas)

    # Restrained paper texture.
    for offset in range(-height, width, 44):
        draw.line(
            (offset, 0, offset + height, height),
            fill="#EEECE8",
            width=1,
        )

    # Clean transparent brand logo on white.
    brand = _brand_logo()
    if brand:
        brand = ImageOps.contain(
            brand,
            cfg["brand_size"],
            Image.Resampling.LANCZOS,
        )
        canvas.paste(
            brand,
            ((width - brand.width) // 2, cfg["brand_y"]),
            brand,
        )

    first, second = HEADLINES.get(headline_key, HEADLINES["top_real"])
    title_start = 82 if output_format != "landscape" else 52
    first_font = _fit(draw, first, width - 2 * margin, title_start, True, 36)
    second_font = _fit(draw, second, width - 2 * margin, title_start, True, 36)

    draw.text(
        (width / 2, cfg["headline_y"]),
        first,
        font=first_font,
        fill=navy,
        anchor="ma",
        stroke_width=1,
        stroke_fill=navy,
    )
    draw.text(
        (width / 2, cfg["headline_y"] + cfg["headline_gap"]),
        second,
        font=second_font,
        fill=red,
        anchor="ma",
        stroke_width=1,
        stroke_fill=red,
    )

    count_y = cfg["count_y"]
    line_width = 120 if output_format != "landscape" else 76
    draw.line((margin, count_y, margin + line_width, count_y), fill=red, width=2)
    draw.line(
        (width - margin - line_width, count_y, width - margin, count_y),
        fill=red,
        width=2,
    )

    count_text = f"{len(cards)} EMPLOYERS  CURRENTLY HIRING IN {(region or 'Canada').upper()}"
    count_font = _fit(
        draw,
        count_text,
        width - 2 * margin - 2 * line_width - 35,
        22 if output_format != "landscape" else 14,
        True,
        11,
    )
    draw.text(
        (width / 2, count_y),
        count_text,
        font=count_font,
        fill=charcoal,
        anchor="mm",
    )

    # Logo grid — the same tight proportions as the approved mock-up.
    cols = cfg["cols"]
    rows = max(1, (len(cards) + cols - 1) // cols)
    gap = 14 if output_format != "landscape" else 10
    grid_bottom = cfg["footer_top"] - 16
    card_width = int((width - 2 * margin - gap * (cols - 1)) / cols)
    card_height = int(
        (grid_bottom - cfg["grid_top"] - gap * (rows - 1)) / rows
    )

    for index, card in enumerate(cards):
        row, column = divmod(index, cols)
        row_count = min(cols, len(cards) - row * cols)
        row_total_width = row_count * card_width + (row_count - 1) * gap
        row_start = int((width - row_total_width) / 2)

        x = row_start + column * (card_width + gap)
        y = cfg["grid_top"] + row * (card_height + gap)
        box = (x, y, x + card_width, y + card_height)

        _shadow_card(
            canvas,
            box,
            radius=15 if output_format != "landscape" else 11,
        )

        logo = _open_logo(card.logo)
        if logo:
            fitted = ImageOps.contain(
                logo,
                (
                    card_width - (34 if output_format != "landscape" else 22),
                    card_height - (24 if output_format != "landscape" else 16),
                ),
                Image.Resampling.LANCZOS,
            )
            px = x + (card_width - fitted.width) // 2
            py = y + (card_height - fitted.height) // 2
            canvas.paste(fitted, (px, py), fitted)

    # Footer matching the mock-up.
    footer_top = cfg["footer_top"]
    draw.rectangle((0, footer_top, width, height), fill=navy)

    top_band_height = 106 if output_format != "landscape" else 64
    cta_width = 335 if output_format != "landscape" else 285

    draw.polygon(
        [
            (width - cta_width - 48, footer_top),
            (width, footer_top),
            (width, footer_top + top_band_height),
            (width - cta_width, footer_top + top_band_height),
        ],
        fill=red,
    )

    professions = [
        ("PT", "PHYSIOTHERAPY"),
        ("OT", "OT"),
        ("RMT", "RMT"),
        ("SLP", "SLP"),
        ("DC", "CHIROPRACTIC"),
        ("KIN", "KINESIOLOGY"),
    ]

    usable_width = width - cta_width - 75
    step = usable_width / len(professions)
    badge_font = _font(10 if output_format != "landscape" else 7, True)
    label_font = _font(13 if output_format != "landscape" else 8, True)

    for index, (badge, label) in enumerate(professions):
        center_x = 26 + step * index + step / 2
        badge_y = footer_top + (32 if output_format != "landscape" else 19)
        radius = 17 if output_format != "landscape" else 10

        draw.ellipse(
            (
                center_x - radius,
                badge_y - radius,
                center_x + radius,
                badge_y + radius,
            ),
            outline=white,
            width=2,
        )
        draw.text(
            (center_x, badge_y),
            badge,
            font=badge_font,
            fill=white,
            anchor="mm",
        )
        draw.text(
            (center_x, footer_top + top_band_height - 23),
            label,
            font=label_font,
            fill=white,
            anchor="mm",
        )

        if index < len(professions) - 1:
            separator_x = 26 + step * (index + 1)
            draw.line(
                (
                    separator_x,
                    footer_top + 16,
                    separator_x,
                    footer_top + top_band_height - 16,
                ),
                fill=red,
                width=2,
            )

    cta_x = width - cta_width / 2
    cta_font = _fit(
        draw,
        "FIND YOUR NEXT",
        cta_width - 48,
        26 if output_format != "landscape" else 16,
        True,
        12,
    )
    draw.text(
        (cta_x, footer_top + top_band_height / 2 - 15),
        "FIND YOUR NEXT",
        font=cta_font,
        fill=white,
        anchor="mm",
    )
    draw.text(
        (cta_x, footer_top + top_band_height / 2 + 18),
        "CAREER MOVE.",
        font=cta_font,
        fill=white,
        anchor="mm",
    )
    draw.line(
        (
            cta_x - 88,
            footer_top + top_band_height - 17,
            cta_x + 88,
            footer_top + top_band_height - 17,
        ),
        fill=white,
        width=3,
    )

    website_top = footer_top + top_band_height
    draw.line((0, website_top, width, website_top), fill="#34495D", width=2)

    website_font = _fit(
        draw,
        "PHYSIOTHERAPYJOBSCANADA.CA",
        width - 2 * margin,
        28 if output_format != "landscape" else 18,
        True,
        14,
    )
    draw.text(
        (width / 2, website_top + (height - website_top) / 2),
        "PHYSIOTHERAPYJOBSCANADA.CA",
        font=website_font,
        fill=white,
        anchor="mm",
    )

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
