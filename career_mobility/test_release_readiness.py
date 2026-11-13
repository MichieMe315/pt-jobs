from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import call_command,CommandError
from django.test import TestCase,override_settings
from career_mobility.models import DigitalProduct,ProductOrder

@override_settings(DEBUG=True,ALLOWED_HOSTS=['testserver'],CAREER_TOOLS_PREVIEW=True,SESSION_COOKIE_SECURE=False,CSRF_COOKIE_SECURE=False)
class ReleaseReadinessTests(TestCase):
 def test_readiness_never_creates_users_or_changes_products(self):
  users=get_user_model().objects.count();products=list(DigitalProduct.objects.values());out=StringIO()
  with patch('career_mobility.management.commands.check_career_tools.stripe_key',return_value=''),patch('career_mobility.management.commands.check_career_tools.webhook_secret',return_value=''):
   call_command('check_career_tools',stdout=out)
  self.assertIn('Paid-launch configuration: NOT READY',out.getvalue());self.assertEqual(get_user_model().objects.count(),users);self.assertEqual(list(DigitalProduct.objects.values()),products)
 def test_admin_login_verification_preserves_password_and_permissions(self):
  User=get_user_model();user=User.objects.create_superuser('local-admin-check','check@example.test','Only-Test-482!');
  from django.contrib.auth.hashers import PBKDF2PasswordHasher
  user.password=PBKDF2PasswordHasher().encode('Only-Test-482!','old-test-salt',iterations=1000);user.save();original=user.password;out=StringIO()
  with patch('builtins.input',return_value=user.email),patch('career_mobility.management.commands.check_career_tools.getpass',return_value='Only-Test-482!'):
   call_command('check_career_tools',admin_login=True,stdout=out)
  self.assertIn('Admin credentials accepted',out.getvalue());user.refresh_from_db();self.assertEqual(user.password,original);self.assertTrue(user.is_superuser)
 def test_wrong_password_does_not_reset_or_create_an_account(self):
  User=get_user_model();user=User.objects.create_superuser('wrong-password-check','wrong@example.test','Only-Test-482!');original=user.password
  with patch('builtins.input',return_value=user.username),patch('career_mobility.management.commands.check_career_tools.getpass',return_value='wrong'),self.assertRaises(CommandError):
   call_command('check_career_tools',admin_login=True,stdout=StringIO())
  user.refresh_from_db();self.assertEqual(user.password,original);self.assertEqual(User.objects.count(),1)
