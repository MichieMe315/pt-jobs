from io import BytesIO
from pathlib import Path
from threading import Lock
from html import escape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, NextPageTemplate, PageTemplate, Paragraph, HRFlowable, Image
from .schema import status_lines, DEFAULT_ORDER
_lock=Lock()

def fonts():
    with _lock:
        if 'PTJCResume' not in pdfmetrics.getRegisteredFontNames():
            path=Path(__file__).parent/'assets'
            pdfmetrics.registerFont(TTFont('PTJCResume',str(path/'DejaVuSans.ttf')))
            pdfmetrics.registerFont(TTFont('PTJCResumeBold',str(path/'DejaVuSans-Bold.ttf')))
            pdfmetrics.registerFont(TTFont('PTJCResumeSerif',str(path/'DejaVuSerif.ttf')))
            pdfmetrics.registerFontFamily('PTJCResume',normal='PTJCResume',bold='PTJCResumeBold')

def render_pdf(d, preview=False, example=False, canadian=False):
    fonts()
    out = BytesIO()
    layout = d.get('layout', 'classic')
    page_w, page_h = 612, 792
    margin = 42
    content_w = page_w - margin * 2
    has_columns = layout != 'classic'
    ink = colors.HexColor({'classic':'#202020', 'clinical':'#30363b', 'editorial':'#302d29', 'sidebar':'#41372f'}[layout])
    palette = d.get('palette', 'original')
    tones = {
        'slate': ('#334155', '#e8edf2'),
        'navy': ('#203c5c', '#e5edf5'),
        'plum': ('#58334b', '#f1e6ee'),
        'grayscale': ('#252525', '#ececec'),
        'forest': ('#22493d', '#e9f1e9'), 'teal': ('#145663', '#e6f3f4'),
        'berry': ('#75384f', '#f7e9ee'), 'clay': ('#793f2d', '#f9eee6'),
        'cobalt': ('#293e86', '#e9edfc'),
    }
    accent, tint = tones.get(palette, (ink, '#fae5d7' if layout == 'clinical' else '#f2ede7'))
    ink = colors.toColor(accent)
    wash = colors.HexColor(tint)
    if not canadian and palette == 'original':
        ink = colors.HexColor({'classic':'#253449','clinical':'#20423f','editorial':'#543446','sidebar':'#29364a'}[layout])
        wash = colors.HexColor('#fae5d7' if layout == 'clinical' else '#eaf0f3')
    if layout == 'classic' and palette == 'original':
        ink = colors.HexColor('#202020')
    if d.get('accent_colour'):
        ink = colors.HexColor(d['accent_colour'])
    header_fill = colors.HexColor(d['header_colour']) if layout == 'clinical' and d.get('header_colour') else wash
    dark_header = (.2126*header_fill.red + .7152*header_fill.green + .0722*header_fill.blue) < .5
    header_ink = colors.white if layout == 'clinical' and dark_header and not d.get('accent_colour') else ink
    typeface = d.get('typeface','original')
    quiet = colors.HexColor('#45484b')
    rule = colors.HexColor('#b8b0a7')
    family = {
        'serif': ('PTJCResumeSerif', 'PTJCResumeSerif'),
        'helvetica': ('Helvetica', 'Helvetica-Bold'),
        'times': ('Times-Roman', 'Times-Bold'),
        'mono': ('Courier', 'Courier-Bold'),
        'italic': ('Times-Italic', 'Times-BoldItalic'),
    }
    normal_face, bold_face = family.get(typeface, ('PTJCResume', 'PTJCResumeBold'))
    compact = layout == 'classic'
    body_size, body_leading = (10.1, 13.3) if compact else ((11, 16) if canadian else (10.5, 14.8))
    base = ParagraphStyle('body', fontName=normal_face, fontSize=body_size, leading=body_leading,
                          spaceAfter=4 if compact else 7, splitLongWords=True)
    heading = ParagraphStyle('heading', parent=base,
                             fontName='PTJCResumeSerif' if layout == 'editorial' and typeface == 'original' else bold_face,
                             fontSize=10.2 if compact else 11, leading=14, spaceBefore=10 if compact else 15,
                             spaceAfter=4 if compact else 6, keepWithNext=True, textColor=ink)
    bold = ParagraphStyle('role', parent=base, fontName=bold_face, keepWithNext=True, spaceAfter=2)
    small = ParagraphStyle('small', parent=base, fontSize=9.5, leading=13.5, textColor=quiet)
    job_meta = ParagraphStyle('role details', parent=small, keepWithNext=True, spaceAfter=6)
    bullet = ParagraphStyle('bullet', parent=base, leftIndent=11, firstLineIndent=-9,
                            spaceAfter=3 if compact else 4)
    def P(t, style=base):
        return Paragraph(escape(str(t)).replace('\n','<br/>'),style)
    contacts = [d[k] for k in ('location','email','phone','profile_url') if d.get(k)]
    name = d.get('name') or 'Your name'
    title = ParagraphStyle('name', parent=base,
        fontName=({'editorial':'PTJCResume', 'clinical':'PTJCResume', 'sidebar':'PTJCResumeSerif'}.get(layout, bold_face)
                  if typeface == 'original' else bold_face),
        fontSize={'classic':21, 'clinical':25, 'editorial':31, 'sidebar':29}[layout], leading=37,
        textColor=header_ink, alignment=1 if layout != 'sidebar' else 0)
    centered = ParagraphStyle('header contact', parent=small, alignment=1, spaceAfter=0)
    display_name = name
    name_line = P(display_name, title)
    identity = [name_line]
    if d.get('portrait'):
        from base64 import b64decode
        from reportlab.lib.utils import ImageReader
        stream = BytesIO(b64decode(d['portrait'].split(',',1)[1]))
        w,h = ImageReader(stream).getSize()
        stream.seek(0)
        scale = d.get('portrait_size',64)/max(w,h)
        portrait = Image(stream,width=w*scale,height=h*scale)
        portrait.hAlign = 'CENTER' if canadian and layout != 'sidebar' else 'LEFT'
        identity.insert(0,portrait)
    role = d.get('target_role') if canadian else next(
        (row.get('role') for row in d.get('experience', []) if row.get('role')), ''
    )
    if role:
        role_style = ParagraphStyle('header role', parent=centered if layout != 'sidebar' else small,
                                    fontName='Times-Italic' if layout == 'clinical' and typeface == 'original' else normal_face,
                                    fontSize=12 if layout == 'clinical' else 9.2,
                                    textColor=header_ink if layout == 'clinical' else quiet)
        identity.append(P(role.upper() if layout == 'editorial' else role, role_style))
    contact_line = None
    if contacts and layout in ('classic', 'editorial'):
        contact_line = P('  |  '.join(contacts), centered)
        identity.append(contact_line)
    order = [key for key in d.get('section_order', DEFAULT_ORDER) if key not in d.get('hidden_sections', [])]
    identity_h = sum(item.wrap(content_w, page_h)[1] + 5 for item in identity)
    if contact_line and layout == 'editorial':
        identity_h += 11
    header_top = page_h - 37
    header_bottom = header_top - identity_h - (17 if layout == 'clinical' else 10)
    first_top = header_bottom - 13
    column_w = {'clinical':152, 'editorial':151, 'sidebar':154}.get(layout, 132)
    column_max = first_top - 105
    column_labels = {
        'education': 'Education', 'home_registration': 'Professional registration' if canadian else 'Professional registration outside Canada',
        'development': 'Selected professional development', 'languages': 'Languages',
    }
    side_heading = ParagraphStyle('side heading', parent=heading, fontSize=9.6, leading=13,
                                  spaceBefore=0, spaceAfter=0, alignment=1 if layout == 'clinical' else 0)
    side_text = ParagraphStyle('side body', parent=small, fontSize=10.2, leading=14.1,
                               alignment=1 if layout == 'clinical' else 0)
    side_gap = 15
    groups = []
    used = 0
    def aside(label, values):
        nonlocal used
        if not values:
            return False
        items = [P(label.upper(), side_heading), *(P(value, side_text) for value in values)]
        height = sum(item.wrap(column_w, page_h)[1] + 4 for item in items) + side_gap
        if used + height > column_max:
            return False
        groups.append(items)
        used += height
        return True

    story = [NextPageTemplate('continuation')]
    if contacts and layout in ('sidebar', 'clinical') and not aside('Contact', contacts):
        story.append(P(' | '.join(contacts), small))
    if d.get('education_country') and not canadian:
        story.append(P('Physiotherapy education: '+d['education_country'],small))
    if d.get('specialties') and not (has_columns and aside('Clinical interests', [interest.strip() for interest in d['specialties'].split(',') if interest.strip()])):
        story.append(P('Clinical interests: '+d['specialties'],small))

    def section(label, parts, *, key='', side_values=()):
        if not parts:
            return
        if has_columns and key in column_labels and aside(column_labels[key], side_values):
            return
        label = label.upper() if layout in ('clinical', 'editorial', 'sidebar') else label
        if layout == 'classic':
            story.append(P(label, heading))
            line = HRFlowable(width='100%', thickness=.5, color=rule, spaceBefore=0, spaceAfter=3)
            line.keepWithNext = True
            story.append(line)
        else:
            if layout == 'sidebar':
                line = HRFlowable(width='100%', thickness=.4, color=rule, spaceBefore=6, spaceAfter=3)
                line.keepWithNext = True
                story.append(line)
            story.append(P(label, heading))
            if layout == 'clinical':
                line = HRFlowable(width='100%', thickness=.45, color=rule, spaceBefore=0, spaceAfter=4)
                line.keepWithNext = True
                story.append(line)
        story.extend(parts)

    for key in order:
        if key=='summary' and d.get('summary'):section('Professional summary' if canadian else 'Professional background',[P(d['summary'])])
        elif key=='status' and not canadian:section('Canadian assessment and registration' if d.get('show_assessment_details') else 'Canadian registration',[P(label+': '+text) for label,text in status_lines(d)])
        elif key in ('experience','canadian_experience'):
            parts=[]
            for r in d.get(key,[]):
                if not any(r.values()):
                    continue
                location = r.get('location') if key == 'canadian_experience' else ', '.join(filter(None,[r.get('location'),r.get('country')]))
                identity_text = ' | '.join(filter(None,[r.get('role'),r.get('employer')]))
                details = ' · '.join(filter(None,[location,r.get('dates'),r.get('setting')]))
                points = [x.strip().lstrip('•- ') for x in r.get('bullets','').splitlines() if x.strip()]
                if identity_text:
                    parts.append(P(identity_text, bold if details or points else base))
                if details:
                    parts.append(P(details, job_meta if points else small))
                parts.extend(P('• '+x, bullet) for x in points)
                if parts:
                    parts[-1].spaceAfter = 7 if compact else 11
            section('Clinical experience' if canadian else 'Canadian experience' if key=='canadian_experience' else 'Clinical experience outside Canada',parts)
        elif key=='education':
            values = [' · '.join(filter(None, [r.get('degree'),r.get('institution'),r.get('country'),r.get('completed')])) for r in d.get('education',[])]
            section('Education',[P(v) for v in values],key=key,side_values=values)
        elif key=='placements':
            parts=[]
            for r in d.get('placements',[]):
                parts.append(P(' | '.join(filter(None,[r.get('institution'),r.get('location'),r.get('country'),r.get('dates')])),bold))
                detail=r.get('setting','')
                if r.get('hours'):detail+=' | '+r['hours']+' documented supervised hours'
                if detail:parts.append(P(detail,small))
                if r.get('contribution'):parts.append(P(r['contribution']))
            section('Supervised clinical education',parts)
        elif key=='home_registration' and d.get('home_registration'):
            section(column_labels[key],[P(d['home_registration'])],key=key,side_values=[d['home_registration']])
        elif key=='development':
            values = [' · '.join(filter(None,[r.get('course'),r.get('provider'),r.get('completed')])) for r in d.get('development',[])]
            section(column_labels[key],[P(v) for v in values],key=key,side_values=values)
        elif key=='languages':
            values = [' · '.join(filter(None,[r.get('language'),r.get('proficiency'),r.get('evidence')])) for r in d.get('languages',[])]
            section('Languages',[P(v) for v in values],key=key,side_values=values)
        elif key=='availability' and d.get('show_availability'):section('Availability',[P(label+': '+d[k]) for label,k in [('Work authorization','work_authorization'),('Relocation / availability','relocation')] if d.get(k)])
    right_rail = canadian and layout == 'sidebar'
    first_left = margin + column_w + 27 if has_columns and not right_rail else margin
    first_right = page_w - margin - column_w - 27 if right_rail else page_w - margin
    rail_x = page_w - margin - column_w if right_rail else margin
    divider = first_right + 13 if right_rail else first_left - 13
    if d.get('extra_text'):
        story.extend([P(d.get('extra_heading') or 'Additional information', heading), P(d['extra_text'])])
    if len(story) == 1:
        story.append(P(''))

    def decorate(canvas, doc):
        canvas.saveState()
        if doc.page == 1:
            if layout == 'clinical':
                canvas.setFillColor(header_fill)
                canvas.rect(0, header_bottom, page_w, page_h-header_bottom, fill=1, stroke=0)
            elif layout == 'sidebar':
                canvas.setFillColor(wash)
                rail_bottom = 47
                if right_rail:
                    canvas.rect(divider, rail_bottom, page_w-divider, header_bottom-rail_bottom, fill=1, stroke=0)
                else:
                    canvas.rect(0, rail_bottom, first_left-13, header_bottom-rail_bottom, fill=1, stroke=0)
            y = header_top
            for item in identity:
                _, h = item.wrap(content_w, page_h)
                if item is contact_line and layout == 'editorial':
                    canvas.setStrokeColor(rule)
                    canvas.setLineWidth(.45)
                    canvas.line(margin, y, page_w-margin, y)
                    y -= 8
                if item is name_line and layout == 'editorial':
                    spacing = 2.6
                    width = pdfmetrics.stringWidth(display_name, title.fontName, title.fontSize) + spacing*max(0,len(display_name)-1)
                    if width <= content_w:
                        canvas.saveState()
                        text = canvas.beginText((page_w-width)/2, y-title.fontSize)
                        text.setFont(title.fontName, title.fontSize)
                        text.setCharSpace(spacing)
                        text.setFillColor(ink)
                        text.textLine(display_name)
                        canvas.drawText(text)
                        canvas.restoreState()
                    else:
                        item.drawOn(canvas, margin, y-h)
                else:
                    item.drawOn(canvas, margin, y-h)
                y -= h+5
            canvas.setStrokeColor(rule)
            canvas.setLineWidth(.45)
            canvas.line(margin, header_bottom, page_w-margin, header_bottom)
            if has_columns:
                canvas.line(divider, first_top, divider, 47)
                y = first_top - 8
                for items in groups:
                    for item in items:
                        _, h = item.wrap(column_w,page_h)
                        item.drawOn(canvas,rail_x,y-h)
                        y -= h+4
                    if layout == 'clinical':
                        canvas.line(rail_x, y-3, rail_x+column_w, y-3)
                    y -= side_gap
        else:
            label = P(name, small)
            _, h = label.wrap(content_w, page_h)
            if h <= 30:
                label.drawOn(canvas, margin, 758-h)
            if layout == 'editorial':
                canvas.setStrokeColor(rule)
                canvas.setLineWidth(.45)
                canvas.line(divider, 722, divider, 47)
        canvas.setFont('PTJCResume', 8)
        canvas.setFillColor(quiet)
        if example:
            canvas.drawString(margin, 25, 'Fictional example')
        canvas.drawRightString(page_w-margin, 25, str(doc.page))
        if preview:
            canvas.setFillAlpha(.10)
            canvas.setFont('PTJCResume', 16)
            canvas.translate(306, 390)
            canvas.rotate(33)
            canvas.drawCentredString(0,0,'PREVIEW · physiotherapyjobscanada.ca')
        canvas.restoreState()

    def frame(left, top, right=page_w-margin):
        return Frame(left, 47, right-left, top-47, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    doc=BaseDocTemplate(out, pagesize=(page_w,page_h), title=name+' — Resume', author=d.get('name') or '')
    doc.addPageTemplates([
        PageTemplate(id='first', frames=[frame(first_left, first_top, first_right)], onPage=decorate),
        PageTemplate(id='continuation', frames=[frame(first_left if layout == 'editorial' else margin, 722)], onPage=decorate),
    ])
    doc.build(story)
    return out.getvalue()
