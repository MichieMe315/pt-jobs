from datetime import timedelta
import os
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db.models import Exists,OuterRef,Q
from django.shortcuts import render
from django.utils import timezone
from .models import Employer,Invoice,Job

def outstanding_paid_employers():
 today=timezone.localdate()
 payments=Invoice.objects.filter(employer_id=OuterRef('pk'),status='paid',order_date__gte=timezone.now()-timedelta(days=90))
 live=Job.objects.filter(employer_id=OuterRef('pk'),is_active=True).filter(Q(expiry_date__isnull=True)|Q(expiry_date__gte=today))
 return Employer.objects.annotate(recent_payment=Exists(payments),has_live_job=Exists(live)).filter(recent_payment=True,has_live_job=False,credits__gt=0).order_by('company_name')

@staff_member_required
def paid_postings(request):
 if not (request.user.has_perm('board.view_employer') and request.user.has_perm('board.view_invoice')):raise PermissionDenied
 from django.contrib import admin
 rows=[]
 for e in outstanding_paid_employers()[:150]:
  rows.append({'employer':e,'jobs':Job.objects.filter(employer=e).order_by('-posting_date','-pk'),'invoice':Invoice.objects.filter(employer=e,status='paid').order_by('-order_date').first()})
 context=admin.site.each_context(request);context.update(title='Paid employers with no published job',rows=rows,deployed_commit=os.environ.get('RAILWAY_GIT_COMMIT_SHA','Local development'))
 return render(request,'admin/board/paid_postings.html',context)
