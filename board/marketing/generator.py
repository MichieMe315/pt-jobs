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
    **{k.lower(): k for k in PROVINCES},
    **{v.lower(): k for k, v in PROVINCES.items()},
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
    parts = [p.strip() for p in re.split(r",|\s+-\s+", value) if p.strip()]
    city = parts[0] if parts else ""
    province = ""
    for part in reversed(parts[1:] or parts):
        cleaned = re.sub(r"\s+Canada$", "", part, flags=re.I).strip()
        code = PROVINCE_ALIASES.get(cleaned.lower())
        if code:
            province = code
            break
    return city, province


_FONT_CACHE = {}


def _font_path(bold: bool) -> str | None:
    key = "bold" if bold else "regular"
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSansCondensed-Bold.ttf",
            "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
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
            _FONT_CACHE[key] = path
            return path

    _FONT_CACHE[key] = None
    return None


def _font(size: int, bold: bool = False):
    path = _font_path(bold)
    if path:
        return ImageFont.truetype(path, size=size)
    # Pillow's bundled DejaVu font is often available by filename.
    try:
        return ImageFont.truetype(
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
            size=size,
        )
    except OSError:
        return ImageFont.load_default(size=size)


def _fit(draw, text, max_width, start_size, bold=True, minimum=14):
    for size in range(start_size, minimum - 1, -1):
        font = _font(size, bold)
        box = draw.textbbox((0, 0), text, font=font)
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


def _brand():
    path = finders.find("board/marketing/brand-logo.jpg")
    if not path:
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _shadow_card(canvas, box, radius):
    x1, y1, x2, y2 = box
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (x1, y1 + 6, x2, y2 + 6),
        radius=radius,
        fill=(0, 0, 0, 34),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    canvas.paste(shadow, (0, 0), shadow)
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


def _layout(fmt):
    if fmt == "portrait":
        return {
            "size": (1080, 1350),
            "limit": 20,
            "cols": 4,
            "margin": 58,
            "brand_box": (350, 22, 730, 130),
            "headline_y": 145,
            "headline_gap": 80,
            "count_y": 328,
            "grid_top": 365,
            "footer_top": 1120,
        }
    if fmt == "landscape":
        return {
            "size": (1200, 630),
            "limit": 12,
            "cols": 6,
            "margin": 42,
            "brand_box": (470, 10, 730, 72),
            "headline_y": 75,
            "headline_gap": 48,
            "count_y": 160,
            "grid_top": 184,
            "footer_top": 515,
        }
    return {
        "size": (1080, 1080),
        "limit": 16,
        "cols": 4,
        "margin": 58,
        "brand_box": (350, 18, 730, 120),
        "headline_y": 132,
        "headline_gap": 78,
        "count_y": 300,
        "grid_top": 338,
        "footer_top": 835,
    }


def render_graphic(*args, **kwargs) -> bytes:
    cards, headline_key, region, output_format = _resolve_call(args, kwargs)
    cfg = _layout(output_format)

    # Hard cap per format so square output always remains a clean 4x4 poster.
    cards = cards[: cfg["limit"]]

    width, height = cfg["size"]
    margin = cfg["margin"]
    navy = "#061E35"
    red = "#C9152C"
    white = "#FFFFFF"
    charcoal = "#172433"
    background = "#F8F7F4"

    canvas = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(canvas)

    # Very subtle texture.
    for offset in range(-height, width, 42):
        draw.line(
            (offset, 0, offset + height, height),
            fill="#EEECE8",
            width=1,
        )

    # Brand logo plaque.
    brand = _brand()
    if brand:
        x1, y1, x2, y2 = cfg["brand_box"]
        fitted = ImageOps.fit(
            brand,
            (x2 - x1, y2 - y1),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.52),
        )
        canvas.paste(fitted, (x1, y1))

    first, second = HEADLINES.get(headline_key, HEADLINES["top_real"])
    if output_format == "landscape":
        title_start = 54
    else:
        title_start = 84

    title1 = _fit(draw, first, width - 2 * margin, title_start, True, 38)
    title2 = _fit(draw, second, width - 2 * margin, title_start, True, 38)

    draw.text(
        (width / 2, cfg["headline_y"]),
        first,
        font=title1,
        fill=navy,
        anchor="ma",
    )
    draw.text(
        (width / 2, cfg["headline_y"] + cfg["headline_gap"]),
        second,
        font=title2,
        fill=red,
        anchor="ma",
    )

    # Count line.
    count_y = cfg["count_y"]
    line_w = 125 if output_format != "landscape" else 80
    draw.line((margin, count_y, margin + line_w, count_y), fill=red, width=2)
    draw.line(
        (width - margin - line_w, count_y, width - margin, count_y),
        fill=red,
        width=2,
    )

    region_label = (region or "Canada").upper()
    count_text = f"{len(cards)} EMPLOYERS  CURRENTLY HIRING IN {region_label}"
    count_font = _fit(
        draw,
        count_text,
        width - 2 * margin - 2 * line_w - 36,
        23 if output_format != "landscape" else 15,
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

    # Fixed clean grid.
    cols = cfg["cols"]
    rows = max(1, (len(cards) + cols - 1) // cols)
    gap = 15 if output_format != "landscape" else 10
    grid_top = cfg["grid_top"]
    grid_bottom = cfg["footer_top"] - 16
    card_w = int((width - 2 * margin - gap * (cols - 1)) / cols)
    card_h = int((grid_bottom - grid_top - gap * (rows - 1)) / rows)

    for idx, card in enumerate(cards):
        row, col = divmod(idx, cols)
        row_count = min(cols, len(cards) - row * cols)
        row_width = row_count * card_w + (row_count - 1) * gap
        row_start_x = int((width - row_width) / 2)

        x = row_start_x + col * (card_w + gap)
        y = grid_top + row * (card_h + gap)
        box = (x, y, x + card_w, y + card_h)
        _shadow_card(canvas, box, 16 if output_format != "landscape" else 12)

        logo = _open_logo(card.logo)
        if logo:
            pad_x = 22 if output_format != "landscape" else 16
            pad_y = 16 if output_format != "landscape" else 10
            fitted = ImageOps.contain(
                logo,
                (card_w - 2 * pad_x, card_h - 2 * pad_y),
                Image.Resampling.LANCZOS,
            )
            px = x + (card_w - fitted.width) // 2
            py = y + (card_h - fitted.height) // 2
            canvas.paste(fitted, (px, py), fitted)

    # Footer matching approved mock-up.
    footer_top = cfg["footer_top"]
    draw.rectangle((0, footer_top, width, height), fill=navy)

    if output_format == "landscape":
        top_band = 65
        cta_w = 285
    else:
        top_band = 108
        cta_w = 335

    draw.polygon(
        [
            (width - cta_w - 48, footer_top),
            (width, footer_top),
            (width, footer_top + top_band),
            (width - cta_w, footer_top + top_band),
        ],
        fill=red,
    )

    labels = ["PHYSIOTHERAPY", "OT", "RMT", "OT", "CHIROPRACTIC", "KINESIOLOGY"]
    usable = width - cta_w - 76
    step = usable / len(labels)
    label_font = _font(14 if output_format != "landscape" else 9, True)
    badge_font = _font(11 if output_format != "landscape" else 7, True)

    badge_map = {
        "PHYSIOTHERAPY": "PT",
        "OT": "OT",
        "RMT": "RMT",
        "CHIROPRACTIC": "DC",
        "KINESIOLOGY": "KIN",
    }

    for i, label in enumerate(labels):
        cx = 28 + i * step + step / 2
        cy = footer_top + (34 if output_format != "landscape" else 20)
        radius = 18 if output_format != "landscape" else 11

        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            outline=white,
            width=2,
        )
        draw.text(
            (cx, cy),
            badge_map[label],
            font=badge_font,
            fill=white,
            anchor="mm",
        )
        draw.text(
            (cx, footer_top + top_band - 24),
            label,
            font=label_font,
            fill=white,
            anchor="mm",
        )

        if i < len(labels) - 1:
            separator_x = 28 + (i + 1) * step
            draw.line(
                (
                    separator_x,
                    footer_top + 18,
                    separator_x,
                    footer_top + top_band - 18,
                ),
                fill=red,
                width=2,
            )

    cta_x = width - cta_w / 2
    cta_font = _fit(
        draw,
        "FIND YOUR NEXT",
        cta_w - 55,
        27 if output_format != "landscape" else 17,
        True,
        13,
    )
    draw.text(
        (cta_x, footer_top + top_band / 2 - 15),
        "FIND YOUR NEXT",
        font=cta_font,
        fill=white,
        anchor="mm",
    )
    draw.text(
        (cta_x, footer_top + top_band / 2 + 18),
        "CAREER MOVE.",
        font=cta_font,
        fill=white,
        anchor="mm",
    )
    draw.line(
        (
            cta_x - 90,
            footer_top + top_band - 18,
            cta_x + 90,
            footer_top + top_band - 18,
        ),
        fill=white,
        width=3,
    )

    website_top = footer_top + top_band
    draw.line((0, website_top, width, website_top), fill="#34495D", width=2)
    site_font = _fit(
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
        font=site_font,
        fill=white,
        anchor="mm",
    )

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
