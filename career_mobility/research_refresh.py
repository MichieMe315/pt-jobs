"""Official wage-table extraction, staged for review before publication."""
from html.parser import HTMLParser
from decimal import Decimal,InvalidOperation
from urllib.request import Request,urlopen
from urllib.parse import urlparse
import hashlib,json,re
from django.utils import timezone
from django.db import transaction
from .models import DataSourceReview,SalaryBenchmark,ReferenceCost
URL='https://www.jobbank.gc.ca/wagereport/occupation/18214'
ALBERTA_URL='https://regionaldashboard.alberta.ca/export/opendata/Average%20Rent/jsons'
SUPPORTED={URL,ALBERTA_URL}
class Tables(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(' '.join(' '.join(self.cell).split()));self.cell=None
        if tag=='tr' and self.row is not None:
            self.rows.append(self.row);self.row=None

def extract(body, *, include_unpublished=False):
    parser=Tables();parser.feed(body.decode('utf-8') if isinstance(body,bytes) else body)
    from .forms import PROVINCES
    rows=[];province=''
    for cells in parser.rows:
        if len(cells)<4 or cells[0] in ('ProvinceCode','Community/Area','Location'):continue
        from .research_library import CODES
        coded=len(cells)>=6 and cells[0] in CODES
        if coded:province=CODES[cells[0]] if cells[0]!='CA' else ''
        area=re.sub(r'\s+(?:Note|Footnote).*','',cells[1] if coded else cells[0]).strip()
        if area in PROVINCES:province=area
        values=[]
        for value in (cells[2:5] if coded else cells[1:4]):
            clean=re.sub(r'[$,\s]','',value)
            try:n=Decimal(clean)
            except InvalidOperation:n=None
            if n is not None and (not n.is_finite() or n<=0 or n>1000):raise ValueError('Unexpected wage value')
            values.append(n)
        if values[1] is None and not include_unpublished:continue
        low,median,high=values
        if median is not None and ((low and low>median) or (high and median>high)):raise ValueError('Wage values are out of order')
        period=re.search(r'Reference period:\s*(20\d\d(?:\s*[-–]\s*20\d\d)?)',' '.join(cells))
        rows.append({'reference_period':period.group(1) if period else 'Confirm source reference period','region':area,'province':province if area!='Canada' else '', 'low_hourly':str(low) if low is not None else None,'median_hourly':str(median) if median is not None else None,'high_hourly':str(high) if high is not None else None})
    if len(rows)<2:raise ValueError('Official wage table was not found; no figures changed')
    if len({(r['region'],r['province']) for r in rows})!=len(rows):raise ValueError('Repeated wage areas require manual review')
    text=body.decode('utf-8') if isinstance(body,bytes) else body
    period=re.search(r'20\d\d\s*[-–]\s*20\d\d',text)
    # A national page contains several reference periods; retain the period in each row.
    return rows

def extract_alberta(body):
    data=json.loads(body)
    if not isinstance(data,list):raise ValueError('Expected the Alberta municipal rent dataset')
    candidates=[]
    for r in data:
        if not isinstance(r,dict) or not any(d.get('Value')=='2 - bedroom' for d in r.get('Dimensions',[]) if isinstance(d,dict)):continue
        try:year=int(r['Period']);amount=Decimal(str(r['OriginalValue']))
        except (KeyError,ValueError,TypeError,InvalidOperation):continue
        if not amount.is_finite() or amount<=0:continue
        if amount>100000 or year<1980 or year>timezone.localdate().year+1:raise ValueError('Unexpected rent or survey year')
        city=r.get('CSD','').strip()
        if not city or len(city)>100:raise ValueError('Invalid municipality name')
        candidates.append({'city':city,'province':'Alberta','amount_cad':str(amount),'reference_period':str(year),'basis':'Municipal survey average; two-bedroom non-subsidized rental units. Historical reference, not a current asking rent.'})
    if not candidates:raise ValueError('No two-bedroom municipal rent figures were found')
    latest=max(int(r['reference_period']) for r in candidates)
    rows=[r for r in candidates if r['reference_period']==str(latest)]
    if len({r['city'] for r in rows})!=len(rows):raise ValueError('Duplicate municipality rents need review')
    return rows


def queue(source,body):
    url=source.url.rstrip('/')
    if url==URL:kind='jobbank_pt_wages';rows=extract(body,include_unpublished=True)
    elif url==ALBERTA_URL:kind='alberta_municipal_rents';rows=extract_alberta(body)
    else:raise ValueError('Structured extraction supports only registered official wage and municipal rent feeds')
    digest=hashlib.sha256(body).hexdigest()
    detail=json.dumps({'kind':kind,'source_url':source.url,'rows':rows},ensure_ascii=False)
    review=DataSourceReview.objects.filter(source=source,detected_hash=digest).first()
    created=review is None
    if created:review=DataSourceReview.objects.create(source=source,detected_hash=digest,status='pending',previous_hash=source.content_sha256,detail=detail)
    if not created and review.status=='pending' and not review.detail.lstrip().startswith('{'):
        review.detail=detail;review.save(update_fields=['detail'])
    return review

def fetch(source):
    if source.url.rstrip('/') not in SUPPORTED:raise ValueError('Choose a registered official wage or rent feed')
    req=Request(source.url,headers={'User-Agent':'PTJC research review/1.0','Accept':'text/html'})
    with urlopen(req,timeout=20) as response:
        if urlparse(response.url).hostname not in ('www.jobbank.gc.ca','jobbank.gc.ca','regionaldashboard.alberta.ca'):raise ValueError('Unexpected source redirect')
        content_type=response.headers.get('Content-Type','')
        if not any(t in content_type for t in ('text/html','application/json')) and not (source.url.rstrip('/')==ALBERTA_URL and 'application/octet-stream' in content_type):raise ValueError('Expected a supported official publication')
        body=response.read(2_000_001)
        if len(body)>2_000_000:raise ValueError('Source is too large')
    return queue(source,body)

def approve(review):
    with transaction.atomic():
        review=DataSourceReview.objects.select_for_update().get(pk=review.pk)
        if review.status!='pending':return 0
        data=json.loads(review.detail)
        kind=data.get('kind')
        expected=URL if kind=='jobbank_pt_wages' else ALBERTA_URL if kind=='alberta_municipal_rents' else None
        if not expected or data.get('source_url')!=expected or review.source.url.rstrip('/')!=expected:raise ValueError('This review has no supported official structured data')
        for row in data['rows']:
            values=dict(row)
            if kind=='jobbank_pt_wages':
                region=values.pop('region');province=values.pop('province')
                if values.get('median_hourly') is None:
                    SalaryBenchmark.objects.filter(region=region,province=province).update(is_published=False)
                    continue
                SalaryBenchmark.objects.update_or_create(region=region,province=province,defaults=dict(values,source_url=URL,verified_on=timezone.localdate(),is_published=True))
            else:
                city=values.pop('city');province=values.pop('province')
                ReferenceCost.objects.update_or_create(kind='rent',city=city,province=province,defaults=dict(values,source_url=ALBERTA_URL,verified_on=timezone.localdate(),is_published=True))
        review.status='approved';review.reviewed_at=timezone.now();review.save(update_fields=['status','reviewed_at'])
        return len(data['rows'])
