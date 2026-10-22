from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory
from .geolocation import visitor_country, client_ip

class GeolocationTests(SimpleTestCase):
    def setUp(self):self.factory=RequestFactory()
    @patch.dict('os.environ',{},clear=True)
    def test_direct_ipv4_and_ipv6_use_bundled_database(self):
        for ip,expected in [('8.8.8.8','United States'),('24.48.0.1','Canada'),('2001:4860:4860::8888','Canada')]:
            self.assertEqual(visitor_country(self.factory.get('/',REMOTE_ADDR=ip)),expected)
    @patch.dict('os.environ',{},clear=True)
    def test_local_private_unknown_and_forged_proxy_headers(self):
        for ip in ['127.0.0.1','::1','10.0.0.1','invalid']:
            self.assertEqual(visitor_country(self.factory.get('/',REMOTE_ADDR=ip,HTTP_X_REAL_IP='8.8.8.8')),'')
    @patch.dict('os.environ',{'RAILWAY_PROJECT_ID':'test'},clear=True)
    def test_railway_uses_real_visitor_instead_of_internal_proxy(self):
        request=self.factory.get('/',REMOTE_ADDR='10.0.0.3',HTTP_X_REAL_IP='8.8.8.8')
        self.assertEqual(client_ip(request),'8.8.8.8')
        self.assertEqual(visitor_country(request),'United States')
    @patch.dict('os.environ',{},clear=True)
    def test_missing_database_does_not_break_page(self):
        with self.settings(PTJC_GEOIP_DATABASE='/missing/not-there.mmdb'):
            self.assertEqual(visitor_country(self.factory.get('/',REMOTE_ADDR='8.8.8.8')),'')
