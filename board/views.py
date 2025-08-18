from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.contrib import messages

from .models import Company, Job, Application
from .forms import CompanyForm, JobForm, ApplicationForm

def home(request):
    q = request.GET.get('q','').strip()
    province = request.GET.get('province','').strip()
    jobs = Job.objects.filter(is_active=True)
    if q:
        jobs = jobs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(company__name__icontains=q) |
            Q(city__icontains=q)
        )
    if province:
        jobs = jobs.filter(province__iexact=province)
    return render(request, 'board/home.html', {'jobs': jobs[:20], 'q': q, 'province': province})

@login_required
def dashboard(request):
    profile = request.user.profile
    if profile.role == 'EMPLOYER':
        companies = Company.objects.filter(owner=request.user).annotate(num_jobs=Count('jobs'))
        jobs = Job.objects.filter(company__owner=request.user).annotate(num_apps=Count('applications'))
        return render(request, 'board/employer_dashboard.html', {'companies': companies, 'jobs': jobs})
    else:
        applications = Application.objects.filter(applicant=request.user).select_related('job','job__company')
        saved = []  # placeholder for saved jobs if you add that feature later
        return render(request, 'board/seeker_dashboard.html', {'applications': applications, 'saved': saved})

@login_required
def company_list(request):
    companies = Company.objects.filter(owner=request.user)
    return render(request, 'board/company_list.html', {'companies': companies})

@login_required
def company_create(request):
    if request.method == 'POST':
        form = CompanyForm(request.POST)
        if form.is_valid():
            company = form.save(commit=False)
            company.owner = request.user
            company.save()
            messages.success(request, 'Company created.')
            return redirect('board:company_list')
    else:
        form = CompanyForm()
    return render(request, 'board/company_form.html', {'form': form})

@login_required
def company_edit(request, pk):
    company = get_object_or_404(Company, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company updated.')
            return redirect('board:company_list')
    else:
        form = CompanyForm(instance=company)
    return render(request, 'board/company_form.html', {'form': form})

def job_list(request):
    q = request.GET.get('q','').strip()
    province = request.GET.get('province','').strip()
    jobs = Job.objects.filter(is_active=True)
    if q:
        jobs = jobs.filter(
            Q(title__icontains=q) |
            Q(description__icontains=q) |
            Q(company__name__icontains=q) |
            Q(city__icontains=q)
        )
    if province:
        jobs = jobs.filter(province__iexact=province)
    return render(request, 'board/job_list.html', {'jobs': jobs, 'q': q, 'province': province})

def job_detail(request, pk):
    job = get_object_or_404(Job, pk=pk, is_active=True)
    can_apply = request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.role == 'SEEKER'
    return render(request, 'board/job_detail.html', {'job': job, 'can_apply': can_apply})

@login_required
def job_create(request):
    if request.user.profile.role != 'EMPLOYER':
        messages.error(request, 'Only employers can post jobs.')
        return redirect('board:dashboard')

    # Limit company choices to user's companies
    if request.method == 'POST':
        form = JobForm(request.POST)
        form.fields['company'].queryset = Company.objects.filter(owner=request.user)
        if form.is_valid():
            job = form.save()
            messages.success(request, 'Job posted!')
            return redirect('board:dashboard')
    else:
        form = JobForm()
        form.fields['company'].queryset = Company.objects.filter(owner=request.user)
    return render(request, 'board/job_form.html', {'form': form})

@login_required
def job_edit(request, pk):
    job = get_object_or_404(Job, pk=pk, company__owner=request.user)
    if request.method == 'POST':
        form = JobForm(request.POST, instance=job)
        form.fields['company'].queryset = Company.objects.filter(owner=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Job updated.')
            return redirect('board:dashboard')
    else:
        form = JobForm(instance=job)
        form.fields['company'].queryset = Company.objects.filter(owner=request.user)
    return render(request, 'board/job_form.html', {'form': form})

@login_required
def job_delete(request, pk):
    job = get_object_or_404(Job, pk=pk, company__owner=request.user)
    job.delete()
    messages.success(request, 'Job deleted.')
    return redirect('board:dashboard')

@login_required
def apply_to_job(request, pk):
    job = get_object_or_404(Job, pk=pk, is_active=True)
    if request.user.profile.role != 'SEEKER':
        messages.error(request, 'Only job seekers can apply.')
        return redirect('board:job_detail', pk=pk)
    if request.method == 'POST':
        form = ApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.job = job
            app.applicant = request.user
            try:
                app.save()
                messages.success(request, 'Application submitted!')
            except Exception as e:
                messages.error(request, f'Could not submit application: {e}')
            return redirect('board:job_detail', pk=pk)
    else:
        form = ApplicationForm()
    return render(request, 'board/apply_form.html', {'form': form, 'job': job})
