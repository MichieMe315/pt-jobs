from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase,override_settings
from django.urls import include,path,reverse,NoReverseMatch
from .models import DigitalProduct
urlpatterns=[path('admin/',admin.site.urls),path('',include('board.urls')),path('career-resources/',include('career_mobility.release_urls'))]
@override_settings(ROOT_URLCONF=__name__)
class ProductionSurfaceAuditTests(TestCase):
 def test_product_without_editor_is_not_listed_on_storefront(self):
  u=get_user_model().objects.create_superuser('surface','surface@example.test','Private-Test-482!');self.client.force_login(u)
  p=DigitalProduct.objects.create(title='Legacy resource',slug='surface',is_published=True,price_cad=20)
  try:
   change = reverse('admin:career_mobility_digitalproduct_change',args=[p.pk])
  except NoReverseMatch:
   self.assertEqual(self.client.get(f'/admin/career_mobility/digitalproduct/{p.pk}/change/').status_code,404)
  else:
   self.assertContains(self.client.get(change),'View this product in the shop')
  self.assertNotContains(self.client.get(reverse('mobility_shop')), p.title)
 def test_public_tools_render_with_planners_disabled(self):
  for name in ['mobility_home','mobility_salary_comparison','mobility_clinic_offer_guide','mobility_research']:self.assertEqual(self.client.get(reverse(name)).status_code,200)
