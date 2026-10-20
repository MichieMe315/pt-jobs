"""First public release: calculator, private salary records and resource index only."""
from django.urls import path
from django.views.generic import RedirectView
from . import views
from .salary_save import save_salary_comparison, load_salary_comparison

urlpatterns = [
    path('', views.home, name='mobility_home'),
    path('salary-vs-split/', views.salary_comparison, name='mobility_salary_comparison'),
    path('salary-comparison/', RedirectView.as_view(pattern_name='mobility_salary_comparison', permanent=True)),
    path('salary-vs-split/save/', save_salary_comparison, name='mobility_salary_save'),
    path('salary-comparison/save/', save_salary_comparison, name='mobility_save_plan'),
    path('salary-vs-split/saved/<int:pk>/', load_salary_comparison, name='mobility_salary_load'),
    path('salary-comparison/report.pdf', views.salary_comparison_pdf, name='mobility_salary_comparison_pdf'),
    path('my-plans/<int:pk>/pdf/', views.plan_pdf, name='mobility_plan_pdf'),
]
