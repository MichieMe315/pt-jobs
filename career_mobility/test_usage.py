import json
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import CalculatorUsageEvent


@override_settings(ALLOWED_HOSTS=['testserver'], EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CalculatorUsageTests(TestCase):
    def setUp(self):
        self.url = reverse('mobility_salary_usage')
        self.page = str(uuid.uuid4())

    def post(self, event='salary_calculator_view', **extra):
        return self.client.post(self.url, json.dumps({'event': event, 'page_id': self.page, 'event_id': str(uuid.uuid4()), **extra}), content_type='application/json')

    def test_anonymous_events_deduplicated_and_cookie_has_privacy_flags(self):
        for event in ['salary_calculator_view', 'salary_calculator_start', 'salary_comparison_complete']:
            self.assertTrue(self.post(event).json()['recorded'])
            self.assertFalse(self.post(event).json()['recorded'])
        self.assertEqual(CalculatorUsageEvent.objects.count(), 3)
        self.assertEqual(CalculatorUsageEvent.objects.values('session_hash').distinct().count(), 1)
        cookie = self.post().cookies['ptjc_calculator_session']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['path'], '/career-resources/')
        self.assertEqual(int(cookie['max-age']), 1800)
        self.assertIn('no-store', self.post()['Cache-Control'])

    def test_success_actions_count_separately_but_retries_do_not(self):
        for event in ['salary_pdf_download', 'salary_comparison_saved']:
            data={'event': event, 'page_id': self.page, 'event_id': str(uuid.uuid4())}
            for _ in range(2):
                self.assertEqual(self.client.post(self.url, json.dumps(data), content_type='application/json').status_code, 200)
            self.post(event)
        self.assertEqual(CalculatorUsageEvent.objects.count(), 4)

    def test_rejects_extra_financial_fields_malformed_and_oversized_events(self):
        for body in ['{}', '[]', '{', json.dumps({'event': 'anything'}), 'x'*513]:
            self.assertEqual(self.client.post(self.url, body, content_type='application/json').status_code, 400)
        self.assertEqual(self.post(salary=120000).status_code, 400)
        self.assertEqual(self.post(page_id='not-a-uuid').status_code, 400)
        self.assertEqual(CalculatorUsageEvent.objects.count(), 0)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    @override_settings(DEBUG=False)
    def test_production_cookie_is_secure(self):
        response = self.post()
        self.assertTrue(response.cookies['ptjc_calculator_session']['secure'])
        self.assertEqual(len(CalculatorUsageEvent.objects.first().session_hash), 64)

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        body=json.dumps({'event':'salary_calculator_view', 'page_id':self.page, 'event_id':str(uuid.uuid4())})
        self.assertEqual(client.post(self.url, body, content_type='application/json').status_code, 403)
        response=client.get(reverse('mobility_salary_comparison'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.post(self.url, body, content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 200)

    def test_staff_and_privacy_signals_are_excluded(self):
        data=json.dumps({'event':'salary_calculator_view','page_id':self.page,'event_id':str(uuid.uuid4())})
        for headers in [{'HTTP_DNT':'1'}, {'HTTP_SEC_GPC':'1'}]:
            self.assertFalse(self.client.post(self.url, data, content_type='application/json', **headers).json()['recorded'])
        self.client.force_login(get_user_model().objects.create_user('staff', is_staff=True))
        self.assertFalse(self.post().json()['recorded'])
        self.assertEqual(CalculatorUsageEvent.objects.count(), 0)

    def test_cookie_tampering_does_not_choose_session_hash(self):
        self.post()
        first=CalculatorUsageEvent.objects.first().session_hash
        self.client.cookies['ptjc_calculator_session']='chosen-session'
        self.page=str(uuid.uuid4())
        self.post()
        self.assertEqual(CalculatorUsageEvent.objects.values('session_hash').distinct().count(), 2)
        self.assertNotEqual(first, CalculatorUsageEvent.objects.first().session_hash)

    def test_per_session_cap(self):
        self.post()
        session=CalculatorUsageEvent.objects.first().session_hash
        CalculatorUsageEvent.objects.bulk_create([CalculatorUsageEvent(event_id=uuid.uuid4(), page_id=uuid.uuid4(), session_hash=session,event='salary_pdf_download') for _ in range(119)])
        self.assertEqual(self.post('salary_pdf_download').status_code,429)
        self.assertEqual(CalculatorUsageEvent.objects.count(),120)

    def test_admin_permission_daily_totals_and_date_filters(self):
        url=reverse('admin:career_mobility_calculatorusageevent_changelist')
        self.assertEqual(self.client.get(url).status_code, 302)
        staff=get_user_model().objects.create_user('reporter',is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code,403)
        staff.user_permissions.add(Permission.objects.get(content_type__app_label='career_mobility',codename='view_calculatorusageevent'))
        today=timezone.localdate()
        for ago in [0, 3, 20, 40]:
            event=CalculatorUsageEvent.objects.create(event_id=uuid.uuid4(),page_id=uuid.uuid4(),session_hash='same-session',event='salary_calculator_view')
            moment=timezone.now()-timedelta(days=ago)
            CalculatorUsageEvent.objects.filter(pk=event.pk).update(created_at=moment)
        for days, expected in [(1,1),(7,2),(30,3)]:
            response=self.client.get(url, {'days':days})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context_data['cards'][0]['value'],expected)
            self.assertEqual(response.context_data['sessions'],1)
            self.assertEqual(len(response.context_data['rows']),days)
            from django.contrib.staticfiles.finders import find
            if find('board/admin-shell.css'):
                self.assertContains(response,'board/admin-shell.css')
            self.assertNotContains(response,'same-session')
        response=self.client.get(url,{'days':'invalid'})
        self.assertEqual(response.context_data['days'],30)
        self.assertContains(self.client.get('/admin/'),'Calculator usage')
        self.assertEqual(self.client.get(url+'add/').status_code,403)

    def test_storage_outage_is_nonfatal_and_collects_no_payload(self):
        from unittest.mock import patch
        from django.db import OperationalError
        with patch('career_mobility.usage.CalculatorUsageEvent.objects.filter',side_effect=OperationalError('offline')):
            self.assertEqual(self.post().status_code,503)
        self.assertEqual(CalculatorUsageEvent.objects.count(),0)

    def test_country_is_server_detected_and_client_cannot_choose_it(self):
        from unittest.mock import patch
        with patch('career_mobility.geolocation.visitor_country',return_value='Canada'):
            self.post()
        self.assertEqual(CalculatorUsageEvent.objects.get().country,'Canada')
        self.assertEqual(self.post('salary_calculator_start',country='India').status_code,400)
        self.assertNotContains(self.client.get(reverse('mobility_salary_comparison')),'usage-country')

    def test_readable_report_url_requires_permission(self):
        url=reverse('calculator_usage_report')
        self.assertEqual(url,'/admin/calculator-usage/')
        self.assertEqual(self.client.get(url).status_code,302)
        user=get_user_model().objects.create_superuser('readable-report','report@example.test','TestOnly123!')
        self.client.force_login(user)
        self.assertContains(self.client.get(url),'Calculator usage')

    def test_live_network_country_is_automatic_and_ip_is_not_persisted(self):
        data={'event':'salary_calculator_view','page_id':self.page,'event_id':str(uuid.uuid4())}
        response=self.client.post(self.url,json.dumps(data),content_type='application/json',REMOTE_ADDR='24.48.0.1')
        self.assertEqual(response.status_code,200)
        event=CalculatorUsageEvent.objects.get()
        self.assertEqual(event.country,'Canada')
        self.assertNotIn('24.48.0.1',str(CalculatorUsageEvent.objects.values().get()))
