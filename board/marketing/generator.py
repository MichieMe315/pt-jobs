from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
import re
from typing import Iterable

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
            "C:/Windows/Fonts/arialbd.ttf",
        ]
        if bold
        else
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
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


def _collage_config(output_format):
    if output_format == "portrait":
        return {
            "size": (1080, 1350),
            "max_cards": 20,
            "cols": 4,
            "margin": 56,
            "headline_y": 58,
            "headline_gap": 80,
            "subhead_y": 245,
            "grid_top": 285,
            "footer_top": 1165,
        }

    if output_format == "landscape":
        return {
            "size": (1200, 630),
            "max_cards": 12,
            "cols": 6,
            "margin": 40,
            "headline_y": 24,
            "headline_gap": 48,
            "subhead_y": 125,
            "grid_top": 150,
            "footer_top": 535,
        }

    return {
        "size": (1080, 1080),
        "max_cards": 16,
        "cols": 4,
        "margin": 58,
        "headline_y": 55,
        "headline_gap": 78,
        "subhead_y": 235,
        "grid_top": 275,
        "footer_top": 880,
    }


def render_graphic(
    cards: Iterable[EmployerCard],
    headline_key: str = "top_real",
    headline: str = "",
    region: str = "Canada",
    output_format: str = "square",
) -> bytes:
    cards = list(cards)
    cfg = _collage_config(output_format)
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

    for offset in range(-height, width, 44):
        draw.line((offset, 0, offset + height, height), fill="#EEECE8", width=1)

    first, second = HEADLINES.get(headline_key, HEADLINES["top_real"])
    title_size = 82 if output_format != "landscape" else 50
    first_font = _fit(draw, first, width - 2 * margin, title_size, True, 34)
    second_font = _fit(draw, second, width - 2 * margin, title_size, True, 34)

    draw.text(
        (width / 2, cfg["headline_y"]),
        first,
        font=first_font,
        fill=navy,
        anchor="ma",
    )
    draw.text(
        (width / 2, cfg["headline_y"] + cfg["headline_gap"]),
        second,
        font=second_font,
        fill=red,
        anchor="ma",
    )

    if region and region.lower() != "canada":
        subhead = f"Discover employers hiring in {region}"
    else:
        subhead = "Discover employers hiring now"

    subhead_font = _fit(
        draw,
        subhead,
        width - 2 * margin - 180,
        26 if output_format != "landscape" else 16,
        True,
        13,
    )
    line_width = 120 if output_format != "landscape" else 75
    draw.line(
        (margin, cfg["subhead_y"], margin + line_width, cfg["subhead_y"]),
        fill=red,
        width=2,
    )
    draw.line(
        (
            width - margin - line_width,
            cfg["subhead_y"],
            width - margin,
            cfg["subhead_y"],
        ),
        fill=red,
        width=2,
    )
    draw.text(
        (width / 2, cfg["subhead_y"]),
        subhead,
        font=subhead_font,
        fill=charcoal,
        anchor="mm",
    )

    cols = cfg["cols"]
    rows = max(1, (len(cards) + cols - 1) // cols)
    gap = 14 if output_format != "landscape" else 10
    grid_bottom = cfg["footer_top"] - 14
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

        _shadow_card(canvas, box, 15 if output_format != "landscape" else 11)

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

    footer_top = cfg["footer_top"]
    footer_height = height - footer_top
    draw.rectangle((0, footer_top, width, height), fill=navy)

    cta_width = 335 if output_format != "landscape" else 285
    draw.polygon(
        [
            (width - cta_width - 48, footer_top),
            (width, footer_top),
            (width, height),
            (width - cta_width, height),
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

    usable_width = width - cta_width - 70
    step = usable_width / len(professions)
    badge_font = _font(9 if output_format != "landscape" else 7, True)
    label_font = _font(11 if output_format != "landscape" else 8, True)

    for index, (badge, label) in enumerate(professions):
        center_x = 24 + step * index + step / 2
        badge_y = footer_top + footer_height * 0.34
        radius = 15 if output_format != "landscape" else 10

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
            (center_x, footer_top + footer_height * 0.72),
            label,
            font=label_font,
            fill=white,
            anchor="mm",
        )

        if index < len(professions) - 1:
            separator_x = 24 + step * (index + 1)
            draw.line(
                (
                    separator_x,
                    footer_top + 14,
                    separator_x,
                    height - 14,
                ),
                fill=red,
                width=2,
            )

    cta_x = width - cta_width / 2
    cta_font = _fit(
        draw,
        "FIND YOUR NEXT",
        cta_width - 48,
        24 if output_format != "landscape" else 16,
        True,
        12,
    )
    draw.text(
        (cta_x, footer_top + footer_height * 0.38),
        "FIND YOUR NEXT",
        font=cta_font,
        fill=white,
        anchor="mm",
    )
    draw.text(
        (cta_x, footer_top + footer_height * 0.67),
        "CAREER MOVE.",
        font=cta_font,
        fill=white,
        anchor="mm",
    )

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _single_canvas(output_format):
    sizes = {
        "square": (1080, 1080),
        "portrait": (1080, 1350),
        "landscape": (1200, 630),
    }
    return sizes.get(output_format, sizes["square"])


def _draw_single_footer(draw, width, height, footer_top, navy, red, white):
    draw.rectangle((0, footer_top, width, height), fill=navy)

    cta_font = _fit(
        draw,
        "VIEW CURRENT OPPORTUNITIES",
        width - 100,
        28 if width <= 1080 else 22,
        True,
        16,
    )
    draw.text(
        (width / 2, footer_top + (height - footer_top) * 0.35),
        "VIEW CURRENT OPPORTUNITIES",
        font=cta_font,
        fill=white,
        anchor="mm",
    )

    site_font = _fit(
        draw,
        "PHYSIOTHERAPYJOBSCANADA.CA",
        width - 100,
        34 if width <= 1080 else 24,
        True,
        17,
    )
    draw.text(
        (width / 2, footer_top + (height - footer_top) * 0.72),
        "PHYSIOTHERAPYJOBSCANADA.CA",
        font=site_font,
        fill=white,
        anchor="mm",
    )


def render_single_graphic(
    card: EmployerCard,
    output_format: str = "square",
    style: str = "classic",
) -> bytes:
    width, height = _single_canvas(output_format)

    navy = "#061E35"
    red = "#C9162B"
    white = "#FFFFFF"
    charcoal = "#182638"
    background = "#F8F7F4"

    canvas = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(canvas)

    for offset in range(-height, width, 44):
        draw.line((offset, 0, offset + height, height), fill="#EEECE8", width=1)

    logo = _open_logo(card.logo)
    location = card.location or "Canada"
    jobs_text = f"{card.active_jobs} ACTIVE JOBS" if card.active_jobs != 1 else "1 ACTIVE JOB"

    landscape = output_format == "landscape"
    portrait = output_format == "portrait"

    if landscape:
        footer_top = 525
    else:
        footer_top = 1110 if portrait else 895

    if style == "spotlight":
        draw.rectangle((0, 0, width, int(height * 0.28)), fill=red)
        headline_font = _fit(draw, "NOW HIRING", width - 100, 74 if not landscape else 52, True, 34)
        draw.text(
            (width / 2, 45 if not landscape else 26),
            "NOW HIRING",
            font=headline_font,
            fill=white,
            anchor="ma",
        )

        logo_box = (
            110,
            330 if portrait else 255,
            width - 110,
            850 if portrait else 700,
        ) if not landscape else (70, 150, 545, 470)

        _shadow_card(canvas, logo_box, 28 if not landscape else 20)
        if logo:
            x1, y1, x2, y2 = logo_box
            fitted = ImageOps.contain(
                logo,
                (x2 - x1 - 100, y2 - y1 - 90),
                Image.Resampling.LANCZOS,
            )
            canvas.paste(
                fitted,
                (
                    x1 + (x2 - x1 - fitted.width) // 2,
                    y1 + (y2 - y1 - fitted.height) // 2,
                ),
                fitted,
            )

        if landscape:
            name_x, name_y = 620, 185
            name_anchor = "la"
            name_width = width - 675
        else:
            name_x, name_y = width / 2, 205
            name_anchor = "ma"
            name_width = width - 120

    elif style == "location":
        headline_font = _fit(draw, "OPPORTUNITIES IN", width - 100, 55 if not landscape else 38, True, 28)
        draw.text(
            (width / 2, 55 if not landscape else 25),
            "OPPORTUNITIES IN",
            font=headline_font,
            fill=navy,
            anchor="ma",
        )
        location_font = _fit(draw, location.upper(), width - 100, 72 if not landscape else 48, True, 32)
        draw.text(
            (width / 2, 125 if not landscape else 72),
            location.upper(),
            font=location_font,
            fill=red,
            anchor="ma",
        )

        logo_box = (
            110,
            295 if portrait else 235,
            width - 110,
            840 if portrait else 720,
        ) if not landscape else (75, 150, 545, 470)

        _shadow_card(canvas, logo_box, 28 if not landscape else 20)
        if logo:
            x1, y1, x2, y2 = logo_box
            fitted = ImageOps.contain(
                logo,
                (x2 - x1 - 100, y2 - y1 - 90),
                Image.Resampling.LANCZOS,
            )
            canvas.paste(
                fitted,
                (
                    x1 + (x2 - x1 - fitted.width) // 2,
                    y1 + (y2 - y1 - fitted.height) // 2,
                ),
                fitted,
            )

        if landscape:
            name_x, name_y = 620, 185
            name_anchor = "la"
            name_width = width - 675
        else:
            name_x, name_y = width / 2, 860 if portrait else 755
            name_anchor = "ma"
            name_width = width - 120

    elif style == "minimal":
        headline_font = _fit(draw, "WE'RE HIRING", width - 100, 64 if not landscape else 44, True, 30)
        draw.text(
            (width / 2, 65 if not landscape else 28),
            "WE'RE HIRING",
            font=headline_font,
            fill=navy,
            anchor="ma",
        )
        draw.line((100, 155 if not landscape else 92, width - 100, 155 if not landscape else 92), fill=red, width=4)

        logo_box = (
            145,
            245 if portrait else 210,
            width - 145,
            820 if portrait else 700,
        ) if not landscape else (75, 135, 545, 465)

        if logo:
            x1, y1, x2, y2 = logo_box
            fitted = ImageOps.contain(
                logo,
                (x2 - x1, y2 - y1),
                Image.Resampling.LANCZOS,
            )
            canvas.paste(
                fitted,
                (
                    x1 + (x2 - x1 - fitted.width) // 2,
                    y1 + (y2 - y1 - fitted.height) // 2,
                ),
                fitted,
            )

        if landscape:
            name_x, name_y = 620, 190
            name_anchor = "la"
            name_width = width - 675
        else:
            name_x, name_y = width / 2, 845 if portrait else 735
            name_anchor = "ma"
            name_width = width - 120

    else:
        headline_font = _fit(draw, "NOW HIRING", width - 100, 76 if not landscape else 54, True, 34)
        draw.text(
            (width / 2 if not landscape else 845, 72 if not landscape else 40),
            "NOW HIRING",
            font=headline_font,
            fill=red,
            anchor="ma",
        )

        logo_box = (
            105,
            285 if portrait else 250,
            width - 105,
            850 if portrait else 740,
        ) if not landscape else (65, 145, 560, 475)

        _shadow_card(canvas, logo_box, 28 if not landscape else 20)
        if logo:
            x1, y1, x2, y2 = logo_box
            fitted = ImageOps.contain(
                logo,
                (x2 - x1 - 110, y2 - y1 - 100),
                Image.Resampling.LANCZOS,
            )
            canvas.paste(
                fitted,
                (
                    x1 + (x2 - x1 - fitted.width) // 2,
                    y1 + (y2 - y1 - fitted.height) // 2,
                ),
                fitted,
            )

        if landscape:
            name_x, name_y = 620, 180
            name_anchor = "la"
            name_width = width - 675
        else:
            name_x, name_y = width / 2, 165 if portrait else 150
            name_anchor = "ma"
            name_width = width - 120

    name_font = _fit(draw, card.name.upper(), name_width, 50 if not landscape else 44, True, 24)
    draw.text(
        (name_x, name_y),
        card.name.upper(),
        font=name_font,
        fill=navy,
        anchor=name_anchor,
    )

    if landscape:
        detail_x = 620
        detail_anchor = "la"
        detail_y = 285
    else:
        detail_x = width / 2
        detail_anchor = "ma"
        detail_y = 930 if portrait else 805

    if style != "location":
        location_font = _fit(draw, location, width - 130, 25 if not landscape else 22, False, 16)
        draw.text(
            (detail_x, detail_y),
            location,
            font=location_font,
            fill=charcoal,
            anchor=detail_anchor,
        )

    jobs_font = _fit(draw, jobs_text, width - 130, 28 if not landscape else 24, True, 18)
    draw.text(
        (detail_x, detail_y + 52),
        jobs_text,
        font=jobs_font,
        fill=red,
        anchor=detail_anchor,
    )

    _draw_single_footer(draw, width, height, footer_top, navy, red, white)

    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()
