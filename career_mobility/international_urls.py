from .international_jobs import job_feed
from . import catalogue
from django.urls import path
from . import views, country_views, planner_views
urlpatterns=[
 path("international/jobs/", job_feed, name="mobility_international_jobs"),
 path('resources/mine/',views.resource_library,name='mobility_resource_library'),
 path('resources/payment-confirmation/',views.product_success,name='mobility_product_success'),
 path('international/resources/<slug:slug>/',catalogue.detail,name='mobility_product_detail_legacy'),
 path('international/resources/image/<int:pk>/',catalogue.product_image,name='mobility_product_image_legacy'),

 path('international/login/',views.InternationalLoginView.as_view(),name='mobility_international_login'),
 path('international/logout/',views.InternationalLogoutView.as_view(),name='mobility_international_logout'),
 path('international/capture/',planner_views.capture,name='mobility_international_capture'),

 path("international/save/",planner_views.save_answers,name="mobility_international_save"),
 path("international/preview/",planner_views.preview,name="mobility_international_preview"),
 path('international/',views.international,name='mobility_international'),
 path('international/plan/',views.international,name='mobility_international_plan'),
 path('international/countries/<slug:slug>/',country_views.country_page,name='mobility_country'),
 path('international/countries/<slug:slug>/resources/',country_views.country_resources,name='mobility_country_resources'),
 path('international/countries/<slug:slug>/checklist.pdf',country_views.country_guide,name='mobility_country_guide'),
 path('international/register/',views.signup,name='mobility_international_signup'),
 path('international/dashboard/',views.dashboard,name='mobility_international_dashboard'),
 path('international/profile/update/',views.update_international_profile,name='mobility_international_profile_update'),
 path('international/checklist/toggle/',views.checklist_toggle,name='mobility_checklist_toggle'),
 path('international/checklist.pdf',views.personalized_checklist,name='mobility_personalized_checklist'),
 path('shop/international/',views.shop,{'audience':'international'},name='mobility_international_shop'),
 path('shop/canadian/',views.shop,{'audience':'canadian'},name='mobility_canadian_shop'),
 path('international/product/<int:pk>/checkout/',views.product_checkout,name='mobility_product_checkout'),
 path('international/download/<int:pk>/',views.product_download,name='mobility_product_download'),
]

from .international_auth import urlpatterns as international_account_patterns
urlpatterns += international_account_patterns

from django.urls import include as resume_include
urlpatterns.insert(0, path("international/resume/", resume_include("ptjc_resumes.urls")))

from .email_verification import urlpatterns as verification_patterns
urlpatterns += verification_patterns

urlpatterns += [path("canadian/resume/", resume_include("ptjc_resumes.canadian_urls", namespace="ptjc_canadian_legacy"))]
