"""Build catalogue covers from the products' actual pages."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DEST = ROOT.parents[1] / 'static/career_mobility/product-previews'
FONTS = ROOT.parents[1] / 'ptjc_resumes/assets'
ITEMS = {
    'exercise-tracker': ('Patient worksheet', ('My Physio', 'Exercise Tracker'), ('Four exercises', 'Seven-day log', 'Weekly notes'), '#efe9e2'),
    'appointment-notes': ('Patient worksheet', ('Questions for', 'My Physio'), ('Visit prompts', 'Your questions', 'Follow-up notes'), '#eceee7'),
    'practice-planner-2027': ('Professional planner', ('2027 Physio', 'Practice Planner'), ('12 dated months', 'Clickable index', 'Reusable logs'), '#e8eaf0'),
    'paediatric-physio-journal': ('Specialty journal', ('Paediatric', 'Physio Journal'), ('Practice reflections', 'Session notes', 'Professional learning'), '#efe6e2'),
    'physio-wall-calendar-2027': ('Photo calendar', ('2027 Physio', 'Wall Calendar'), ('January–December', 'Personalize your photos', 'Print or use digitally'), '#eeebe4'),
}


def font(name, size):
    return ImageFont.truetype(str(FONTS / ('DejaVu' + name + '.ttf')), size)


def cover(slug, spec):
    kind, _, _, background = spec
    pages = {
        'exercise-tracker': (1,),
        'appointment-notes': (1, 2),
        'practice-planner-2027': (1, 2, 14),
        'paediatric-physio-journal': (1, 2),
        'physio-wall-calendar-2027': (5,),
    }[slug]
    samples = DEST / 'pages'
    sheets = []
    for page in pages:
        sample = samples / f'{slug}-{page}.jpg'
        with Image.open(sample) as src:
            sheets.append(src.convert('RGB'))
    image = Image.new('RGB', (900, 600), background)
    d = ImageDraw.Draw(image)
    d.line((38, 43, 862, 43), fill='#a49a8f', width=1)
    d.text((38, 23), kind.upper(), font=font('Sans-Bold', 13), fill='#54483e')
    d.text((862, 23), 'PTJC', font=font('Sans-Bold', 13), fill='#54483e', anchor='ra')
    if len(sheets) == 1:
        coords = [(450, 524, 56)]
    elif len(sheets) == 2:
        coords = [(276, 492, 70), (626, 492, 70)]
    else:
        coords = [(190, 414, 108), (450, 502, 57), (710, 414, 108)]
    for i in sorted(range(len(sheets)), key=lambda i: coords[i][1]):
        sheet = sheets[i]
        center, height, y = coords[i]
        sheet.thumbnail((390, height), Image.Resampling.LANCZOS)
        x = center - sheet.width // 2
        d.rectangle((x+6, y+7, x+sheet.width+6, y+sheet.height+7), fill='#cfc9c2')
        image.paste(sheet, (x, y))
    image.save(DEST/f'{slug}.png', optimize=True)


if __name__=='__main__':
    for slug,spec in ITEMS.items():
        cover(slug,spec)
