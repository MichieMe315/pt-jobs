"""Private, readable salary comparison PDF; calculations are rederived from saved inputs."""
from io import BytesIO
from math import isfinite
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether

NAVY=colors.HexColor('#17374c')
BLUE=colors.HexColor('#697886')
GREEN=colors.HexColor('#c9343b')
PALE=colors.HexColor('#edf4f8')

def compute(d):
    def number(key, minimum=0, maximum=1e8):
        x=float(d[key]);
        if not isfinite(x) or x<=minimum or x>maximum:raise ValueError(key)
        return x
    pay_type=d['employee-type']
    if pay_type not in ('hourly','annual'):raise ValueError('employee-type')
    pay=number('employee-pay')
    hours=number('employee-hours',0,80) if pay_type=='hourly' else None
    paid_weeks=number('employee-weeks',0,52) if pay_type=='hourly' else None
    fee=number('billing',0,100000);split=number('split',0,100)
    visits=number('visits',0,60);days=number('days',0,7);weeks=number('weeks',0,52)
    def optional(key):
        raw=d.get(key)
        if raw is None or raw=='':return 0.
        n=float(raw)
        if not isfinite(n) or n<0 or n>10000000:raise ValueError(key)
        return n
    expenses=optional('contractor-expenses');unpaid=optional('unpaid-hours')
    if unpaid>100:raise ValueError('unpaid-hours')
    employee=pay if pay_type=='annual' else pay*hours*paid_weeks
    visit_share=fee*split/100
    contractor=visit_share*visits*days*weeks
    net=contractor-expenses
    return dict(pay_type=pay_type,pay=pay,hours=hours,paid_weeks=paid_weeks,fee=fee,split=split,visits=visits,days=days,weeks=weeks,expenses=expenses,unpaid=unpaid,employee=employee,contractor=contractor,net=net,visit_share=visit_share,breakeven=(employee+expenses)/(visit_share*days*weeks))

def pdf_bytes(data, title=None):
    v=compute(data)
    money=lambda x:'${:,.0f}'.format(x)
    if title is None:title=f"{money(v['pay'])}{'/hour' if v['pay_type']=='hourly' else '/year'} vs. {v['split']:g}% split"
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='PTTitle',parent=styles['Title'],fontSize=21,leading=26,textColor=NAVY,spaceAfter=8))
    styles.add(ParagraphStyle(name='PTSub',parent=styles['Normal'],fontSize=9,leading=14,textColor=colors.HexColor('#4d6676')))
    styles.add(ParagraphStyle(name='PTSection',parent=styles['Heading2'],fontSize=12,textColor=NAVY,spaceBefore=17,spaceAfter=8))
    buffer=BytesIO();doc=SimpleDocTemplate(buffer,pagesize=letter,rightMargin=43,leftMargin=43,topMargin=42,bottomMargin=42,title='PTJC salary vs split offer comparison')
    story=[Paragraph('PHYSIOTHERAPY JOBS CANADA  |  CAREER TOOLS',styles['PTSub']),Spacer(1,9),Paragraph(escape(title),styles['PTTitle']),Paragraph('Employee compensation vs. contractor fee split • Canadian dollars • before tax',styles['PTSub']),Spacer(1,17)]
    rows=[['EMPLOYEE ANNUAL GROSS','CONTRACTOR ANNUAL REVENUE'],[money(v['employee']),money(v['contractor'])]]
    t=Table(rows,colWidths=[260,260],rowHeights=[25,43]);t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,-1),colors.HexColor('#eaf2f8')),('BACKGROUND',(1,0),(1,-1),colors.HexColor('#fbecee')),('TEXTCOLOR',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,1),(-1,1),NAVY),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,1),(-1,1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,0),9),('FONTSIZE',(0,1),(-1,1),19),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),15)]));story.extend([t,Spacer(1,14)])
    story.append(Paragraph('What the numbers mean',styles['PTSection']))
    lines=[('Employee gross / month',money(v['employee']/12)),('Contractor revenue / month',money(v['contractor']/12)),('Contractor business expenses / year',money(v['expenses'])),('Contractor revenue after expenses / year',money(v['net'])),('Annual difference after contractor expenses',('+' if v['net']-v['employee']>0 else '')+money(v['net']-v['employee'])),('Contractor earnings per completed visit',money(v['visit_share'])),('Break-even completed visits per clinical day',f"{v['breakeven']:.1f}")]
    details=Table([[a,b] for a,b in lines],colWidths=[355,165]);details.setStyle(TableStyle([('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white,PALE]),('TEXTCOLOR',(0,0),(-1,-1),NAVY),('FONTNAME',(1,0),(1,-1),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('LEFTPADDING',(0,0),(-1,-1),12)]));story.append(details)
    story.append(Paragraph('Assumptions',styles['PTSection']))
    for line in [f"Employee: {'annual salary' if v['pay_type']=='annual' else f"{money(v['pay'])}/hour, {v['hours']:g} hours/week, {v['paid_weeks']:g} paid weeks/year"}.",f"Contractor: clinic fee {money(v['fee'])}/visit × {v['split']:g}% share × {v['visits']:g} completed visits/day × {v['days']:g} days/week × {v['weeks']:g} weeks/year.",f"Annual professional/business expenses: {money(v['expenses'])}. Additional unpaid hours/week: {v['unpaid']:g}."]:
        story.append(Paragraph(escape(line),styles['Normal']));story.append(Spacer(1,5))
    story.append(Paragraph('Questions to ask before accepting',styles['PTSection']))
    for q in ['Are completed visits and cancellations paid as expected?','Who pays for insurance, licensing, supplies and charting time?','How do vacation, benefits, CPP, taxes and paid holidays change the offer?','What are the notice, scheduling and restrictive-covenant terms?']:
        story.append(Paragraph('• '+escape(q),styles['Normal']));story.append(Spacer(1,5))
    story.extend([Spacer(1,14),Paragraph('Planning estimate only. Contractor revenue is not take-home pay. This report does not calculate income tax, CPP, employee benefits or legal employment status. Verify the agreement and seek appropriate professional advice.',styles['PTSub'])])
    doc.build(story);return buffer.getvalue()
