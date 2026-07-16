
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
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
    a, b = HEADLINES.get(key, HEADLINES["top_real"])
    return f"{a} {b}"


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


def _font(size: int, bold: bool = False):
    names = (
        ["DejaVuSansCondensed-Bold.ttf", "DejaVuSans-Bold.ttf", "arialbd.ttf"]
        if bold else
        ["DejaVuSans.ttf", "arial.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


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
    sd.rounded_rectangle((x1, y1 + 5, x2, y2 + 5), radius=radius, fill=(0, 0, 0, 38))
    shadow = shadow.filter(ImageFilter.GaussianBlur(9))
    canvas.paste(shadow, (0, 0), shadow)
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=radius, fill="#FFFFFF")


def _config(fmt):
    if fmt == "portrait":
        return dict(size=(1080, 1350), margin=54, header=350, footer=220, cols=4, gap=14)
    if fmt == "landscape":
        return dict(size=(1200, 630), margin=38, header=170, footer=112, cols=6, gap=10)
    return dict(size=(1080, 1080), margin=54, header=305, footer=190, cols=4, gap=13)


def _resolve_call(args, kwargs):
    """
    Supports both deployed signatures:
      old: render_graphic(cards, title, subtitle, output_format)
      new: render_graphic(cards=..., headline_key=..., headline=..., region=..., output_format=...)
    """
    cards = kwargs.get("cards")
    if cards is None and args:
        cards = args[0]

    output_format = kwargs.get("output_format")
    if not output_format:
        output_format = args[3] if len(args) >= 4 else "square"

    headline_key = kwargs.get("headline_key", "top_real")
    region = kwargs.get("region", "Canada")

    # Infer region from old title if possible.
    if len(args) >= 2 and isinstance(args[1], str):
        old_title = args[1]
        lower = old_title.lower()
        if "hiring in " in lower:
            region = old_title[lower.index("hiring in ") + 10:].strip()
        elif "canada" in lower:
            region = "Canada"

    return list(cards or []), headline_key, region, output_format


def render_graphic(*args, **kwargs) -> bytes:
    cards, headline_key, region, output_format = _resolve_call(args, kwargs)
    cfg = _config(output_format)
    width, height = cfg["size"]
    margin = cfg["margin"]

    NAVY = "#071D33"
    RED = "#C4162A"
    WHITE = "#FFFFFF"
    TEXT = "#172433"
    BG = "#F6F5F2"

    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)

    # Fine diagonal texture.
    for offset in range(-height, width, 28):
        draw.line((offset, 0, offset + height, height), fill="#ECEAE6", width=1)

    # Brand plaque.
    brand = _brand()
    if brand:
        if output_format == "landscape":
            target = (270, 72)
            top = 8
        else:
            target = (330, 104)
            top = 14
        b = ImageOps.contain(brand, target, Image.Resampling.LANCZOS)
        canvas.paste(b, ((width - b.width) // 2, top))

    first, second = HEADLINES.get(headline_key, HEADLINES["top_real"])

    if output_format == "landscape":
        y1, gap, start = 67, 47, 52
    else:
        y1, gap, start = 125, 73, 78

    f1 = _fit(draw, first, width - 2 * margin, start, True, 30)
    f2 = _fit(draw, second, width - 2 * margin, start, True, 30)
    draw.text((width / 2, y1), first, font=f1, fill=NAVY, anchor="ma")
    draw.text((width / 2, y1 + gap), second, font=f2, fill=RED, anchor="ma")

    # Count band.
    count_y = cfg["header"] - (25 if output_format == "landscape" else 38)
    side = 110 if output_format != "landscape" else 72
    draw.line((margin, count_y, margin + side, count_y), fill=RED, width=2)
    draw.line((width - margin - side, count_y, width - margin, count_y), fill=RED, width=2)

    region_label = (region or "Canada").upper()
    count_text = f"{len(cards)} EMPLOYERS  CURRENTLY HIRING IN {region_label}"
    cf = _fit(draw, count_text, width - 2 * margin - 2 * side - 26,
              22 if output_format != "landscape" else 14, True, 11)
    draw.text((width / 2, count_y), count_text, font=cf, fill=TEXT, anchor="mm")

    # Grid.
    footer_top = height - cfg["footer"]
    grid_top = cfg["header"]
    grid_bottom = footer_top - 12
    cols = min(cfg["cols"], max(1, len(cards)))
    rows = max(1, (len(cards) + cols - 1) // cols)
    gap_px = cfg["gap"]
    card_w = int((width - 2 * margin - gap_px * (cols - 1)) / cols)
    card_h = int((grid_bottom - grid_top - gap_px * (rows - 1)) / rows)

    # Avoid ugly single card stuck at left: center incomplete final rows.
    for idx, card in enumerate(cards):
        row = idx // cols
        col = idx % cols
        row_start = row * cols
        row_count = min(cols, len(cards) - row_start)
        row_width = row_count * card_w + (row_count - 1) * gap_px
        row_x = (width - row_width) / 2

        x = int(row_x + col * (card_w + gap_px))
        y = int(grid_top + row * (card_h + gap_px))
        box = (x, y, x + card_w, y + card_h)
        _shadow_card(canvas, box, 16 if output_format != "landscape" else 12)

        logo = _open_logo(card.logo)
        if logo:
            max_w = card_w - (34 if output_format != "landscape" else 24)
            max_h = card_h - (26 if output_format != "landscape" else 18)
            fitted = ImageOps.contain(logo, (max_w, max_h), Image.Resampling.LANCZOS)
            px = x + (card_w - fitted.width) // 2
            py = y + (card_h - fitted.height) // 2
            canvas.paste(fitted, (px, py), fitted)

    # Footer.
    draw.rectangle((0, footer_top, width, height), fill=NAVY)
    top_band = 105 if output_format != "landscape" else 62
    cta_w = 330 if output_format != "landscape" else 275

    draw.polygon([
        (width - cta_w - 48, footer_top),
        (width, footer_top),
        (width, footer_top + top_band),
        (width - cta_w, footer_top + top_band),
    ], fill=RED)

    labels = ["PHYSIOTHERAPY", "OT", "RMT", "OT", "CHIROPRACTIC", "KINESIOLOGY"]
    usable = width - cta_w - 70
    step = usable / len(labels)
    lf = _font(15 if output_format != "landscape" else 10, True)

    for i, label in enumerate(labels):
        cx = 24 + step * i + step / 2
        # small badge above label
        badge_r = 18 if output_format != "landscape" else 11
        badge_y = footer_top + 33 if output_format != "landscape" else footer_top + 20
        draw.ellipse((cx-badge_r, badge_y-badge_r, cx+badge_r, badge_y+badge_r),
                     outline=WHITE, width=2)
        initials = {"PHYSIOTHERAPY":"PT", "CHIROPRACTIC":"DC", "KINESIOLOGY":"KIN"}.get(label, label)
        bif = _fit(draw, initials, badge_r*1.5, 12 if output_format != "landscape" else 8, True, 7)
        draw.text((cx, badge_y), initials, font=bif, fill=WHITE, anchor="mm")
        draw.text((cx, footer_top + top_band - 22), label, font=lf, fill=WHITE, anchor="mm")
        if i < len(labels) - 1:
            sx = 24 + step * (i + 1)
            draw.line((sx, footer_top + 18, sx, footer_top + top_band - 18), fill=RED, width=2)

    cta_font = _fit(draw, "FIND YOUR NEXT", cta_w - 50,
                    25 if output_format != "landscape" else 16, True, 13)
    cta_x = width - cta_w / 2
    draw.text((cta_x, footer_top + top_band/2 - 14), "FIND YOUR NEXT",
              font=cta_font, fill=WHITE, anchor="mm")
    draw.text((cta_x, footer_top + top_band/2 + 17), "CAREER MOVE.",
              font=cta_font, fill=WHITE, anchor="mm")
    draw.line((cta_x - 90, footer_top + top_band - 17,
               cta_x + 90, footer_top + top_band - 17), fill=WHITE, width=3)

    website_top = footer_top + top_band
    draw.line((0, website_top, width, website_top), fill="#31465A", width=2)
    site = "PHYSIOTHERAPYJOBSCANADA.CA"
    sf = _fit(draw, site, width - 2 * margin,
              28 if output_format != "landscape" else 18, True, 14)
    draw.text((width/2, website_top + (height - website_top)/2),
              site, font=sf, fill=WHITE, anchor="mm")

    out = BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()
