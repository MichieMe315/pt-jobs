# Homepage Enhancement Proposal (Planning)

**Goal** – Boost the main landing page of *Physiotherapy Jobs Canada* so it becomes a strong SEO hub and a convenient entry point for both job‑seekers and employers, without adding heavy scripts or flashy design.

## 1. Content Structure (300‑500 words total)
- **Hero** – Keep the existing gradient hero but tighten the copy:
  - H1: *“Find Physiotherapy Jobs Across Canada”*.
  - Sub‑head: *“Browse thousands of current openings, filter by province or city, and discover the best fit for your career.”*.
- **Provincial Quick‑Links** – A clean, responsive grid of the 13 provinces/territories. Each tile shows the province name, a small SVG icon, and the number of live jobs (pulled from the database via a lightweight API call). Links go to the new SEO‑optimized province pages (`/physiotherapy-jobs‑{province}/`).
- **Featured Cities** – Below the province grid, surface the top 8‑12 cities with the highest job volume. Use the same card style as the “Major Cities” section on province pages, but without extra hover‑shadow classes to keep load time low.
- **Why Choose Us** – A three‑column block highlighting:
    1. *Nation‑wide coverage* – all provinces, all settings.
    2. *Simple search* – keyword, location, and specialty filters.
    3. *Trusted listings* – verified employers, no hidden fees.
- **Call‑to‑Action** – Prominent, primary‑button “Browse All Jobs” linking to `/jobs/` and a secondary “Post a Job” linking to the employer portal.
- **SEO Metadata** –
    - Title: *“Physiotherapy Jobs Canada – Nationwide PT Vacancies”*.
    - Meta description (≈155 chars): *“Search physiotherapy jobs across Canada. Filter by province, city or specialty and find your next PT role today.”*.
    - Structured data: `WebPage` with `breadcrumb` list and `ItemList` for the province tiles (each `ListItem` includes `position` and `url`).

## 2. Internal Linking Strategy
- Hero CTA → `/jobs/` (search page).
- Province tiles → corresponding SEO‑optimized province pages (`/physiotherapy-jobs‑ontario/`, etc.).
- City cards → job list filtered by city (`/jobs/?location=Toronto`).
- “Why Choose Us” links to static informational pages (e.g., *How We Verify Employers*).
- Footer retains existing navigation (Home, About, Contact, Privacy, Terms).

## 3. Styling & Performance
- Continue using Bootstrap 5 utilities; avoid custom CSS beyond spacing and colour tweaks.
- Remove any heavy hover‑shadow classes (already done on province pages) to keep the page lightweight.
- Lazy‑load the province icons SVGs and defer non‑critical scripts.
- Keep the page under 2 s LCP by serving a pre‑generated HTML snapshot for the province grid (no DB queries on first load).

## 4. Analytics & Tracking
- Add a single Google Analytics event on the primary CTA (`browse_all_jobs`) and on each province tile click (`province_click_{province}`).
- No additional third‑party scripts; maintain privacy‑first approach.

## 5. Next Steps (No deployment yet)
1. Draft the HTML markup in a new template `home.html` based on the structure above.
2. Add the province‑grid view in `views.py` that pulls the job counts (can be a cached query).
3. Update the URL config to serve the homepage with the new template.
4. Review SEO metadata and structured‑data snippets.
5. Run Lighthouse audit locally; iterate until >90 score.
6. Once approved, open a PR for the team to review.

*This proposal stays within the current Bootstrap styling, avoids flashy animations, and aligns with the tone and SEO focus of the province pages.*
