"""Editable cards using the supplied PTJC practice-design assets."""
import base64,binascii,json,re,xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from html import escape
from django.core.exceptions import ValidationError
from django.http import HttpResponse,JsonResponse
from django.shortcuts import render,get_object_or_404,redirect
from django.urls import reverse
from django.db.models import F
from django.utils import timezone
from django.views.decorators.http import require_POST,require_GET
from django.views.decorators.cache import never_cache
from .models import BusinessCardDraft
from functools import wraps
from django.contrib.auth.decorators import login_required
from career_mobility.models import DigitalProduct
from career_mobility.store_access import has_access
from career_mobility.starter import authorize as authorize_starter, remaining as starter_remaining
SLUG='international-business-card-builder-access'
def job_board(request):
    return request.resolver_match.namespace == 'jobseeker_cards'


def route(request, name, args=None):
    namespace = 'jobseeker_cards' if job_board(request) else 'ptjc_resumes'
    return reverse(namespace + ':' + name, args=args)


def candidate_only(view):
    @login_required
    @wraps(view)
    def checked(request, *args, **kwargs):
        user = request.user
        jobseeker = getattr(user, 'jobseeker', None)
        approved = jobseeker and jobseeker.is_approved and jobseeker.login_active
        if not user.is_active or not (approved or (job_board(request) and getattr(user, 'employer', None)) or (not job_board(request) and hasattr(user, 'international_pt_profile'))):
            return HttpResponse('An employer or candidate account is required to save business cards.', status=403)
        from career_mobility.store_eligibility import account_requirement
        product = DigitalProduct.objects.filter(slug=SLUG).first()
        if product and product.eligible_accounts and account_requirement(user, product):
            return HttpResponse('This product is unavailable for your account type.', status=403)
        return view(request, *args, **kwargs)
    return checked


MAX_CARD_BODY = 600_000

def artwork(value):
    from PIL import Image
    if not isinstance(value, str) or len(value) > 270_000:
        raise ValidationError('Use a smaller image.')
    if not value:
        return ''
    try:
        prefix, encoded = value.split(',', 1)
        if prefix not in ('data:image/png;base64', 'data:image/jpeg;base64'):
            raise ValueError
        with Image.open(BytesIO(base64.b64decode(encoded, validate=True))) as image:
            if image.format != ('PNG' if '/png' in prefix else 'JPEG') or max(image.size) > 1500:
                raise ValueError
            image.verify()
    except (ValueError, OSError, SyntaxError, binascii.Error, Image.DecompressionBombError) as exc:
        raise ValidationError('Choose a valid PNG or JPEG image.') from exc
    return value


DESIGNS=('clinical','community','editorial','networking')
FIELDS={'name':70,'role':100,'organization':100,'phone':60,'email':140,'website':160,'address':120,'city':100,'booking':160,'background':140,'status':140,'education_country':80,'profile':160,'initials':5}
CARD_FONTS = {
    'sans': ('Arial, Helvetica, sans-serif', 'Helvetica', 'Helvetica-Bold'),
    'serif': ('Georgia, serif', 'PTJCResumeSerif', 'PTJCResumeSerif'),
    'editorial': ('Times New Roman, Times, serif', 'Times-Roman', 'Times-Bold'),
    'mono': ('Courier New, Courier, monospace', 'Courier', 'Courier-Bold'),
    'humanist': ('DejaVu Sans, Verdana, sans-serif', 'PTJCResume', 'PTJCResumeBold'),
    'italic': ('Times New Roman, Times, serif', 'Times-Italic', 'Times-BoldItalic'),
}

def _card_pdf_font(node):
    spec = CARD_FONTS.get(node.get('data-typeface'))
    if spec:
        return spec[2] if node.get('font-weight') == 'bold' else spec[1]
    if 'Georgia' in node.get('font-family', ''):
        return 'PTJCResumeSerif'
    return 'PTJCResumeBold' if node.get('font-weight') == 'bold' else 'PTJCResume'


def normalize(raw):
    if not isinstance(raw,dict):raise ValidationError('Enter card details.')
    out={}
    for key,limit in FIELDS.items():
        value=raw.get(key,'')
        if not isinstance(value,str) or len(value)>limit or any(ord(c)<32 for c in value):raise ValidationError('Check '+key+' and its length.')
        try:value.encode('utf-8')
        except UnicodeEncodeError:raise ValidationError('Unsupported character in '+key+'.')
        out[key]=value.strip()
    out['design']=raw.get('design','networking')
    if out['design'] not in DESIGNS:raise ValidationError('Choose an available design.')
    hidden = raw.get('hidden', [])
    if not isinstance(hidden, list):
        raise ValidationError('Invalid field selection.')
    out['hidden'] = [key for key in FIELDS if key in hidden]
    for key,default in (('paper',''),('ink',''),('accent','')):
        value = raw.get(key, default)
        if not isinstance(value,str) or (value and not re.fullmatch(r'#[0-9a-fA-F]{6}',value)):
            raise ValidationError('Choose a valid colour.')
        out[key] = value
    out['typeface'] = raw.get('typeface','original')
    if not isinstance(out['typeface'], str) or out['typeface'] not in ('original', *CARD_FONTS):
        raise ValidationError('Choose a valid font.')
    extra = raw.get('extra','')
    if not isinstance(extra,str) or len(extra)>160:
        raise ValidationError('Custom detail is too long.')
    if any(ord(char)<32 for char in extra):
        raise ValidationError('Enter the custom detail on one line.')
    out['extra'] = extra.strip()
    for side in ('front', 'back'):
        size = raw.get(side+'_scale',100)
        if type(size) is not int or not 35 <= size <= 100:
            raise ValidationError('Choose an artwork size between 35 and 100 percent.')
        out[side+'_scale'] = size
        for layer in ('art','text'):
            for axis in ('x','y'):
                key = f'{side}_{layer}_{axis}'
                value = raw.get(key,0)
                if type(value) is not int or not -24 <= value <= 24:
                    raise ValidationError('Invalid layer position.')
                out[key] = value
        out[side + '_art'] = artwork(raw.get(side + '_art', ''))
        placement = raw.get(side + '_placement', 'right')
        if placement not in ('right', 'left', 'full'):
            raise ValidationError('Choose an artwork placement.')
        out[side + '_placement'] = placement
    return out

def svg(data,side,watermark=False):
    data = {**data, **{key:'' for key in data.get('hidden', [])}}
    ns = '{http://www.w3.org/2000/svg}'
    root=ET.parse(Path(__file__).parent/'assets/cards'/(data['design']+'-'+side+'.svg')).getroot()
    replacements={'Alex Morgan':data['name'],'Robin Chen':data['name'],'Samira Patel':data['name'],'Ari Shah':data['name'],'AM':data['initials'],
      'MScPT  /  Physiotherapist':data['role'],'Physiotherapist  /  MScPT':data['role'],'Physiotherapy graduate':data['role'],
      'EXAMPLE REHABILITATION':data['organization'],'EXAMPLE COMMUNITY REHAB':data['organization'],'EXAMPLE PHYSIOTHERAPY':data['organization'],'Example Rehabilitation':data['organization'],
      '613 555 0142':data['phone'],'519 555 0142':data['phone'],'+91 555 0142':data['phone'],
      'alex@clinic.example':data['email'],'robin@clinic.example':data['email'],'samira@clinic.example':data['email'],'ari.shah@example.com':data['email'],
      'clinic.example':data['website'],'clinic.example/book':data['booking'],'123 Example Street, Suite 200':data['address'],'City, Province  A1A 1A1':data['city'],
      'Outpatient and inpatient rehabilitation':data['background'],'Clinical experience gained in India':('Education: '+data['education_country']) if data['education_country'] else '',
      'Education and clinical experience: India':('Education: '+data['education_country']) if data['education_country'] else '',
      'Not currently registered in Canada':data['status'],'linkedin.example/your-profile':data['profile'],
      '613 555 0142   /   clinic.example':' / '.join(filter(None,[data['phone'],data['website']])),'Professional networking':data['organization']}
    from .pdf import fonts
    from reportlab.pdfbase.pdfmetrics import stringWidth
    fonts()
    if data.get('paper'):
        root[0].set('fill',data['paper'])
        # Keep user text legible on the selected single-colour paper.
        for node in list(root)[1:]:
            if node.tag == ns+'rect' and float(node.get('width',0)) * float(node.get('height',0)) > 0.35 * 252 * 144:
                root.remove(node)
    if accent := data.get('accent'):
        for layer in list(root)[1:]:
            for node in layer.iter(ns+'rect'):
                node.set('fill', accent)
    if side == 'back' and data.get('extra'):
        for node in root.iter():
            if node.tag == ns+'text' and float(node.get('y',0)) > 45:
                node.set('y',str(45+(float(node.get('y'))-45)*.83))
        root.append(ET.Element(ns+'text',{'x':'16','y':'126','font-size':'8','fill':'#694d44'}))
        root[-1].text = data['extra']
    for node in root.iter():
        if node.tag.endswith('text'):
            if data.get('ink'):
                node.set('fill',data['ink'])
            if spec := CARD_FONTS.get(data.get('typeface')):
                node.set('font-family', spec[0])
                node.set('data-typeface', data['typeface'])
                if data['typeface'] == 'italic':
                    node.set('font-style', 'italic')
            node.text=replacements.get(node.text,node.text)
            # Shrink text to its available line width. Never clip customer names.
            size=float(node.get('font-size',10));x=float(node.get('x',18))
            width=max(20,2*min(x-14,238-x) if node.get('text-anchor')=='middle' else 234-x)
            font=_card_pdf_font(node)
            while size>5 and stringWidth(node.text or '',font,size)>width:size-=.25
            node.set('font-size',str(size))
    if image := data.get(side + '_art'):
        placement = data.get(side + '_placement', 'right')
        if placement == 'full':
            root[:] = [root[0]]
            x, y, w, h = 0, 0, 252, 144
        else:
            left = placement == 'left'
            start, end = (91, 236) if left else (16, 160)
            x, y, w, h = (12 if left else 174), 30, 66, 78
            for node in list(root):
                if node.get('id') == 'logo-slot':
                    root.remove(node)
                    continue
                if node.tag.endswith('text'):
                    centred = node.get('text-anchor') == 'middle'
                    node.set('x', str((start+end)/2 if centred else start))
                    size = float(node.get('font-size', 10))
                    font = _card_pdf_font(node)
                    measured = stringWidth(node.text or '', font, size)
                    if measured:
                        node.set('font-size', str(min(size, size*(end-start)/measured)))
        ET.SubElement(root, '{http://www.w3.org/2000/svg}image', {
            'x':str(x), 'y':str(y), 'width':str(w), 'height':str(h),
            'href':image, 'preserveAspectRatio':'none' if placement=='full' else 'xMidYMid meet'})
        scale = data.get(side+'_scale',100)/100
        root[-1].attrib.update(x=str(x+w*(1-scale)/2),y=str(y+h*(1-scale)/2),width=str(w*scale),height=str(h*scale))
    for node in root.iter():
        tag = node.tag.split('}')[-1]
        layer = 'art' if tag == 'image' else 'text' if tag == 'text' else None
        if layer:
            for axis in ('x','y'):
                value = float(node.get(axis,0)) + data.get(f'{side}_{layer}_{axis}',0)
                if layer == 'art':
                    size = float(node.get('width' if axis == 'x' else 'height',0))
                    value = min(max(0,value),(252 if axis == 'x' else 144)-size)
                node.set(axis,str(value))
    if watermark:
        node=ET.SubElement(root,'{http://www.w3.org/2000/svg}text',{'x':'126','y':'138','text-anchor':'middle','font-size':'6','fill':'#a83449'});node.text='PREVIEW · physiotherapyjobscanada.ca'
    return ET.tostring(root,encoding='utf-8',xml_declaration=True)

def pdf(data,preview=False):
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    from .pdf import fonts
    fonts();out=BytesIO();c=canvas.Canvas(out,pagesize=(252,144));c.setTitle(data['name']+' — Business card')
    for side in ('front','back'):
        root=ET.fromstring(svg(data,side))
        for node in root.iter():
            tag=node.tag.split('}')[-1]
            if tag=='rect':
                c.setFillColor(HexColor(node.get('fill','#ffffff')));c.rect(float(node.get('x',0)),144-float(node.get('y',0))-float(node.get('height',0)),float(node.get('width',0)),float(node.get('height',0)),stroke=0,fill=1)
            elif tag=='image':
                from reportlab.lib.utils import ImageReader
                image = ImageReader(BytesIO(base64.b64decode(node.get('href').split(',',1)[1])))
                x, y, w, h = (float(node.get(a)) for a in ('x','y','width','height'))
                c.drawImage(image, x, 144-y-h, w, h, preserveAspectRatio=node.get('preserveAspectRatio')!='none', anchor='c', mask='auto')
            elif tag=='text':
                c.setFillColor(HexColor(node.get('fill','#183a47')));c.setFont(_card_pdf_font(node),float(node.get('font-size',10)))
                draw=c.drawCentredString if node.get('text-anchor')=='middle' else c.drawString;draw(float(node.get('x',0)),144-float(node.get('y',0)),node.text or '')
        if preview:
            c.saveState();c.setFillAlpha(.20);c.setFillColor(HexColor('#9a3046'));c.setFont('PTJCResumeBold',9);c.translate(126,72);c.rotate(25);c.drawCentredString(0,0,'PREVIEW · physiotherapyjobscanada.ca');c.restoreState()
        c.showPage()
    c.save();return out.getvalue()

@never_cache
@candidate_only
def index(request):
    product=DigitalProduct.objects.filter(slug=SLUG).first()
    return render(request,'ptjc_resumes/cards_index.html' if job_board(request) else 'ptjc_resumes/international_cards_index.html',{'card_create_url':route(request,'card_create'),'card_rows':[{'draft':d,'edit_url':route(request,'card_edit',[d.pk]),'delete_url':route(request,'card_delete',[d.pk])} for d in BusinessCardDraft.objects.filter(owner=request.user).order_by('-updated_at')],'product':product,'paid':bool(product and has_access(request.user,product))})
@candidate_only
@require_POST
def create(request):
    if BusinessCardDraft.objects.filter(owner=request.user).count()>=30:return HttpResponse('Delete an unused card draft first.',status=400)
    d=BusinessCardDraft.objects.create(owner=request.user,data=normalize({'design': 'clinical' if getattr(request.user, 'jobseeker', None) else 'networking', 'name':request.user.get_full_name(),'email':request.user.email,'education_country':getattr(getattr(request.user,'international_pt_profile',None),'country_of_education','')}))
    return redirect(route(request,'card_edit',[d.pk]))
@never_cache
@candidate_only
@require_GET
def edit(request,pk):
    d=get_object_or_404(BusinessCardDraft,pk=pk,owner=request.user);product=DigitalProduct.objects.filter(slug=SLUG).first()
    cfg={'data':normalize(d.data),'revision':d.revision,'save_url':route(request,'card_save',[pk]),'preview_url':route(request,'card_preview',[pk]),'download_url':route(request,'card_download',[pk])}
    return render(request,'ptjc_resumes/jobseeker_card_editor.html' if job_board(request) else 'ptjc_resumes/international_card_editor.html',{'draft':d,'card_index_url':route(request,'cards'),'product':product,'paid':bool(product and has_access(request.user,product)),'starter_cards':starter_remaining(request.user,product),'bootstrap':cfg})
@candidate_only
@require_POST
def save(request,pk):
    d=get_object_or_404(BusinessCardDraft,pk=pk,owner=request.user)
    if len(request.body)>MAX_CARD_BODY:return JsonResponse({'error':'Card data is too large.'},status=413)
    try:
        payload=json.loads(request.body);data=normalize(payload['data']);rev=payload['revision']
        if type(rev) is not int:raise ValueError
    except (ValueError,KeyError,TypeError,ValidationError):return JsonResponse({'error':'Check the card fields.'},status=400)
    if not BusinessCardDraft.objects.filter(pk=d.pk,owner=request.user,revision=rev).update(data=data,revision=F('revision')+1,updated_at=timezone.now()):return JsonResponse({'error':'This card changed in another tab. Reload before editing.'},status=409)
    from career_mobility.product_activity import record
    product = DigitalProduct.objects.filter(slug=SLUG).first()
    if product:
        record(product, 'saved', request=request)
    return JsonResponse({'revision':rev+1})
@never_cache
@candidate_only
@require_GET
def preview(request,pk):
    d=get_object_or_404(BusinessCardDraft,pk=pk,owner=request.user)
    side=request.GET.get('side','front')
    if side not in ('front','back'):return HttpResponse(status=400)
    response=HttpResponse(svg(normalize(d.data),side,True),content_type='image/svg+xml');response['Cache-Control']='private, no-store';response['Content-Security-Policy']="default-src 'none'; style-src 'unsafe-inline'; img-src data:";return response
@never_cache
@candidate_only
@require_GET
def download(request,pk):
    d=get_object_or_404(BusinessCardDraft,pk=pk,owner=request.user);product=DigitalProduct.objects.filter(slug=SLUG).first()
    if not product or not (has_access(request.user,product) or starter_remaining(request.user, product)):return HttpResponse('Purchase business-card PDF access before downloading.',status=403)
    output = pdf(normalize(d.data))
    if not authorize_starter(request.user,product,1):return HttpResponse('No starter business card exports remain.',status=403)
    from career_mobility.product_activity import record
    record(product, 'exported', request=request)
    response=HttpResponse(output,content_type='application/pdf');response['Content-Disposition']='attachment; filename="business-card-front-and-back.pdf"';response['Cache-Control']='private, no-store';return response

@candidate_only
@require_POST
def delete(request,pk):
    get_object_or_404(BusinessCardDraft,pk=pk,owner=request.user).delete()
    return redirect(route(request,'cards'))
