from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from .models import Employer,JobSeeker
@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ProfileApprovalTests(TestCase):
 def test_profile_buttons_and_idempotent_approval(self):
  staff=get_user_model().objects.create_superuser('approval-admin','admin@example.test','Test-Only-481!');self.client.force_login(staff)
  for model in (Employer,JobSeeker):
   user=get_user_model().objects.create_user(model.__name__,email=model.__name__+'@example.test');obj=model.objects.create(user=user,is_approved=False)
   name='admin:board_'+model._meta.model_name
   self.assertContains(self.client.get(reverse(name+'_change',args=[obj.pk])),'Approve saved profile')
   with self.captureOnCommitCallbacks(execute=True):self.client.post(reverse(name+'_approve_profile',args=[obj.pk]))
   obj.refresh_from_db();self.assertTrue(obj.is_approved);self.assertTrue(obj.login_active);count=len(mail.outbox)
   with self.captureOnCommitCallbacks(execute=True):self.client.post(reverse(name+'_approve_profile',args=[obj.pk]))
   self.assertEqual(len(mail.outbox),count);self.assertEqual(self.client.get(reverse(name+'_approve_profile',args=[obj.pk])).status_code,405)
