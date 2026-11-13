"""Build the fillable paediatric journal and photo wall calendar."""
from calendar import Calendar, SUNDAY, month_name
from pathlib import Path
from reportlab.lib.colors import HexColor, white
from reportlab.pdfgen.canvas import Canvas

from build import ROOT, W, H, M, label, box, field, lines

NAVY, PEACH, RED, BLUE, GREEN, GOLD, PALE = map(HexColor, (
    '#193446','#fde2da','#ae4946','#dbeff7','#e0f2dc','#faedbb','#fffaf4',
))
PALETTES = (HexColor('#f4eae3'), HexColor('#f7f3ed'), HexColor('#f4eae3'), HexColor('#f7f3ed'))
PHOTOS = ROOT / 'calendar_photos'


def base(c):
    c.setFillColor(PALE)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setStrokeColor(RED)
    c.line(M, 40, W-M, 40)
    label(c, 'PTJC  /  PAEDIATRIC PHYSIOTHERAPY', M, 24, 8, RED, 'Helvetica-Bold')
    label(c, str(c.getPageNumber()), W-M-18, 24, 8, RED)


def journal_block(c, key, title, prompt, y, colour):
    h = 113
    box(c, M, y, W-2*M, h, colour)
    label(c, title, M+15, y+h-24, 15, NAVY, 'Helvetica-Bold')
    label(c, prompt, M+15, y+h-43, 9.5, NAVY)
    lines(c, M+15, y+51, W-2*M-30, 3, 16)
    field(c, key, M+15, y+9, W-2*M-30, 48, True)


JOURNAL = [
    ('Goals and participation', (
        ('What matters to the family?', 'Which activities at home, school or play are the priority?'),
        ('What can the child do now?', 'Describe the starting point and the context that makes it easier or harder.'),
        ('One goal to revisit', 'Name the activity, setting and what progress would look like.'),
        ('How will we review it?', 'Record the agreed measure, review date or question to bring to the team.'))),
    ('Plan a visit', (
        ('Focus for this visit', 'Choose one goal or skill to explore in the session.'),
        ('Activities and adaptations', 'Plan play, equipment and setup; note how to make the activity easier or harder.'),
        ('What will I observe?', 'Consider participation, assistance, comfort and how the activity is managed.'),
        ('Debrief and next step', 'What worked, what would I change and what will we revisit?'))),
    ('Build a play activity bank', (
        ('Balance and mobility', 'List play activities and settings to draw from when planning.'),
        ('Strength and movement', 'Note activity ideas, available equipment and possible adaptations.'),
        ('Participation and motivation', 'Record interests, ways to offer choice, and ideas for including siblings or peers.'),
        ('Ideas to try next', 'Leave room for activity variations or questions for colleagues.'))),
    ('Family and school collaboration', (
        ('Share the goal in plain language', 'Describe the activity and why it matters in the child’s usual routine.'),
        ('Make the plan practical', 'Identify time, space, equipment and access considerations.'),
        ('Questions for the care team', 'What information or input would make the plan easier to use?'),
        ('Follow-up', 'Note the next conversation, agreed responsibilities and timing.'))),
    ('Reflect on practice', (
        ('What went well?', 'Identify one decision, approach or collaboration you would repeat.'),
        ('What could improve?', 'Describe one practical change to test in a future visit.'),
        ('What should I learn next?', 'Note a resource, course or question for supervision.'),
        ('What will I do with it?', 'Set a next step and a date to revisit your learning.'))),
]


def journal():
    c=Canvas(str(ROOT/'paediatric-physio-journal.pdf'),pagesize=(W,H),pageCompression=1)
    c.setTitle('Paediatric Physiotherapy Journal')
    base(c)
    c.setFillColor(HexColor('#f0e0d6'))
    c.rect(0, 430, W, H-430, fill=1, stroke=0)
    label(c,'PTJC / CLINICIAN WORKBOOK',M,735,10,RED,'Helvetica-Bold')
    for i,title in enumerate(('Paediatric Physiotherapy','Journal')):
        label(c,title,M,655-i*54,37,NAVY,'Times-Bold')
    label(c,'Visit planning, activity ideas and practice reflection',M,516,12,NAVY)
    c.setStrokeColor(RED)
    c.line(M,477,W-M,477)
    label(c,'Name',78,311,10,NAVY,'Helvetica-Bold')
    lines(c,121,309,357,1);field(c,'Journal_name',121,311,357,18)
    label(c,'Fill in the PDF or print fresh copies of the pages you use.',M,248,10,NAVY)
    label(c,'Keep patient identifiers in your approved clinical system.',M,226,10,NAVY)
    c.showPage()
    for page_no,(title,blocks) in enumerate(JOURNAL,1):
        base(c)
        label(c,f'PRACTICE JOURNAL  /  {page_no:02}', M,739,10,RED,'Helvetica-Bold')
        label(c,title,M,701,29,NAVY,'Times-Bold')
        label(c,'Date / week:',M,670,10,NAVY)
        lines(c,120,668,240,1);field(c,f'Section_{page_no}_date',120,670,240)
        for i,(heading,prompt) in enumerate(blocks):
            journal_block(c,f'Section_{page_no}_notes_{i+1}',heading,prompt,526-i*133,PALETTES[i])
        c.showPage()
    c.save()


def wall_calendar():
    c=Canvas(str(ROOT/'physio-wall-calendar-2027.pdf'),pagesize=(W,H),pageCompression=1)
    c.setTitle('2027 Physiotherapy Photo Wall Calendar')
    for month in range(1,13):
        c.setFillColor(white);c.rect(0,0,W,H,fill=1,stroke=0)
        c.drawImage(str(PHOTOS/f'{month:02}.jpg'),M,371,W-2*M,365,mask=None)
        c.setStrokeColor(HexColor('#e0e5e8'));c.circle(W/2,760,5,stroke=1,fill=0)
        label(c,month_name[month].upper(),M,326,30,NAVY,'Helvetica-Bold')
        c.setFont('PTJCPrintBold',27);c.setFillColor(NAVY);c.drawRightString(W-M,327,'2027')
        cw=(W-2*M)/7
        for day,short in enumerate(('SUN','MON','TUE','WED','THU','FRI','SAT')):
            label(c,short,M+day*cw+7,294,9,NAVY,'Helvetica-Bold')
        for row,week in enumerate(Calendar(SUNDAY).monthdayscalendar(2027,month)):
            for day,date in enumerate(week):
                x=M+day*cw
                y=245-row*36
                c.setStrokeColor(HexColor('#d8e1e4'));c.setFillColor(HexColor('#f3f7f8') if day in (0,6) else white)
                c.rect(x,y,cw,36,stroke=1,fill=1)
                if date:
                    label(c,str(date),x+6,y+22,9,NAVY,'Helvetica-Bold')
                    field(c,f'M{month:02}_day_{date:02}',x+4,y+2,cw-8,18,True)
        label(c,'PTJC  /  PHYSIOTHERAPY JOBS CANADA', M,30,8,NAVY,'Helvetica-Bold')
        label(c,'US LETTER',W-M-54,30,8,NAVY)
        c.showPage()
    c.save()


if __name__=='__main__':
    journal()
    wall_calendar()
