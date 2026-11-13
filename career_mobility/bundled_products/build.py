"""Generate the original PTJC printable collection. Run from the Django root."""
from calendar import Calendar, month_name
import os
from pathlib import Path
from reportlab.lib.colors import HexColor as _HexColor, Color
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).parent
THEME = os.environ.get('PTJC_PRINT_THEME', '')
PLUM = {'#132c3c':'#3a2735', '#116662':'#76415d', '#dff1e9':'#f3e2e9',
        '#fbfaf5':'#fffbf8', '#eedab5':'#ecddc8', '#e6efe4':'#f3e6ec',
        '#c9ded4':'#dec3d2', '#d9e9de':'#eddae5', '#a1b9b0':'#bca4b1',
        '#edf2ec':'#f8eef2', '#f1f1eb':'#f8f0ea', '#b7c8bf':'#cdb8c3'}


def HexColor(value):
    original = _HexColor(PLUM.get(value, value) if THEME == 'plum' else value)
    if THEME == 'grayscale':
        shade = .2126 * original.red + .7152 * original.green + .0722 * original.blue
        return Color(shade, shade, shade)
    return original


def output(stem):
    return str(ROOT / (stem + (f'-{THEME}' if THEME else '') + '.pdf'))


INK, TEAL, MINT, PAPER, GOLD = map(HexColor, ('#132c3c','#116662','#dff1e9','#fbfaf5','#eedab5'))
W, H = 612, 792
M = 40
FONT_DIR = ROOT.parents[1] / 'ptjc_resumes/assets'
pdfmetrics.registerFont(TTFont('PTJCPrint', str(FONT_DIR/'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('PTJCPrintBold', str(FONT_DIR/'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFont(TTFont('PTJCPrintSerif', str(FONT_DIR/'DejaVuSerif.ttf')))


def label(c, s, x, y, size=11, colour=INK, font='Helvetica'):
    font = {'Helvetica':'PTJCPrint', 'Times-Bold':'PTJCPrintSerif'}.get(font,'PTJCPrintBold')
    available = W-M-x
    measure = pdfmetrics.stringWidth(s,font,size)
    if measure > available:
        size *= available/measure
    c.setFillColor(colour); c.setFont(font, size); c.drawString(x, y, s)


def box(c, x, y, w, h, colour):
    c.setFillColor(colour); c.rect(x, y, w, h, fill=1, stroke=0)


def page(c, series, title, subtitle):
    c.setFillColor(PAPER); c.rect(0,0,W,H,fill=1,stroke=0)
    label(c, series.upper(), M, 738, 9, TEAL, 'Helvetica-Bold')
    label(c, title, M, 699, 31, INK, 'Times-Bold')
    label(c, subtitle, M, 672, 10, INK)
    c.setStrokeColor(TEAL)
    c.setLineWidth(.55)
    c.line(M, 650, W-M, 650)
    c.setStrokeColor(TEAL); c.line(M, 47, 572, 47)
    label(c, 'PTJC   /   PHYSIOTHERAPY JOBS CANADA', M, 30, 8, TEAL, 'Helvetica-Bold')
    label(c, f'{c.getPageNumber():02}', 556, 30, 9, TEAL)


def lines(c, x, y, w, n, step=21):
    c.setStrokeColor(HexColor('#a1b9b0'))
    for i in range(n): c.line(x, y-step*i, x+w, y-step*i)


def field(c, name, x, y, width, height=16, multiline=False):
    c.acroForm.textfield(name=name, tooltip=name.replace('_',' '), x=x, y=y, width=width, height=height,
                        borderWidth=0, borderColor=Color(0,0,0,alpha=0), fillColor=Color(1,1,1,alpha=0),
                        textColor=INK, fontSize=9, fieldFlags='multiline' if multiline else '',
                        maxlen=250 if multiline else 75)


def tick(c, name, x, y, size=12):
    c.acroForm.checkbox(name=name, tooltip=name.replace('_',' '), x=x, y=y, size=size,
                        borderColor=TEAL, borderWidth=.65, fillColor=PAPER, textColor=TEAL)


def sheet(c, title, prompts, y, height):
    box(c,M,y,532,height,MINT)
    label(c,title,M+15,y+height-23,14,TEAL,'Helvetica-Bold')
    for i, prompt in enumerate(prompts):
        label(c,prompt,M+15,y+height-44-18*i,10)
    return y+height-60-18*(len(prompts)-1)


def exercise():
    c=Canvas(output('exercise-tracker'),pagesize=(W,H))
    page(c,'Patient worksheet  /  01','My exercise tracker','A weekly record for exercises your physiotherapist has already prescribed.')
    label(c,'Week of:',M,613,11); lines(c,95,610,155,1); field(c,'Week_of',95,612,155)
    label(c,'Physiotherapist:',278,613,11); lines(c,365,610,200,1); field(c,'Physiotherapist',365,612,200)
    for i in range(4):
        x=M+(i%2)*271; y=443-(i//2)*147
        box(c,x,y,261,131,MINT)
        label(c,f'EXERCISE {i+1:02}',x+14,y+105,11,TEAL,'Helvetica-Bold')
        label(c,'Exercise:',x+14,y+83); lines(c,x+73,y+81,171,1); field(c,f'Exercise_{i+1}',x+73,y+83,171)
        label(c,'Prescribed reps / time:',x+14,y+61,10); lines(c,x+119,y+59,125,1); field(c,f'Exercise_{i+1}_reps_or_time',x+119,y+61,125)
        for j,day in enumerate(('M','T','W','T','F','S','S')):
            dx=x+17+j*32
            label(c,day,dx+2,y+38,9)
            tick(c,f'Exercise_{i+1}_{j+1}',dx,y+16)
    for j,(title,prompt) in enumerate((
        ('How I felt', 'Note how you felt before and after.'),
        ('For my next appointment', 'What felt easier, harder, or worth asking about?'),
    )):
        x=M+j*271
        box(c,x,127,261,144,HexColor('#f2e8d9') if j==0 else MINT)
        label(c,title,x+13,247,14,TEAL,'Helvetica-Bold')
        label(c,prompt,x+13,228,9,INK)
        lines(c,x+13,207,234,4,19);field(c,'Exercise_notes_'+str(j),x+13,144,234,73,True)
    label(c,'Bring this page to your next visit. Follow the plan your physiotherapist gave you.',M,101,10)
    c.showPage(); c.save()


def appointment():
    c=Canvas(output('appointment-notes'),pagesize=(W,H))
    page(c,'Patient worksheet  /  02','Questions for my physiotherapist','Pick the questions that matter to you and bring this sheet to your visit.')
    prompts=[
        ('Symptoms',('What might explain what I feel?','Which changes should I tell you about?')),
        ('Pain',('What should I do if symptoms change?','When should I contact the clinic?')),
        ('Exercises',('Which exercises are the priority?','How should I record what I do?')),
        ('Activity and recovery',('What should I consider before returning to activities?','What progress should we look for next time?')),
        ('Before I leave',('What should I do next?','When and how should I follow up?')),
    ]
    for i,(heading,items) in enumerate(prompts):
        y=531-i*87
        box(c,M,y,311,76,MINT if i%2==0 else HexColor('#edf2ec'))
        label(c,heading,M+13,y+54,12,TEAL,'Helvetica-Bold')
        for j,question in enumerate(items):
            tick(c,f'Question_{i+1}_{j+1}',M+13,y+31-j*16,9)
            label(c,question,M+28,y+33-j*16,8.5,INK)
    x=365
    for name,title,y in (('My_own_questions','My own questions',416),('What_to_remember','What I need to remember',218)):
        box(c,x,y,207,191,HexColor('#f2e8d9'))
        label(c,title,x+13,y+168,13,TEAL,'Helvetica-Bold')
        lines(c,x+13,y+146,181,7,19);field(c,name,x+13,y+19,181,139,True)
    label(c,'Next appointment',x+3,181,10,TEAL,'Helvetica-Bold')
    lines(c,x+3,153,201,1);field(c,'Next_appointment',x+3,155,201)
    label(c,'Bring this sheet to your appointment and write down your next steps.',M,103,10,INK)
    c.showPage()
    page(c,'Patient worksheet  /  02','My appointment notes','Record what you and your physiotherapist discussed so you can refer to it later.')
    for i,(heading,prompt) in enumerate((('What we discussed','What did I learn about my symptoms or goals?'),('What I agreed to do','What should I do, how often, and until when?'),('What to bring next time','What do I want to ask or report back?'))):
        y=sheet(c,heading,(prompt,),448-i*167,152); lines(c,M+15,y,502,4,19); field(c,f'Visit_notes_{i+1}',M+15,y-62,502,72,True)
    c.showPage(); c.save()


def planner():
    c=Canvas(output('practice-planner-2027'),pagesize=(W,H))
    page(c,'2027 professional collection','Physio Practice Planner','January to December 2027  /  Click a month or print the pages you use.')
    c.bookmarkPage('index')
    for i in range(12):
        x=M+(i%3)*181; y=541-(i//3)*78
        box(c,x,y,169,57,MINT if i%2==0 else GOLD)
        label(c,f'{i+1:02}   {month_name[i+1]}',x+13,y+22,14,INK,'Helvetica-Bold')
        c.linkRect('',f'month-{i+1}',(x,y,x+169,y+57),relative=0,thickness=0)
    for i,(name,key) in enumerate((('Weekly priorities','weekly'),('Hours and shifts','hours'),('Learning and renewal','learning'))):
        y=260-i*44; label(c,name,M,y,13,TEAL,'Helvetica-Bold')
        c.linkRect('',key,(M,y-6,240,y+17),relative=0,thickness=0)
    label(c,'For professional planning. Keep patient identifiers and clinical records elsewhere.',M,81,10)
    c.showPage()
    for month in range(1,13):
        c.bookmarkPage(f'month-{month}')
        page(c,'Monthly planner',f'{month_name[month]} 2027','Appointments, working hours, professional goals and dates to remember.')
        for tab in range(1,13):
            y=612-(tab-1)*34
            colour=TEAL if tab==month else HexColor('#d9e9de')
            box(c,575,y,34,26,colour)
            c.setFillColor(PAPER if tab==month else INK);c.setFont('PTJCPrintBold',6.5)
            c.drawCentredString(592,y+10,month_name[tab][:3].upper())
            c.linkRect('',f'month-{tab}',(575,y,609,y+26),relative=0,thickness=0)
        for j, day in enumerate(('MON','TUE','WED','THU','FRI','SAT','SUN')):
            label(c,day,M+9+j*76,613,9,TEAL,'Helvetica-Bold')
        for i, week in enumerate(Calendar().monthdayscalendar(2027,month)):
            for j,day in enumerate(week):
                x=M+j*76; y=537-i*59
                box(c,x,y,72,54,MINT if day else PAPER)
                if day:
                    label(c,str(day),x+8,y+36,10,TEAL,'Helvetica-Bold')
                    field(c,f'Month_{month}_day_{day}',x+5,y+4,62,27,True)
        y=sheet(c,'This month’s priorities',('Key deadlines, schedule changes or learning goals.',),83,145)
        lines(c,M+15,y,502,4,18); field(c,f'Month_{month}_priorities',M+15,y-60,502,69,True)
        label(c,'Back to months',M,61,9,TEAL); c.linkRect('','index',(M,57,M+90,73),relative=0,thickness=0)
        c.showPage()
    for key,title,cols in (
        ('weekly','Weekly priorities',('Day','Schedule','Priority / follow-up')),
        ('hours','Hours and shifts',('Date','Clinic / setting','Hours','Notes')),
        ('learning','Learning and renewal',('Activity or renewal','Provider','Date / due','Hours / evidence')),
    ):
        c.bookmarkPage(key)
        page(c,'Reusable planning sheet',title,'Print another copy when needed. Keep identifying patient information out of this planner.')
        for j,name in enumerate(cols):
            label(c,name,M+9+j*532/len(cols),605,10,TEAL,'Helvetica-Bold')
        for i in range(12):
            y=552-i*39; box(c,M,y,532,35,MINT if i%2==0 else HexColor('#f1f1eb'))
            c.setStrokeColor(HexColor('#b7c8bf'))
            for j in range(1,len(cols)): c.line(M+j*532/len(cols),y+3,M+j*532/len(cols),y+32)
            for j in range(len(cols)):
                cell=532/len(cols)
                field(c,f'{key}_{i+1}_{j+1}',M+6+j*cell,y+5,cell-12,24)
        label(c,'Back to months',M,61,9,TEAL); c.linkRect('','index',(M,57,M+90,73),relative=0,thickness=0)
        c.showPage()
    c.save()


if __name__=='__main__':
    exercise(); appointment(); planner()
