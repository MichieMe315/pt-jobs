from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import SavedCareerPlan

class RelocationWorkspaceTests(TestCase):
    def test_requires_login(self):
        response=self.client.get(reverse("mobility_relocation_comparisons"))
        self.assertEqual(response.status_code,302)

    def test_requires_canadian_candidate(self):
        user=get_user_model().objects.create_user(username="workspace_user",password="example-pass")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("mobility_relocation_comparisons")).status_code,403)

    def test_relocation_page_public(self):
        self.assertEqual(self.client.get(reverse("mobility_canadian")).status_code,200)
