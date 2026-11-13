"""Staff-only interactive product preview; never creates customer drafts or orders."""
import json
from django.core.exceptions import PermissionDenied,ValidationError
from django.http import HttpResponse,JsonResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.utils import timezone
from .models import DigitalProduct

def preview(request,pk,modeladmin,pdf=False):
    product=get_object_or_404(DigitalProduct,pk=pk)
    if not modeladmin.has_view_permission(request,product):raise PermissionDenied
    if product.includes_card_builder:return card_preview(request,product,pdf)
    if product.has_editable_preview and request.method == 'GET' and not pdf:
        from .shop_gallery import editor_key
        from .editable_products import configured_document
        response = HttpResponse(configured_document(editor_key(product), demo=True, extra={
            'shopUrl': reverse('admin:career_mobility_digitalproduct_change', args=[pk]),
            'shopLabel': 'Back to product settings',
        }), content_type='text/html; charset=utf-8')
        response['Content-Security-Policy'] = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; form-action 'none'; frame-ancestors 'none'"
        response['Cache-Control'] = 'private, no-store'
        return response
    if not product.includes_resume_builder:return redirect('admin:career_mobility_digitalproduct_review',pk=pk)
    from ptjc_resumes.schema import normalize,completion_errors,EXAMPLE,PROVINCES,PATHWAYS,REGISTRATION,ASSESSMENT,PET,EXAM,SOURCES,DEFAULT_ORDER
    from ptjc_resumes.pdf import render_pdf
    if len(request.body)>160000:return JsonResponse({'error':'Preview data exceeds the permitted size.'},status=413)
    data=normalize(EXAMPLE)
    if request.method=='POST':
        try:
            raw=json.loads(request.body);data=normalize(raw.get('data'))
            if not isinstance(raw.get('revision'),int):raise ValidationError('Invalid preview request.')
        except (ValueError,AttributeError,ValidationError):return JsonResponse({'error':'Check the preview fields.'},status=400)
        if not pdf:return JsonResponse({'revision':raw['revision']+1,'saved_at':timezone.now().isoformat(),'completion_errors':completion_errors(data)})
    if pdf:
        response=HttpResponse(render_pdf(data,preview=True,example=True),content_type='application/pdf');response['Content-Disposition']='inline; filename="resume-product-preview.pdf"';response['Cache-Control']='private, no-store';return response
    bootstrap={'data':data,'title':'Fictional product preview','revision':1,'save_url':reverse('admin:career_mobility_digitalproduct_demo',args=[pk]),'preview_url':reverse('admin:career_mobility_digitalproduct_demo_pdf',args=[pk]),'download_url':'','paid':False,'demo':True,'choices':{'destination':PROVINCES,'pathway':PATHWAYS,'canadian_registration':REGISTRATION,'assessment':ASSESSMENT,'pet':PET,'exam':EXAM},'sources':SOURCES,'order':DEFAULT_ORDER}
    response=render(request,'ptjc_resumes/editor.html',{'draft':{'title':'Fictional product preview'},'product':product,'bootstrap':bootstrap,'paid':False,'staff_demo':True});response['Cache-Control']='private, no-store';return response


def card_preview(request,product,is_pdf=False):
    from ptjc_resumes.cards import MAX_CARD_BODY,normalize,svg,pdf as make_pdf
    if request.method == 'POST' and len(request.body) > MAX_CARD_BODY:
        return JsonResponse({'error': 'Card data is too large.'}, status=413)
    sample=normalize({'name':'Alex Morgan','role':'Physiotherapy graduate','organization':'Professional networking','email':'alex@example.test','education_country':'Philippines','background':'Outpatient rehabilitation experience','status':'Not currently registered in Canada','initials':'AM'})
    if request.method=='POST':
        if len(request.body)>15000:return JsonResponse({'error':'Card data is too large.'},status=413)
        try:sample=normalize(json.loads(request.body)['data'])
        except (ValueError,KeyError,TypeError,ValidationError):return JsonResponse({'error':'Check the card fields.'},status=400)
        if request.GET.get('side') in ('front','back'):
            response=HttpResponse(svg(sample,request.GET['side'],True),content_type='image/svg+xml');response['Cache-Control']='private, no-store';return response
        if is_pdf:return HttpResponse(make_pdf(sample,True),content_type='application/pdf')
        return JsonResponse({'revision':1})
    url=reverse('admin:career_mobility_digitalproduct_demo',args=[product.pk])
    cfg={'data':sample,'revision':1,'demo':True,'save_url':url,'preview_url':url,'download_url':reverse('admin:career_mobility_digitalproduct_demo_pdf',args=[product.pk])}
    return render(request,'ptjc_resumes/card_editor.html',{'draft':{'title':'Fictional example'},'product':product,'paid':False,'bootstrap':cfg,'staff_demo':True})
