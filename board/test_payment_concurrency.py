"""Run these on PostgreSQL staging; SQLite cannot verify row locks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connections
from django.test import TransactionTestCase, Client, override_settings, skipUnlessDBFeature
from .models import Employer, PostingPackage, PurchasedPackage, Job, Invoice
from .payments import fulfill_checkout


@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
@skipUnlessDBFeature('has_select_for_update')
class PaymentConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('clinic')
        self.employer=Employer.objects.create(user=self.user,company_name='Clinic',is_approved=True)
        self.package=PostingPackage.objects.create(code='test',name='Test',credits=1,price_cents=9900)
    def together(self, operation):
        ready=Barrier(2)
        def run():
            close_old_connections()
            try:
                ready.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            tasks=[pool.submit(run) for _ in range(2)]
            return [task.result(timeout=30) for task in tasks]
    def publish(self, path):
        client=Client();client.force_login(get_user_model().objects.get(pk=self.user.pk))
        return client.post(path,{'title':'PT','description':'Assessment and treatment','location':'Toronto, ON','relocation_assistance':'no','action':'publish'}).status_code
    def test_two_publications_cannot_spend_one_credit_twice(self):
        p=PurchasedPackage.objects.create(employer=self.employer,package=self.package)
        self.assertEqual(self.together(lambda:self.publish('/jobs/new/')),[302,302])
        p.refresh_from_db();self.assertEqual(p.credits_remaining,0)
        self.assertEqual(Job.objects.filter(is_active=True).count(),1)
        self.assertEqual(Job.objects.filter(is_active=False).count(),1)
    def test_same_draft_concurrent_publication_consumes_once(self):
        p=PurchasedPackage.objects.create(employer=self.employer,package=self.package)
        job=Job.objects.create(employer=self.employer,title='Draft',is_active=False)
        self.assertEqual(self.together(lambda:self.publish(f'/jobs/{job.pk}/edit/')),[302,302])
        p.refresh_from_db();self.assertEqual(p.credits_remaining,0)
        job.refresh_from_db();self.assertTrue(job.is_active)
    def test_webhook_and_return_concurrent_fulfilment_grants_once(self):
        session={'id':'cs_concurrent','payment_status':'paid','amount_total':9900,'currency':'cad','metadata':{'employer_id':str(self.employer.pk),'package_id':str(self.package.pk),'terms_version':'1','credits':'1','duration_days':'30','package_expires_days':'365','amount_cents':'9900'}}
        self.together(lambda:fulfill_checkout(session))
        self.assertEqual(Invoice.objects.count(),1)
        self.assertEqual(PurchasedPackage.objects.count(),1)
