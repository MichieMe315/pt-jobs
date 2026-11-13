from django.utils import timezone
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .research_library import DATASETS,records,rural_housing_references,present
from .research import fee_references
from .models import InternationalProfile

class ResearchLibraryTests(TestCase):
    def test_all_collections_render_with_pagination(self):
        for name in DATASETS:
            with self.subTest(collection=name):
                response=self.client.get(reverse('mobility_research'),{'collection':name})
                self.assertEqual(response.status_code,200)
                self.assertLessEqual(len(response.context['page'].object_list),20)
                self.assertContains(response,DATASETS[name][0])
    def test_rural_rents_are_connected_to_comparison(self):
        refs=rural_housing_references()
        self.assertGreater(len(refs),100)
        self.assertTrue(all(r['amount']>0 and r['period']=='2025' for r in refs))
        response=self.client.get(reverse('mobility_canadian'))
        self.assertContains(response,'apply-rural-current')
        self.assertEqual(len(response.context['rural_housing_references']),len(refs))
    def test_suppressed_rent_is_not_zero_or_suggested(self):
        row=next(r for r in records('housing_cmhc_rural_2025') if r['monthly_rent_cad'] is None)
        item=present('housing_cmhc_rural_2025',row)
        self.assertIn('Not available',item['measures'][0]['value'])
        for reference in rural_housing_references():
            collection,index=reference['id'].split(':')
            original=records(collection)[int(index)]
            self.assertEqual(reference['amount'],original['monthly_rent_cad'])
            if collection=='housing_cmhc_rural_2025':self.assertTrue(original['use_for_reviewed_reference'])
    def test_banff_vacancy_is_not_fabricated(self):
        rows=[r for r in records('housing_alberta_rural_2025') if r['community']=='Banff']
        self.assertTrue(rows)
        self.assertTrue(all(r['vacancy_percent'] is None for r in rows))
    def test_pt_ineligible_program_is_excluded(self):
        row=next(r for r in records('rural_incentives') if r.get('pt_eligible') is False)
        item=present('rural_incentives',row)
        self.assertFalse(item['measures'])
        self.assertIn('Excluded',item['notes'][0]['value'])
    def test_full_licensing_research_replaces_small_snapshot(self):
        self.assertEqual(len(fee_references()),len(records('licensing_fees')))
        self.assertTrue(any(r['province']=='Yukon' for r in fee_references()))
        self.assertTrue(any(r['amount_cad'] is None for r in fee_references()))
    def test_filtered_search_and_unknown_collection(self):
        r=self.client.get(reverse('mobility_research'),{'collection':'housing_alberta_rural_2025','q':'Athabasca','province':'Alberta'})
        self.assertTrue(r.context['page'].paginator.count)
        self.assertTrue(all('Athabasca' in x['title'] for x in r.context['page']))
        self.assertEqual(self.client.get(reverse('mobility_research'),{'collection':'../../settings'}).status_code,200)
    def test_international_dashboard_includes_researched_costs(self):
        user=get_user_model().objects.create_user('research-account')
        profile=InternationalProfile.objects.create(email_verified_at=timezone.now(),user=user,country_of_education='India',destination_province='Ontario',application_history='new')
        self.client.force_login(user)
        response=self.client.get(reverse('mobility_international_dashboard'))
        self.assertContains(response,'Initial application')
        self.assertContains(response,'3,950')
        self.assertEqual(self.client.get(reverse('mobility_personalized_checklist')).status_code,200)
        profile.destination_province='Quebec';profile.save()
        response=self.client.get(reverse('mobility_international_dashboard'))
        self.assertFalse(response.context['plan']['cost_examples'])
