"""Interactive private workbook generated from the same plan as the dashboard."""
from io import BytesIO
from pathlib import Path
import textwrap
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from .planning import build

def render(profile,completed,fees=()):
    import reportlab
    root=Path(reportlab.__file__).parent/'fonts'
    for name,file in [('PTJC','Vera.ttf'),('PTJCBold','VeraBd.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(root/file)))
    buf=BytesIO();c=canvas.Canvas(buf,pagesize=A4);c.setTitle('Your international physiotherapy workbook');c.setAuthor('Physiotherapy Jobs Canada')
    W,H=A4;ink=HexColor('#1f2937');red=HexColor('#b62b3b');muted=HexColor('#526170');page=0
    def text(value,x,y,size=10,bold=False,color=ink):
        c.setFillColor(color);c.setFont('PTJCBold' if bold else 'PTJC',size);c.drawString(x,y,str(value).replace('–','-').replace('—','-').replace('‑','-'))
    def lines(value,y,width=91,size=9.5):
        for paragraph in str(value).split('\n'):
            for line in textwrap.wrap(paragraph,width=width,break_long_words=True) or ['']:
                text(line,46,y,size);y-=14
        return y-7
    def start(title):
        nonlocal page
        if page:c.showPage()
        page+=1;c.setStrokeColor(red);c.setLineWidth(2);c.line(44,H-40,W-44,H-40)
        text('PTJC INTERNATIONAL',46,H-63,9,True,red);text(title,46,H-100,20,True)
        c.setStrokeColor(HexColor('#c6cdd5'));c.line(44,42,W-44,42)
        text('Private planning workbook · '+profile.country_of_education+' to '+(profile.destination_province or 'Canada'),46,28,7.5,color=muted)
        text(str(page),W-55,28,8)
        return H-135
    plan=build(profile);y=start('Your move to Canada')
    from reportlab.lib.utils import ImageReader
    try:
        import fitz
    except (ImportError, OSError):
        fitz = None  # Flags are optional; a missing native DLL must not block the PDF.
    flag_root=Path(__file__).parent.parent/'static/career_mobility/flags'
    drawn=False
    for code,x in [(plan.get('flag_code',''),46),('CA',140)]:
        path=flag_root/(code+'.svg')
        if fitz is not None and code and path.is_file():
            try:
                with fitz.open(path) as svg:png=svg[0].get_pixmap(alpha=True).tobytes('png')
                c.drawImage(ImageReader(BytesIO(png)),x,y-32,width=51,height=34,preserveAspectRatio=True,mask='auto');drawn=True
            except (ValueError,RuntimeError):pass
    if drawn:text('to',112,y-20,10,True);y-=55
    percent=round(100*sum(step['key'] in completed for step in plan['steps'])/len(plan['steps']))
    c.setFillColor(HexColor('#e7eaee'));c.roundRect(46,y-12,W-92,9,4,fill=1,stroke=0)
    if percent:c.setFillColor(red);c.roundRect(46,y-12,(W-92)*percent/100,9,4,fill=1,stroke=0)
    y-=34
    text(str(percent)+'% of checklist complete',46,y,10,True,red);y-=28
    name = profile.user.get_full_name() if getattr(profile, 'user_id', None) else ''
    if name:y=lines(name,y,size=12)
    y=lines(plan['route'],y,size=12)
    for label,value in [('Education country',profile.country_of_education),('Destination',plan['destination']),('Current residence',getattr(profile,'residence_country','') or 'Not supplied'),('Progress',str(sum(s['key'] in completed for s in plan['steps']))+' of '+str(len(plan['steps']))+' steps complete')]:
        text(label,46,y,9,True);y-=18;y=lines(value,y)
    y=lines('Use this workbook to track the actions and evidence for your plan. Tick completed tasks and type notes into the fields. Save a copy after editing. Notes entered in this PDF remain in that copy; update your online checklist separately.',y-15)
    if plan.get('country_note'):y=lines(plan['country_note'],y-10)
    if plan['guidance']:y=lines(plan['guidance']['note'],y-10)
    y=lines('Assessment decisions, professional registration and permission to work are separate. Confirm current requirements before paying fees or setting a start date.',y-15)
    for i,step in enumerate(plan['steps']):
        needed=210+14*(len(textwrap.wrap(step['label'],width=68))+len(textwrap.wrap(step['detail'],width=91))+len(textwrap.wrap(step['evidence'],width=91)))
        if i%2==0 or y<needed+65:y=start(step['stage'])
        title=str(i+1).zfill(2)+'  '+step['label'];y=lines(title,y,width=68,size=12)
        c.acroForm.checkbox(name='done_'+step['key'],tooltip=step['label'],x=46,y=y-14,size=15,checked=step['key'] in completed,buttonStyle='check',borderColor=muted,fillColor=HexColor('#ffffff'),textColor=red)
        text('Completed',70,y-10,9);y-=36
        y=lines(step['detail'],y)
        y=lines('Keep: '+step['evidence'],y)
        label='Official requirements';text(label,46,y,9,color=red);c.linkURL(step['source_url'],(46,y-2,160,y+11),relative=0);y-=24
        text('My notes / requested / sent / accepted',46,y,9,True);y-=70
        c.acroForm.textfield(name='notes_'+step['key'],tooltip='Notes: '+step['label'],x=46,y=y,width=W-92,height=57,fontName='Helvetica',fontSize=10,borderWidth=.7,borderColor=muted,fillColor=HexColor('#f4f6f8'),textColor=ink,fieldFlags='multiline',maxlen=1800)
        y-=40
    y=start('Document delivery for your route')
    for task in plan.get('document_tasks',[]):
        needed=35+14*(len(textwrap.wrap(task['action'],width=91))+len(textwrap.wrap(task['sender'],width=91)))
        if y<needed+70:y=start('Document delivery continued')
        y=lines(task['title'],y,width=68,size=12)
        y=lines(task['action'],y)
        y=lines('Who sends it: '+task['sender'],y)
    if plan.get('language_policy'):
        y=start('Language test reference')
        y=lines('If a test is required, meet the minimum in every skill. Check the current policy and destination requirements before booking. The table below follows CAPR’s October 2026 policy.',y)
        for test,scores in plan['language_policy']['minimum_scores'].items():
            y=lines(test,y,width=75,size=11)
            y=lines('Reading '+str(scores.get('reading',''))+' | Writing '+str(scores.get('writing',''))+' | Listening '+str(scores.get('listening',''))+' | Speaking '+str(scores.get('speaking','')),y)
        y=lines('Official results must reach CAPR within two years. Most applicants must meet the scores in one sitting; the policy permits an eligible IELTS One Skill Retake. Manitoba has additional language-policy provisions.',y-10)
    y=start('Your registration budget')
    y=lines('Assessment and examination fees',y,size=12)
    for ex in plan['cost_examples']:
        for label,amount in ex['components_cad'].items():
            label={'qa':'Qualifications assessment','pet':'Physiotherapy Evaluation Tool','pap':'Pre-approved application','cpte_standard':'Canadian Physiotherapy Examination'}.get(label,label)
            y=lines(label+': CAD $'+str(amount),y)
        y=lines('These fees: CAD $'+str(ex['total_cad'])+'. Excludes '+', '.join(ex['excluded'])+'.',y)
    if not plan['cost_examples']:y=lines('Use your individual assessment instructions or destination decision to confirm the assessment fees that apply.',y)
    y=lines(plan['destination']+' registration components',y-8,size=12)
    for fee in plan['licence_research'][:6]:
        y=lines(fee['description']+': '+('CAD $'+str(fee['amount_cad']) if fee.get('amount_cad') is not None else 'No territorial PT fee listed' if fee.get('status')=='no_territorial_regulator_listed' else 'Confirm amount'),y)
    y=lines('Full-year and partial-year permits are alternatives. Do not add both. Other costs can include language tests, document services, courses, insurance and travel.',y-5)
    # Keep editable budget fields on their own page so researched rows never crowd them.
    y=start('Build your own budget')
    for key,label in [('assessment','Assessment and examination fees (CAD)'),('registration','Destination application and registration (CAD)'),('documents','Documents, translations, tests and courses (CAD)'),('other','Insurance, travel and other costs (CAD)')]:
        text(label,46,y,10,True);y-=42;c.acroForm.textfield(name='budget_'+key,x=46,y=y,width=W-92,height=28,fontSize=11,borderColor=muted,fillColor=HexColor('#f4f6f8'));y-=35
    text('Budget notes / confirmed quotes / payment dates',46,y,10,True);y-=125
    c.acroForm.textfield(name='budget_notes',x=46,y=y,width=W-92,height=110,fontSize=10,fieldFlags='multiline',maxlen=2500,borderColor=muted,fillColor=HexColor('#f4f6f8'))
    y=start('Sources and next steps')
    sources=list(dict.fromkeys([s['source_url'] for s in plan['steps']]+[f['source_url'] for f in plan['licence_research'] if f.get('source_url')]))
    for i,url in enumerate(sources,1):
        if y<120:y=start('Sources continued')
        text('Source '+str(i)+' - open official page',46,y,10,True,red);c.linkURL(url,(46,y-3,W-46,y+13),relative=0);y-=20;y=lines(url,y,width=97,size=8)
    y=lines('Information updated as of '+plan['reviewed_on']+'. Confirm fees and requirements with the issuing organization before paying.',y-5)
    c.save();return buf.getvalue()
