"""Render and label selected pages for the public preview gallery."""
from pathlib import Path
from subprocess import run
from tempfile import TemporaryDirectory
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
DEST=ROOT.parents[1]/'static/career_mobility/product-previews'
FONT=ROOT.parents[1]/'ptjc_resumes/assets/DejaVuSans-Bold.ttf'
PAGES={
    'exercise-tracker': ((1,'Weekly exercise log'),),
    'appointment-notes': ((1,'Questions to bring'),(2,'Notes and next steps')),
    'practice-planner-2027': ((1,'Clickable index'),(2,'Monthly calendar'),(14,'Weekly priorities'),(16,'Learning and renewal')),
}

def generate(slug, pages):
    cols=min(len(pages),2)
    out=Image.new('RGB',(cols*440,((len(pages)+cols-1)//cols)*530),'#e5ede8')
    font=ImageFont.truetype(str(FONT),19)
    for index,(page,label) in enumerate(pages):
        with TemporaryDirectory() as tmp:
            preview=Path(tmp)/'page'
            run(['pdftoppm','-f',str(page),'-l',str(page),'-scale-to','470','-png','-singlefile',str(ROOT/f'{slug}.pdf'),str(preview)],check=True)
            src=Image.open(preview.with_suffix('.png')).convert('RGB')
        x=(index%cols)*440;y=(index//cols)*530
        out.paste(src,(x+(440-src.width)//2,y+10))
        d=ImageDraw.Draw(out)
        d.text((x+220,y+499),label,font=font,fill='#132c3c',anchor='mt')
        # Label the samples without exposing the fillable download.
        d.text((x+220,y+462),'PTJC PREVIEW',font=font,fill='#285854',anchor='mt')
    out.save(DEST/f'{slug}-inside.png',optimize=True)

if __name__=='__main__':
    for slug,pages in PAGES.items():
        generate(slug,pages)
