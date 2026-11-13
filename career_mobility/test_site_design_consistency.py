from html.parser import HTMLParser
from urllib.parse import urlsplit
from django.test import TestCase, override_settings
from django.urls import resolve, Resolver404, reverse
from django.contrib.staticfiles import finders


class PageAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in ("script", "img") and attrs.get("src"):
            self.assets.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.assets.append(attrs["href"])


@override_settings(SECURE_SSL_REDIRECT=False, CAREER_TOOLS_PREVIEW=True)
class SiteDesignConsistencyTests(TestCase):
    def test_public_entry_pages_and_assets(self):
        names = [
            "home", "job_list", "employer_list", "about", "contact", "terms", "login", "jobseeker_signup",
            "mobility_home", "mobility_shop", "mobility_salary_comparison", "mobility_clinic_offer_guide",
            "mobility_international", "mobility_international_login", "mobility_international_signup",
            "mobility_try_cards", "ptjc_resumes:start", "ptjc_canadian_resumes:canadian_start",
        ]
        for name in names:
            with self.subTest(page=name):
                response = self.client.get(reverse(name), follow=True)
                self.assertEqual(response.status_code, 200)
                page = PageAssets()
                page.feed(response.content.decode())
                for path in page.assets:
                    if path.startswith("/static/"):
                        self.assertTrue(finders.find(urlsplit(path).path.removeprefix("/static/")), path)
                for path in page.links:
                    if path.startswith("/") and not path.startswith("//"):
                        try:
                            resolve(urlsplit(path).path)
                        except Resolver404:
                            self.fail(f"{name}: unresolved link {path}")

    def test_journal_pages_are_branded_and_configured(self):
        from .editable_products import JOURNALS
        for key in JOURNALS:
            response = self.client.get(reverse("mobility_editable_preview", args=[key]))
            self.assertContains(response, "PTJC")
            self.assertNotContains(response, "Digital Design Studio")
            self.assertContains(response, "Physiotherapy Jobs Canada")
            self.assertContains(response, "<iframe")
            response = self.client.get(reverse("mobility_editable_preview", args=[key]), {"editor_frame": "1"})
            self.assertContains(response, '"worksheets":')
            self.assertContains(response, 'id="page-nav"')
            self.assertContains(response, 'id="get-template"')
