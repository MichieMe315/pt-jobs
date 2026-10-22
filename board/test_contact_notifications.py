from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import SiteSettings, EmailTemplate

@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='site@example.test')
class ContactNotificationTests(TestCase):
    def setUp(self):
        SiteSettings.objects.create(contact_email='owner@example.test')

    def test_contact_reply_goes_to_sender_with_safe_html_and_plain_text(self):
        response=self.client.post(reverse('contact'),{'name':'A Visitor','email':'visitor@example.test','message':'Question <script>alert(1)</script>'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(mail.outbox),1)
        msg=mail.outbox[0]
        self.assertEqual(msg.from_email,'site@example.test')
        self.assertEqual(msg.to,['owner@example.test'])
        self.assertEqual(msg.reply_to,['visitor@example.test'])
        self.assertIn('Question',msg.body)
        self.assertNotIn('<script>',msg.alternatives[0].content)
        self.assertIn('&lt;script&gt;',msg.alternatives[0].content)

    def test_invalid_and_header_injection_do_not_send(self):
        for email,name,message in [('bad','Visitor','Hi'),('x@example.test\r\nBcc:a@b.test','Visitor','Hi'),('x@example.test','Bad\r\nName','Hi'),('x@example.test','Visitor','x'*12001)]:
            self.client.post(reverse('contact'),{'name':name,'email':email,'message':message})
        self.assertEqual(len(mail.outbox),0)

    def test_admin_template_retains_custom_copy_and_adds_review_action(self):
        from .views import send_templated_email
        EmailTemplate.objects.create(key='admin_new_employer',subject='New employer',html='<p>Custom copy {{ email }}</p>',is_enabled=True)
        sent=send_templated_email('admin_new_employer',['owner@example.test'],{'email':'clinic@example.test','review_url':'https://example.test/admin/board/employer/3/change/'})
        self.assertTrue(sent)
        self.assertIn('Custom copy',mail.outbox[0].body)
        self.assertIn('Review in admin',mail.outbox[0].alternatives[0].content)
        self.assertEqual(mail.outbox[0].reply_to,['clinic@example.test'])
        self.assertTrue(mail.outbox[0].subject.startswith('[PTJC]'))
