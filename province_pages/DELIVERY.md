# Province SEO Pages - Delivery Package

**Date:** 2026-05-08  
**Project:** PhysiotherapyJobsCanada.ca  
**Branch:** `feature/province-seo-pages`

---

## Files Delivered

### App Code

| File | Path | Purpose |
|------|------|---------|
| `__init__.py` | `/province_pages/__init__.py` | App initialization |
| `urls.py` | `/province_pages/urls.py` | URL routing for 10 province pages |
| `views.py` | `/province_pages/views.py` | View functions with province data (448 lines) |
| `province_base.html` | `/province_pages/templates/province_pages/` | Reusable template |
| `INTEGRATION.md` | `/province_pages/INTEGRATION.md` | Integration guide |

---

## Province Pages Created

| URL Path | Province | Word Count* |
|----------|----------|-------------|
| `/physiotherapy-jobs-ontario/` | Ontario | ~500+ |
| `/physiotherapy-jobs-british-columbia/` | British Columbia | ~500+ |
| `/physiotherapy-jobs-alberta/` | Alberta | ~500+ |
| `/physiotherapy-jobs-saskatchewan/` | Saskatchewan | ~500+ |
| `/physiotherapy-jobs-manitoba/` | Manitoba | ~500+ |
| `/physiotherapy-jobs-quebec/` | Quebec | ~500+ |
| `/physiotherapy-jobs-nova-scotia/` | Nova Scotia | ~500+ |
| `/physiotherapy-jobs-new-brunswick/` | New Brunswick | ~500+ |
| `/physiotherapy-jobs-newfoundland-and-labrador/` | Newfoundland and Labrador | ~500+ |
| `/physiotherapy-jobs-prince-edward-island/` | Prince Edward Island | ~500+ |

*Each page includes unique introductory paragraphs (2-3 paragraphs), plus employer lists, city information, and certification details.

---

## SEO Features Included

### Per-Page Elements
- ✅ Unique H1 heading
- ✅ Unique `<title>` tag (60-70 characters)
- ✅ Unique meta description (150-160 characters)
- ✅ Schema.org JSON-LD structured data (CollectionPage + ItemList)
- ✅ Canonical URL
- ✅ Open Graph tags

### Content Elements
- ✅ Province-specific career information
- ✅ Major cities with search links
- ✅ Common work settings
- ✅ Major employers in each province
- ✅ Certification/registration requirements
- ✅ Salary range information (not claims)
- ✅ Internal linking between province pages
- ✅ Links to job board with filters

### Technical
- ✅ Extends existing `base.html` template
- ✅ Uses existing `home` and `job_alert_signup` URL names
- ✅ No database models → no migrations needed
- ✅ No auth/payment logic touched
- ✅ No admin changes
- ✅ Clean, semantic HTML
- ✅ Bootstrap 5 styling (matches existing site)

---

## What Was NOT Modified

These critical systems remain untouched:
- Payment logic
- Authentication/authorization
- Job posting flows
- Employer approval system
- Admin configuration
- Database models
- Existing `board` app
- Marketplace app
- International candidates app

---

## Integration Instructions

### 1. Copy Files

Copy the entire `province_pages/` directory to your Django project root:

```bash
cp -r province_pages /path/to/your/project/
```

### 2. Update settings.py

Add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    "province_pages",
]
```

### 3. Update urls.py

Add the include line to your main `urls.py` (as shown in `urls_updated.py`):

```python
urlpatterns = [
    # ... existing paths ...
    path("", include("province_pages.urls")),
]
```

### 4. Test

```bash
python manage.py runserver
# Visit: http://localhost:8000/physiotherapy-jobs-ontario/
```

---

## Expected URLs After Deployment

```
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-ontario/
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-british-columbia/
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-alberta/
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-saskatchewan/
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-manitoba/
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-quebec/
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-nova-scotia/
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-new-brunswick/
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-newfoundland-and-labrador/
https://www.physiotherapyjobscanada.ca/physiotherapy-jobs-prince-edward-island/
```

---

## Content Summary

### Ontario
- 10 major cities listed (Toronto, Ottawa, Hamilton, etc.)
- 6 work settings (private clinics, hospitals, home care, sports, LTC, university)
- 5 major employers (UHN, Sunnybrook, Ottawa Hospital, etc.)
- Focus: Largest job market, diverse settings

### British Columbia
- 10 major cities (Vancouver, Victoria, Kelowna, etc.)
- 6 work settings (coastal practices, health authorities, sports)
- 5 major employers (Vancouver Coastal Health, Fraser Health, etc.)
- Focus: Outdoor lifestyle, coastal/rural mix

### Alberta
- 10 major cities (Calgary, Edmonton, Red Deer, etc.)
- 6 work settings (industrial rehab, teaching hospitals, rural)
- 5 major employers (AHS, Foothills, U of A Hospital, etc.)
- Focus: Competitive salaries, energy sector rehab

### Saskatchewan
- 10 major cities (Saskatoon, Regina, Prince Albert, etc.)
- 6 work settings (Saskatoon City Hospital, rural centres, ag injury)
- 5 major employers (SHA, Royal University Hospital, etc.)
- Focus: Rural autonomy, lower cost of living

### Manitoba
- 10 major cities (Winnipeg, Brandon, Thompson, etc.)
- 6 work settings (HSC Winnipeg, northern nursing stations, Indigenous health)
- 5 major employers (Shared Health, HSC, St. Boniface, etc.)
- Focus: Indigenous health, northern opportunities

### Quebec
- 10 major cities (Montreal, Quebec City, Laval, etc.)
- 6 work settings (CISSS/CIUSS, francophone clinics, bilingual rural)
- 5 major employers (MUHC, CHUM, CISSS, etc.)
- Focus: Bilingual opportunities, distinct healthcare system

### Nova Scotia
- 10 major cities (Halifax, Sydney, Truro, etc.)
- 6 work settings (QEII, Cape Breton, seniors care, Dalhousie)
- 5 major employers (NSHA, QEII, Cape Breton Regional, etc.)
- Focus: Coastal lifestyle, aging population needs

### New Brunswick
- 10 major cities (Moncton, Saint John, Fredericton, etc.)
- 6 work settings (Horizon, Vitalite, bilingual clinics, nursing homes)
- 5 major employers (Horizon, Vitalite, Chalmers Hospital, etc.)
- Focus: Only officially bilingual province

### Newfoundland and Labrador
- 10 major cities (St. John's, Corner Brook, Labrador City, etc.)
- 6 work settings (Eastern Health, Labrador-Grenfell, remote stations)
- 5 major employers (Eastern Health, Labrador-Grenfell, Western, Central)
- Focus: Adventurous rural practice, recruitment incentives

### Prince Edward Island
- 9 major cities (Charlottetown, Summerside, Stratford, etc.)
- 6 work settings (Queen Elizabeth, Prince County, community care)
- 5 major employers (Health PEI, QE Hospital, PCH, etc.)
- Focus: Intimate community practice, island lifestyle

---

## Next Steps

1. **Create branch** in your repo: `git checkout -b feature/province-seo-pages`
2. **Copy files** as documented above
3. **Test locally** using `python manage.py runserver`
4. **Review** each province page for accuracy
5. **Commit** changes: `git add province_pages/ && git commit -m "Add province SEO landing pages"`
6. **Push** to remote: `git push origin feature/province-seo-pages`
7. **Create PR** for review (do not merge directly to main)
8. **Deploy to staging** first
9. **Verify** all 10 URLs work
10. **Submit sitemap** to Google Search Console after production deploy

---

## Compliance Notes

- Salary ranges are presented as observed ranges with caveats ("varies by...")
- No specific medical claims or guarantees
- Disclaimer text can be added to footer if needed
- All employer names are publicly available information
- College/registration information is factual

---

## Questions?

Refer to `INTEGRATION.md` for detailed technical integration steps.
