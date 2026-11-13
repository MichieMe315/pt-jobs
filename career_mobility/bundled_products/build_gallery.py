"""Render separate, labelled public samples of the actual print files."""
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
DEST = ROOT.parents[1] / 'static/career_mobility/product-previews/pages'
FONT = ROOT.parents[1] / 'ptjc_resumes/assets/DejaVuSans.ttf'
PAGES = {
    'exercise-tracker': (1,),
    'appointment-notes': (1, 2),
    'practice-planner-2027': (1, 2, 14, 16),
    'paediatric-physio-journal': (1, 2, 3, 6),
    'physio-wall-calendar-2027': (1, 5, 9),
}

def render():
    DEST.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as tmp:
        preview = Path(tmp) / 'page'
        for slug, pages in PAGES.items():
            for page in pages:
                run(['pdftoppm','-f',str(page),'-l',str(page),'-scale-to','1050','-png','-singlefile',str(ROOT/f'{slug}.pdf'),str(preview)],check=True)
                with Image.open(preview.with_suffix('.png')) as src:
                    sheet = src.convert('RGBA')
                watermark = Image.new('RGBA',sheet.size)
                draw = ImageDraw.Draw(watermark)
                draw.text((sheet.width/2,sheet.height*.49),'PTJC SAMPLE',font=ImageFont.truetype(str(FONT),68),fill=(25,42,60,36),anchor='mm')
                watermark = watermark.rotate(28, resample=Image.Resampling.BICUBIC)
                Image.alpha_composite(sheet,watermark).convert('RGB').save(DEST/f'{slug}-{page}.jpg',quality=87,optimize=True)

if __name__ == '__main__':
    render()
