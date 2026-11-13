from .research_library import library as research_library
"""First public release: calculator, private salary records and resource index only."""
from django.urls import path
from django.views.generic import RedirectView
from . import views
from .usage import record_usage
from .salary_save import save_salary_comparison, load_salary_comparison

urlpatterns = [
    # Accept signed deliveries even when new purchases are disabled.
    path('stripe/mobility-webhook/', views.mobility_stripe_webhook, name='mobility_stripe_webhook'),
 path('my-offer-review/',views.offer_review,name='mobility_offer_review'),

 path("research/",research_library,name="mobility_research"),
    path("salary-comparison/clinic-offer-guide/",views.clinic_offer_guide,name="mobility_clinic_offer_guide"),
    path('salary-vs-split/usage/', record_usage, name='mobility_salary_usage'),
    path('', views.home, name='mobility_home'),
    path('salary-vs-split/', views.salary_comparison, name='mobility_salary_comparison'),
    path('salary-comparison/', RedirectView.as_view(pattern_name='mobility_salary_comparison', permanent=True)),
    path('salary-vs-split/save/', save_salary_comparison, name='mobility_salary_save'),
    path('salary-comparison/save/', save_salary_comparison, name='mobility_save_plan'),
    path('salary-vs-split/saved/<int:pk>/', load_salary_comparison, name='mobility_salary_load'),
    path('salary-comparison/report.pdf', views.salary_comparison_pdf, name='mobility_salary_comparison_pdf'),
    path('my-plans/<int:pk>/pdf/', views.plan_pdf, name='mobility_plan_pdf'),
]

from .international_activity import enabled
if enabled():
    from .international_urls import urlpatterns as international_patterns
    urlpatterns += international_patterns

from .preview_urls import urlpatterns as public_preview_patterns
urlpatterns += public_preview_patterns

from .shop_urls import urlpatterns as shop_patterns
urlpatterns += shop_patterns

if not enabled():
    from django.urls import include
    urlpatterns += [path("canadian/resume/", include("ptjc_resumes.canadian_urls", namespace="ptjc_canadian_legacy"))]
