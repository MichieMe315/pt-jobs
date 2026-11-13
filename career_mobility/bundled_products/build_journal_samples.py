"""Render public sample images from the same default worksheet content as the editor."""
from pathlib import Path
from tempfile import TemporaryDirectory
from subprocess import run
from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from ptjc_resumes.pdf import fonts
from career_mobility.journal_content import worksheets
from career_mobility.journal_editions import EDITIONS
from html import escape

ROOT=Path(__file__).resolve().parent
DEST=ROOT.parents[1]/'static/career_mobility/product-previews/journals'
INK=HexColor('#242629')
ACCENT=HexColor('#76415d')

def sample(track):
    fonts()
    stream=BytesIO()
    c=Canvas(stream,pagesize=(612,792))
    def text(value,x,y,width,size=10,font='PTJCResume',colour=INK,leading=None):
        style=ParagraphStyle('sample',fontName=font,fontSize=size,leading=leading or size*1.45,textColor=colour)
        p=Paragraph(escape(value).replace('\n','<br/>'),style)
        _,h=p.wrap(width,760)
        p.drawOn(c,x,y-h)
        return h
    def footer(number):
        c.setStrokeColor(HexColor('#d8d6d4'));c.setLineWidth(.5);c.line(36,43,576,43)
        text('PTJC · physiotherapyjobscanada.ca',36,32,400,7,colour=HexColor('#737373'))
        text(f'{number:02}',558,32,25,7)
        c.saveState();c.setFillAlpha(.07);c.translate(306,396);c.rotate(28);c.setFont('PTJCResume',25);c.drawCentredString(0,0,'PTJC SAMPLE');c.restoreState()
    c.setFillColor(HexColor('#fbfaf7'));c.rect(0,0,612,792,fill=1,stroke=0)
    c.setFillColor(ACCENT);c.rect(0,72,16,650,fill=1,stroke=0)
    text('PTJC · PROFESSIONAL RESOURCES',36,756,430,9,font='PTJCResumeBold')
    text('PROFESSIONAL PRACTICE JOURNAL',52,658,500,8,font='PTJCResumeBold',colour=ACCENT)
    title=EDITIONS[track][0]+' Journal'
    h=text(title,52,604,485,38,font='PTJCResumeSerif',leading=43)
    c.setStrokeColor(ACCENT);c.setLineWidth(1.5);c.line(52,572-h,118,572-h)
    text('Visit preparation, participation goals and professional learning.',52,540-h,350,12,colour=HexColor('#555555'))
    text('Prepared by',52,180,400,11)
    footer(1);c.showPage()
    for i,sheet in enumerate(worksheets(track)):
        text('PTJC · PROFESSIONAL RESOURCES',36,755,500,9,font='PTJCResumeBold')
        c.setStrokeColor(HexColor('#d8d6d4'));c.line(36,722,576,722)
        text(f'WORKSHEET {i+1:02}',36,702,500,8,font='PTJCResumeBold',colour=ACCENT)
        h=text(sheet['title'],36,682,530,27,font='PTJCResumeSerif',leading=32)
        h2=text(sheet['intro'],36,672-h,525,9,colour=HexColor('#606060'))
        y=650-h-h2
        text('Date / week: ____________________        Reference / topic: ____________________',36,y,540,8)
        y-=32
        for j,field in enumerate(sheet['fields']):
            c.setStrokeColor(HexColor('#cfcac6'));c.setLineWidth(.5);c.line(36,y,576,y)
            text(f'{j+1:02}',36,y-9,24,8,font='PTJCResumeBold',colour=ACCENT)
            text(field['label'],61,y-8,515,10,font='PTJCResumeBold')
            ph=text(field['prompt'],36,y-28,540,8.5,colour=HexColor('#626262'))
            bottom=y-30-ph
            c.setStrokeColor(HexColor('#e5e0dc'))
            for line in range(3):c.line(36,bottom-17-line*17,576,bottom-17-line*17)
            y=bottom-70
        assert y>48,(track,sheet['title'],y)
        footer(i+2);c.showPage()
    c.save()
    return stream.getvalue()

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory() as tmp:
        pdf=Path(tmp)/'sample.pdf'
        for track in EDITIONS:
            key=track+'-physio-journal'
            folder=DEST/key;folder.mkdir(exist_ok=True)
            pdf.write_bytes(sample(track))
            for page,name in ((1,'cover'),(2,'worksheet'),(3,'review')):
                run(['pdftoppm','-f',str(page),'-l',str(page),'-r','100','-singlefile','-jpeg','-jpegopt','quality=88',str(pdf),str(folder/name)],check=True)

if __name__=='__main__':
    main()
