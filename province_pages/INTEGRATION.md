# Province SEO Pages - Integration Guide

## Overview

This package adds 10 province-specific SEO landing pages to PhysiotherapyJobsCanada.ca:

1. `/physiotherapy-jobs-ontario/`
2. `/physiotherapy-jobs-british-columbia/`
3. `/physiotherapy-jobs-alberta/`
4. `/physiotherapy-jobs-saskatchewan/`
5. `/physiotherapy-jobs-manitoba/`
6. `/physiotherapy-jobs-quebec/`
7. `/physiotherapy-jobs-nova-scotia/`
8. `/physiotherapy-jobs-new-brunswick/`
9. `/physiotherapy-jobs-newfoundland-and-labrador/`
10. `/physiotherapy-jobs-prince-edward-island/`

Each page includes:
- Unique H1, title tag, and meta description
- 400+ words of province-specific content
- Links to jobs filtered by province/city
- Schema.org structured data
- Internal linking to other province pages

---

## Integration Steps

### Step 1: Copy the App to Your Project

Copy the `province_pages/` directory to your Django project root:

```bash
# From your project root
cp -r /path/to/province_pages ./province_pages
```

---

### Step 2: Add to INSTALLED_APPS

Edit your `settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    "board",
    "province_pages",  # <-- ADD THIS
]
```

---

### Step 3: Add URL Patterns

Edit your main `urls.py` (the one shown in `urls_updated.py`):

```python
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from board.sitemaps import StaticViewSitemap, JobSitemap

sitemaps = {
    "static": StaticViewSitemap,
    "jobs": JobSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),

    # Existing app
    path("", include("board.urls")),

    # New apps (kept separate from board)
    path("marketplace/", include("marketplace.urls")),
    path("sponsor-an-international-candidate/", include("international_candidates.urls")),
    
    # Province SEO pages  # <-- ADD THIS
    path("", include("province_pages.urls")),

    # Sitemap and Robots
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(
            template_name="robots.txt",
            content_type="text/plain",
        ),
    ),
]

# Serve uploaded media in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

### Step 4: Verify Templates Directory

Ensure your `settings.py` has the templates directory configured:

```python
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # This should already exist
        "APP_DIRS": True,  # This loads templates from app directories
        # ...
    },
]
```

The `province_pages/templates/` directory will be auto-discovered via `APP_DIRS = True`.

---

### Step 5: No Migrations Required

This app has **no models** and requires **no migrations**. It's completely safe to add to production without database changes.

---

### Step 6: Optional - Update Sitemap

To include province pages in your sitemap, update `board/sitemaps.py`:

```python
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from board.models import Job


class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = "weekly"

    def items(self):
        return [
            "home",
            "job_list",
            # Province pages
            "province_ontario",
            "province_bc",
            "province_alberta",
            "province_saskatchewan",
            "province_manitoba",
            "province_quebec",
            "province_nova_scotia",
            "province_new_brunswick",
            "province_newfoundland",
            "province_pei",
        ]

    def location(self, item):
        return reverse(item)


class JobSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.9

    def items(self):
        return Job.objects.filter(is_active=True)

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)
```

---

## Testing

### Local Development

```bash
# Run development server
python manage.py runserver

# Test URLs
curl http://localhost:8000/physiotherapy-jobs-ontario/
curl http://localhost:8000/physiotherapy-jobs-alberta/
```

### Verify SEO Elements

Check that each page has:
- [ ] Unique `<title>` tag
- [ ] Unique `<meta name="description">`
- [ ] Proper `<h1>` heading
- [ ] Schema.org JSON-LD structured data
- [ ] Canonical URL
- [ ] Links to job search with province/city filters

---

## File Structure

```
province_pages/
├── __init__.py              # App init
├── urls.py                  # URL patterns for all 10 provinces
├── views.py                 # View functions with province data
├── templates/
│   └── province_pages/
│       └── province_base.html  # Reusable template
└── INTEGRATION.md           # This file
```

---

## What This App Does NOT Touch

✅ Safe - No changes to:
- Database models
- Migrations
- Authentication logic
- Payment processing
- Job posting flows
- Employer approvals
- Admin configuration
- Existing board app

---

## URL Reference

| URL Path | View Name | Province |
|----------|-----------|----------|
| `/physiotherapy-jobs-ontario/` | `province_ontario` | Ontario |
| `/physiotherapy-jobs-british-columbia/` | `province_bc` | British Columbia |
| `/physiotherapy-jobs-alberta/` | `province_alberta` | Alberta |
| `/physiotherapy-jobs-saskatchewan/` | `province_saskatchewan` | Saskatchewan |
| `/physiotherapy-jobs-manitoba/` | `province_manitoba` | Manitoba |
| `/physiotherapy-jobs-quebec/` | `province_quebec` | Quebec |
| `/physiotherapy-jobs-nova-scotia/` | `province_nova_scotia` | Nova Scotia |
| `/physiotherapy-jobs-new-brunswick/` | `province_new_brunswick` | New Brunswick |
| `/physiotherapy-jobs-newfoundland-and-labrador/` | `province_newfoundland` | Newfoundland and Labrador |
| `/physiotherapy-jobs-prince-edward-island/` | `province_pei` | Prince Edward Island |

---

## Deployment Checklist

- [ ] Copy `province_pages/` directory to project
- [ ] Add `"province_pages"` to `INSTALLED_APPS`
- [ ] Add `path("", include("province_pages.urls"))` to main `urls.py`
- [ ] Test locally at `/physiotherapy-jobs-ontario/`
- [ ] Verify all 10 province pages load
- [ ] Check SEO meta tags render correctly
- [ ] Deploy to staging
- [ ] Deploy to production
- [ ] Submit updated sitemap to Google Search Console

---

## Support

For questions about integration, refer to:
- This README
- Django documentation: https://docs.djangoproject.com/
- Your existing project structure in `urls_updated.py` and `settings_updated.py`
