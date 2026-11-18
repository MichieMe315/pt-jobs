"""Private staff product review and explicit draft import. Never auto-publish."""
from io import BytesIO
from pathlib import Path,PurePosixPath
import zipfile,json,re,base64,posixpath
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import HttpResponse,FileResponse,Http404,HttpResponseNotAllowed
from django.shortcuts import render,get_object_or_404,redirect
from django.urls import reverse
from django.views.decorators.clickjacking import xframe_options_exempt
from .models import DigitalProduct,ProductOrder
SOURCE=Path(__file__).parent/'product_imports/PTJC-Rebuilt-Collection.zip'

def safe_response(data,kind,attachment=False,name='download'):
    r=HttpResponse(data,content_type=kind)
    r['Cache-Control']='private, no-store';r['X-Content-Type-Options']='nosniff'
    if attachment:r['Content-Disposition']='attachment; filename="'+PurePosixPath(name).name.replace('"','')+'"'
    return r

def entries(product):
    if not product.download or not product.download.storage.exists(product.download.name):return []
    with product.download.open('rb') as f:
        if not zipfile.is_zipfile(f):return [{'name':PurePosixPath(product.download.name).name,'size':product.download.size,'suffix':Path(product.download.name).suffix.lower()}]
        f.seek(0)
        with zipfile.ZipFile(f) as z:return [{'name':i.filename,'size':i.file_size,'suffix':Path(i.filename).suffix.lower()} for i in z.infolist() if not i.is_dir() and not any(p.startswith('.') or p=='..' for p in PurePosixPath(i.filename).parts) and not i.filename.startswith('/')]

def member(product,name):
    rows=entries(product);row=next((r for r in rows if r['name']==name),None)
    if not row or row['size']>25*1024*1024:raise Http404('File unavailable or too large to preview')
    with product.download.open('rb') as f:
        if zipfile.is_zipfile(f):
            f.seek(0)
            with zipfile.ZipFile(f) as z:return z.read(name)
        f.seek(0);return f.read(25*1024*1024+1)

def catalogue(request,modeladmin):
    if not modeladmin.has_view_permission(request):raise PermissionDenied
    from django.core.paginator import Paginator
    from django.db.models import Count, Q
    sort = request.GET.get('sort', 'title')
    sorts = {'title':'Name A–Z','-title':'Name Z–A','price_cad':'Price: low to high','-price_cad':'Price: high to low','-pk':'Newest products'}
    sorts['storefront_order'] = 'Shop order'
    if sort not in sorts or 'sort' not in request.GET:
        sort = 'storefront_order'
    from .shop_studios import editor_visibility, for_shop, linked_studio_products, published_journal_slugs, storefront_products
    audience = request.GET.get('audience', 'canadian')
    if audience not in ('canadian', 'international'):
        audience = 'canadian'
    base = storefront_products(modeladmin.get_queryset(request), audience)
    editors = list(for_shop(audience, include_hidden=True)) if (
        request.user.has_perm('career_mobility.view_storefrontstudio') or
        request.user.has_perm('career_mobility.change_storefrontstudio')
    ) else []
    if editors:
        linked = linked_studio_products()
        for studio in editors:
            product = linked.get(studio['key'])
            studio['status'] = editor_visibility(studio, audience, product)
            studio['linked_product'] = product
            if studio['visible'] and studio['key'] == 'printables':
                count = len(published_journal_slugs(audience))
                studio['status'] = f'Visible · {count} published journal editions' if count else 'Hidden · no published journal editions'
    from .views import shop_context
    storefront = shop_context(request, audience, catalogue=True)
    live_rows = ([{'studio': storefront['featured_resume']}] if storefront['featured_resume'] else []) + storefront['listings']
    live_urls = {}
    for row in live_rows:
        studio = row.get('studio') or {}
        product = row.get('product') or studio.get('product')
        if product:
            live_urls[product.pk] = row.get('editor_url') or studio.get('href')
    products = base.order_by('-is_published', sort, 'pk')
    q = request.GET.get('q', '').strip()[:100]
    if q:
        products = products.filter(Q(title__icontains=q) | Q(slug__icontains=q))
    category = request.GET.get('category', '').strip()[:60]
    status = request.GET.get('status', 'all')
    if category:
        products = products.filter(category=category)
    if status == 'published':
        products = products.filter(pk__in=live_urls)
    elif status == 'draft':
        products = products.filter(is_published=False)
    else:
        status = ''
    categories = base.exclude(category='').values_list('category', flat=True).distinct().order_by('category')
    counts = base.aggregate(total=Count('pk'), published=Count('pk', filter=Q(is_published=True)))
    counts['draft'] = counts['total'] - counts['published']
    page = Paginator(products, 24).get_page(request.GET.get('page'))
    for product in page:
        product.storefront_url = live_urls.get(product.pk, '')
    query = request.GET.copy()
    query.pop('page', None)
    can_import = modeladmin.has_add_permission(request)
    can_edit = modeladmin.has_change_permission(request)
    from ptjc_resumes.models import ResumeTemplate
    resume_builders = ResumeTemplate.objects.select_related('access_product').filter(
        key__in=('canadian-professional', 'international-professional')).order_by('key')
    context = dict(modeladmin.admin_site.each_context(request), title='Digital product catalogue',
        products=page, page=page, query=query.urlencode(), counts=counts, q=q, category=category, status=status,
        categories=categories, audience=audience, editors=editors, resume_builders=resume_builders, live_rows=live_rows, live_count=len(live_rows),
        sort=sort, sorts=sorts, can_import=can_import, can_edit=can_edit, can_import_resumes=can_import and can_edit)
    return render(request,'admin/career_mobility/catalogue.html',context)

def duplicates(request,modeladmin):
    if not modeladmin.has_view_permission(request):
        raise PermissionDenied
    from .catalogue_duplicates import duplicate_groups
    groups = duplicate_groups(DigitalProduct.objects.order_by('title','pk'))
    return render(request,'admin/career_mobility/catalogue_duplicates.html',{
        **modeladmin.admin_site.each_context(request),'title':'Review possible duplicate products','groups':groups,
    })


def import_resumes(request,modeladmin):
    if request.method!='POST':return HttpResponseNotAllowed(['POST'])
    if not (modeladmin.has_add_permission(request) and modeladmin.has_change_permission(request)):raise PermissionDenied
    from django.core.management import call_command,CommandError
    from django.db import transaction
    from io import StringIO
    try:
        with transaction.atomic():call_command('import_pt_resume_v6',stdout=StringIO())
    except (OSError,CommandError):
        messages.error(request,'The resume packages could not be imported. Check that all supplied product files are installed.')
    else:messages.success(request,'Resume packages are in the draft catalogue. Existing prices, files and publication settings were preserved. Review each product before publishing.')
    return redirect('admin:career_mobility_digitalproduct_catalogue')


def import_collection(request,modeladmin):
    if request.method!='POST':return HttpResponseNotAllowed(['POST'])
    if not modeladmin.has_add_permission(request):raise PermissionDenied
    if not SOURCE.is_file():raise Http404('Supplied collection not installed')
    product,created=DigitalProduct.objects.get_or_create(slug='ptjc-professional-career-collection',defaults={'title':'PTJC Professional Career Collection','category':'Career bundles','short_description':'Editable physiotherapy resumes, workbooks, business cards and practice designs.','description':'Physiotherapy-specific resume templates, examples, career and international planning workbooks, business cards, appointment cards and practice graphics. Review the file list and previews before publishing.','price_cad':0,'is_published':False})
    if created or not product.download:
        result=BytesIO()
        with zipfile.ZipFile(SOURCE) as src,zipfile.ZipFile(result,'w',zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                parts=PurePosixPath(info.filename).parts
                if info.is_dir() or any(p.startswith('.') or p=='..' for p in parts) or 'Owner-Resources' in parts or parts[-1] in ('READ-ME.txt','Research-Sources.json','documents.json'):continue
                dst.writestr('/'.join(parts[1:]),src.read(info.filename))
        product.download.save('ptjc-professional-career-collection.zip',ContentFile(result.getvalue()),save=True)
    messages.success(request,'Collection added to the draft catalogue. Review the files and set a price before publishing.')
    return redirect('admin:career_mobility_digitalproduct_review',pk=product.pk)

def review(request,pk,modeladmin):
    product=get_object_or_404(DigitalProduct,pk=pk)
    if not modeladmin.has_view_permission(request,product):raise PermissionDenied
    rows=entries(product)
    if request.method=='POST':
        if not modeladmin.has_change_permission(request,product):raise PermissionDenied
        name=request.POST.get('preview','')
        suffix=Path(name).suffix.lower()
        if suffix not in ('.png','.jpg','.jpeg','.pdf'):raise Http404
        from PIL import Image
        if suffix=='.pdf':
            try:
                import fitz
                with fitz.open(stream=member(product,name),filetype='pdf') as doc:
                    pix=doc[0].get_pixmap(matrix=fitz.Matrix(1.2,1.2));image=Image.open(BytesIO(pix.tobytes('png')))
            except (ImportError,OSError):
                messages.error(request,'PDF thumbnail rendering is unavailable on this computer. You can still open the PDF, or upload a PNG or JPEG preview image in the product settings.')
                return redirect('admin:career_mobility_digitalproduct_review',pk=pk)
            except (ValueError,RuntimeError,IndexError):raise Http404('The PDF preview could not be rendered')
        else:image=Image.open(BytesIO(member(product,name)))
        image.thumbnail((1000,1000));out=BytesIO();image.convert('RGB').save(out,format='JPEG',quality=88)
        product.preview_image.save('product-'+str(product.pk)+'.jpg',ContentFile(out.getvalue()),save=True)
        messages.success(request,'Store preview image saved.')
        return redirect('admin:career_mobility_digitalproduct_review',pk=pk)
    card_groups = {}
    for row in rows:
        match = re.fullmatch(r'(.+)-(Front|Back)\.png', PurePosixPath(row['name']).name, re.I)
        if match and product.slug.removeprefix('ptjc-') in ('business-card-design-files', 'appointment-card-designs'):
            name, side = match.groups()
            group = card_groups.setdefault(name, {'title': name.replace('-', ' '), 'sides': []})
            group['sides'].append({'name': row['name'], 'label': side.title()})
    return render(request,'admin/career_mobility/product_review.html',dict(modeladmin.admin_site.each_context(request),product=product,files=rows,card_groups=card_groups.values(),card_group_title='Appointment card designs' if product.slug.removeprefix('ptjc-') == 'appointment-card-designs' else 'Business card designs',can_change=modeladmin.has_change_permission(request,product)))

@xframe_options_exempt
def asset(request,pk,modeladmin):
    product=get_object_or_404(DigitalProduct,pk=pk)
    if not modeladmin.has_view_permission(request,product):raise PermissionDenied
    name=request.GET.get('file','');data=member(product,name);suffix=Path(name).suffix.lower()
    if request.GET.get('download'):return safe_response(data,'application/octet-stream',True,name)
    if suffix=='.pdf':
        try:
            import fitz
            doc=fitz.open(stream=data,filetype='pdf');page=int(request.GET.get('page','1'))-1
            if page<0 or page>=len(doc):raise ValueError
            pix=doc[page].get_pixmap(matrix=fitz.Matrix(1.4,1.4));result=pix.tobytes('png');doc.close()
        except (ImportError,OSError):
            return safe_response(data,'application/pdf')
        except (ValueError,RuntimeError):raise Http404('Page not found')
        return safe_response(result,'image/png')
    if suffix in ('.png','.jpg','.jpeg'):
        return safe_response(data,'image/png' if suffix=='.png' else 'image/jpeg')
    if suffix=='.html':
        text=data.decode('utf-8')
        # The editor is self-contained except for preview PNGs. Inline bounded thumbnails.
        def replace(match):
            relative=json.loads(match.group(1));path=posixpath.normpath(posixpath.join(posixpath.dirname(name),relative))
            try:
                from PIL import Image
                im=Image.open(BytesIO(member(product,path)));im.thumbnail((600,600));out=BytesIO();im.save(out,format='PNG')
                return '"preview":'+json.dumps('data:image/png;base64,'+base64.b64encode(out.getvalue()).decode())
            except (Http404,OSError):return match.group(0)
        text=re.sub(r'"preview"\s*:\s*("(?:[^"\\]|\\.)*")',replace,text)
        response=safe_response(text,'text/html; charset=utf-8')
        response['Content-Security-Policy']="sandbox allow-scripts allow-downloads; default-src 'none'; img-src data: blob:; script-src 'unsafe-inline'; style-src 'unsafe-inline'; font-src data:; connect-src 'none'"
        return response
    return safe_response(data,'application/octet-stream',True,name)

def preview_page(request,pk,modeladmin):
    product=get_object_or_404(DigitalProduct,pk=pk)
    if not modeladmin.has_view_permission(request,product):raise PermissionDenied
    name=request.GET.get('file','');data=member(product,name);suffix=Path(name).suffix.lower();pages=1;native_pdf=False
    if suffix=='.pdf':
        try:
            import fitz
            with fitz.open(stream=data,filetype='pdf') as doc:pages=len(doc)
        except (ImportError,OSError):
            native_pdf=True
        except (ValueError,RuntimeError):raise Http404('The PDF preview could not be opened')
    try:page=max(1,min(int(request.GET.get('page','1')),pages))
    except ValueError:raise Http404
    return render(request,'admin/career_mobility/asset_preview.html',dict(modeladmin.admin_site.each_context(request),product=product,name=name,suffix=suffix,page=page,pages=pages,native_pdf=native_pdf,previous=page-1,next=page+1))

def _international_planner_available():
    from django.urls import NoReverseMatch, reverse
    try:
        reverse('mobility_international')
    except NoReverseMatch:
        return False
    return True


def detail(request,slug):
    p=get_object_or_404(DigitalProduct,slug=slug,is_published=True)
    from ptjc_resumes.offers import available_offers, product_access, resume_template_for
    owned=product_access(request.user,p)
    from .starter import remaining
    from .product_activity import record
    record(p, 'viewed', request=request)
    offers = []
    if p.includes_resume_builder:
        template = resume_template_for(p)
        if template:
            offers = [offer for offer in available_offers(template, request.user) if offer['product'].pk != p.pk]
    from .shop_gallery import editor_key, editor_link, gallery
    from .print_palettes import variants
    pages, custom_gallery = gallery(p)
    international = (p.audience == 'international' or (p.audience == 'both' and (
        request.GET.get('audience') == 'international' or
        ('audience' not in request.GET and hasattr(request.user, 'international_pt_profile'))
    ))) and _international_planner_available()
    from .pricing import pricing_audience
    price = p.price_for(pricing_audience(request.user, p, 'international' if international else 'canadian'))
    from .recovered_products import CARD_DESIGN_FILES
    card_designs = [(key, name) for key, (name, _) in CARD_DESIGN_FILES.items()] if p.slug.removeprefix('ptjc-') == 'business-card-design-files' else []
    return render(request,'career_mobility/product_detail.html',{'product':p,'starter_remaining':remaining(request.user,p),'price':price,'card_designs':card_designs,'print_palettes':bool(variants(p.download)),'editable_key': editor_key(p), 'editor_url': editor_link(p, 'international' if international else 'canadian'), 'gallery_pages': pages, 'gallery_print_samples': p.download.name.endswith('.html') and not custom_gallery and not p.journal_preview, 'resume_offers':offers,'owned':owned,'file_available':bool(p.kind in ('bundle','workbook') or p.is_online_builder or p.has_editable_preview or (p.download and p.download.storage.exists(p.download.name))), 'bundle_items':p.bundle_lines.select_related('product') if p.kind=='bundle' else [],'international_shop':international,'product_base':'career_mobility/standalone.html' if international else 'career_mobility/base_tool.html'})

def product_image(request,pk):
    p=get_object_or_404(DigitalProduct,pk=pk,is_published=True)
    if not p.preview_image:raise Http404
    try:handle=p.preview_image.open('rb')
    except (OSError,FileNotFoundError):raise Http404('Preview unavailable')
    import mimetypes
    return FileResponse(handle,content_type=mimetypes.guess_type(p.preview_image.name)[0] or 'image/jpeg')


def store_image(request,pk,modeladmin):
    product=get_object_or_404(DigitalProduct,pk=pk)
    if not modeladmin.has_view_permission(request,product):raise PermissionDenied
    if not product.preview_image or not product.preview_image.storage.exists(product.preview_image.name):raise Http404
    response=FileResponse(product.preview_image.open('rb'),content_type='image/png' if product.preview_image.name.lower().endswith('.png') else 'image/jpeg')
    response['Cache-Control']='private, no-store';response['X-Content-Type-Options']='nosniff'
    return response


def product_gallery_image(request, pk, image_pk):
    from .models import ProductGalleryImage
    page = get_object_or_404(ProductGalleryImage, pk=image_pk, product_id=pk, product__is_published=True)
    try:
        handle = page.image.open("rb")
    except OSError as exc:
        raise Http404("Preview unavailable") from exc
    response = FileResponse(handle)
    response["X-Content-Type-Options"] = "nosniff"
    return response


def reorder(request, modeladmin):
    from django.db import transaction
    from .shop_gallery import resource_link

    if not modeladmin.has_change_permission(request):
        raise PermissionDenied

    def products(queryset):
        return [item for item in queryset if any(resource_link(item, a) for a in ('canadian', 'international'))]

    qs = modeladmin.get_queryset(request).filter(is_published=True).order_by('storefront_order', 'title', 'pk')
    if request.method == 'POST':
        with transaction.atomic():
            items = {str(item.pk): item for item in products(qs.select_for_update())}
            order = request.POST.getlist('product')
            if len(order) != len(items) or set(order) != set(items) or any(not modeladmin.has_change_permission(request, item) for item in items.values()):
                return HttpResponse('The product list changed. Reload before saving the order.', status=409)
            for position, pk in enumerate(order, 1):
                items[pk].storefront_order = position
            DigitalProduct.objects.bulk_update(items.values(), ['storefront_order'])
        messages.success(request, 'Shop order saved.')
        return redirect('admin:career_mobility_digitalproduct_order')
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET', 'POST'])
    def eligible_roles(product):
        roles = []
        if product.audience in ('canadian', 'both'):
            roles.extend(['jobseeker', 'employer'])
        if product.audience in ('international', 'both'):
            roles.append('international')
        if product.includes_resume_builder or 'resume' in product.slug or product.kind == 'workbook':
            roles = [role for role in roles if role != 'employer']
        return [role for role in roles if not product.eligible_accounts or role in product.eligible_accounts]

    return render(request, 'admin/career_mobility/shop_order.html', {
        **modeladmin.admin_site.each_context(request), 'title': 'Reorder shop',
        'items': [{'product': p, 'thumbnail': modeladmin.product_thumbnail(p), 'roles': eligible_roles(p)} for p in products(qs)],
    })


def activity_report(request, modeladmin):
    from datetime import timedelta
    from django.db.models import Count
    from django.utils import timezone
    from .models import ProductActivity
    from .store_eligibility import ACCOUNTS

    if not modeladmin.has_view_permission(request):
        raise PermissionDenied
    days = request.GET.get('days', 'all')
    if days not in ('all', '7', '30', '90'):
        days = 'all'
    product = request.GET.get('product', '')
    role = request.GET.get('role', '')
    qs = ProductActivity.objects.all()
    if days != 'all':
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=int(days)))
    if product.isdecimal() and len(product) < 10:
        qs = qs.filter(product_id=int(product))
    if role in dict(ACCOUNTS) or role == 'guest':
        qs = qs.filter(account=role)
    rows = qs.values('product__title', 'account', 'event').annotate(total=Count('pk')).order_by('product__title', 'account', 'event')
    return render(request, 'admin/career_mobility/product_activity.html', {
        **modeladmin.admin_site.each_context(request), 'title': 'Digital product activity', 'rows': rows,
        'days': str(days), 'role': role, 'accounts': (*ACCOUNTS, ('guest', 'Guest')),
        'selected_product': product, 'products': DigitalProduct.objects.order_by('title'),
    })


def starter_allowances(request, modeladmin):
    from django.db import transaction
    from .starter import unit

    if not modeladmin.has_view_permission(request):
        raise PermissionDenied
    qs = modeladmin.get_queryset(request).order_by('title', 'pk')

    if request.method == 'POST':
        if not modeladmin.has_change_permission(request):
            raise PermissionDenied
        with transaction.atomic():
            changes = []
            for product in qs.select_for_update():
                key = f'quantity_{product.pk}'
                if key not in request.POST or not unit(product):
                    continue
                value = request.POST[key]
                if not modeladmin.has_change_permission(request, product):
                    raise PermissionDenied
                if not value.isascii() or not value.isdecimal() or len(value) > 5 or int(value) > 32767:
                    return HttpResponse('Enter a whole number between 0 and 32767.', status=400)
                if int(value) != product.starter_quantity:
                    changes.append((product, int(value)))
            for product, value in changes:
                product.starter_quantity = value
                product.save(update_fields=['starter_quantity'])
                modeladmin.log_change(request, product, f'Starter allowance set to {value}.')
        messages.success(request, 'Starter allowances saved.')
        return redirect('admin:career_mobility_digitalproduct_allowances')
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET', 'POST'])
    return render(request, 'admin/career_mobility/starter_allowances.html', {
        **modeladmin.admin_site.each_context(request),
        'title': 'Starter allowances',
        'rows': [(product, unit(product), modeladmin.has_change_permission(request, product)) for product in qs],
        'can_edit': modeladmin.has_change_permission(request),
    })
