from . import catalogue
from .research_library import library as research_library
from django.urls import path
from django.views.generic import RedirectView
from . import views, country_views, planner_views
from .usage import record_usage
from .relocation_pdf import relocation_comparison_pdf
from .salary_save import save_salary_comparison, load_salary_comparison
urlpatterns=[
 path('resources/mine/',views.resource_library,name='mobility_resource_library'),
 path('resources/payment-confirmation/',views.product_success,name='mobility_product_success'),
 path('my-offer-review/',views.offer_review,name='mobility_offer_review'),

 path('international/resources/<slug:slug>/',catalogue.detail,name='mobility_product_detail_legacy'),
 path('international/resources/image/<int:pk>/',catalogue.product_image,name='mobility_product_image_legacy'),

 path('international/login/',views.InternationalLoginView.as_view(),name='mobility_international_login'),
 path('international/logout/',views.InternationalLogoutView.as_view(),name='mobility_international_logout'),
 path('international/capture/',planner_views.capture,name='mobility_international_capture'),

 path("research/",research_library,name="mobility_research"),
 path("international/save/",planner_views.save_answers,name="mobility_international_save"),
 path("international/preview/",planner_views.preview,name="mobility_international_preview"),
    path('salary-vs-split/usage/', record_usage, name='mobility_salary_usage'),
 path("salary-comparison/report.pdf",views.salary_comparison_pdf,name="mobility_salary_comparison_pdf"),
 path("",views.home,name="mobility_home"),
 path("shop/international/",views.shop,{"audience":"international"},name="mobility_international_shop"),
 path("shop/canadian/",views.shop,{"audience":"canadian"},name="mobility_canadian_shop"),
 path('international/',views.international,name='mobility_international'),
 path('international/plan/',views.international,name='mobility_international_plan'),
 path('international/countries/<slug:slug>/',country_views.country_page,name='mobility_country'),
 path('international/countries/<slug:slug>/resources/',country_views.country_resources,name='mobility_country_resources'),
 path('international/countries/<slug:slug>/checklist.pdf',country_views.country_guide,name='mobility_country_guide'),
 path("international/register/",views.signup,name="mobility_international_signup"),
 path("international/dashboard/",views.dashboard,name="mobility_international_dashboard"),
 path("international/profile/update/",views.update_international_profile,name="mobility_international_profile_update"),
 path("canadian/report.pdf",relocation_comparison_pdf,name="mobility_relocation_pdf"),
 path("canadian/",views.canadian,name="mobility_canadian"),
 path("canadian/comparisons/",views.relocation_comparisons,name="mobility_relocation_comparisons"),
 path("canadian/comparisons/<int:pk>/rename/",views.rename_relocation_plan,name="mobility_rename_relocation_plan"),
 path("canadian/full/",views.canadian_full,name="mobility_canadian_full"),
 path("salary-vs-split/",views.salary_comparison,name="mobility_salary_comparison"),
 path("salary-comparison/",RedirectView.as_view(pattern_name="mobility_salary_comparison",permanent=True)),
 path("salary-comparison/save/",views.save_plan,name="mobility_save_plan"),
 path("salary-vs-split/save/",save_salary_comparison,name="mobility_salary_save"),
 path("salary-vs-split/saved/<int:pk>/",load_salary_comparison,name="mobility_salary_load"),
 path("my-plans/",views.my_plans,name="mobility_my_plans"),
 path("my-plans/<int:pk>/pdf/",views.plan_pdf,name="mobility_plan_pdf"),
 path("my-plans/<int:pk>/delete/",views.delete_plan,name="mobility_delete_plan"),
 path("salary-comparison/clinic-offer-guide/",views.clinic_offer_guide,name="mobility_clinic_offer_guide"),
 path("international/checklist/toggle/",views.checklist_toggle,name="mobility_checklist_toggle"),
 path("international/checklist.pdf",views.personalized_checklist,name="mobility_personalized_checklist"),
 path("international/product/<int:pk>/checkout/",views.product_checkout,name="mobility_product_checkout"),
 path("stripe/mobility-webhook/",views.mobility_stripe_webhook,name="mobility_stripe_webhook"),
 path("international/download/<int:pk>/",views.product_download,name="mobility_product_download"),
]

from .international_auth import urlpatterns as international_account_patterns
urlpatterns += international_account_patterns

from django.urls import include as resume_include
urlpatterns.insert(0, path("international/resume/", resume_include("ptjc_resumes.urls")))

from .email_verification import urlpatterns as verification_patterns
urlpatterns += verification_patterns

urlpatterns += [path("canadian/resume/", resume_include("ptjc_resumes.canadian_urls", namespace="ptjc_canadian_legacy"))]

from .preview_urls import urlpatterns as public_preview_patterns
urlpatterns += public_preview_patterns

from .shop_urls import urlpatterns as shop_patterns
urlpatterns += shop_patterns
