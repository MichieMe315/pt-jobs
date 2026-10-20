from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import SavedCareerPlan

class RelocationWorkspaceV15Tests(TestCase):
    def test_anonymous_redirected(self):
        response = self.client.get(reverse("mobility_relocation_comparisons"))
        self.assertEqual(response.status_code, 302)

    def test_rename_cannot_access_other_users_plan(self):
        User = get_user_model()
        owner = User.objects.create_user(username="owner15", password="testpassword")
        other = User.objects.create_user(username="other15", password="testpassword")
        plan = SavedCareerPlan.objects.create(user=owner, plan_type="relocation", title="Old", inputs={"destination":"Toronto"})
        self.client.force_login(other)
        response = self.client.post(reverse("mobility_rename_relocation_plan", args=[plan.pk]), {"title":"Hijacked"})
        self.assertEqual(response.status_code, 403)
        plan.refresh_from_db()
        self.assertEqual(plan.title, "Old")
