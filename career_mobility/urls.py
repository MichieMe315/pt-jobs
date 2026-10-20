from django.urls import path
from django.views.generic import RedirectView
from . import views
from .relocation_pdf import relocation_comparison_pdf
from .salary_save import save_salary_comparison, load_salary_comparison
urlpatterns=[
 path("salary-comparison/report.pdf",views.salary_comparison_pdf,name="mobility_salary_comparison_pdf"),
 path("",views.home,name="mobility_home"),
 path("shop/",views.shop,name="mobility_shop"),
 path("international/",views.international,name="mobility_international"),
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
