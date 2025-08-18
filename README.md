# PT Jobs Canada (Demo)

A minimal Django job board with employer & job seeker portals.

## Quickstart

1. **Create and activate a virtualenv (recommended)**
   ```
   python3 -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **Install requirements**
   ```
   pip install -r requirements.txt
   ```

3. **Run migrations and create a superuser**
   ```
   python manage.py migrate
   python manage.py createsuperuser
   ```

4. **Start the dev server**
   ```
   python manage.py runserver
   ```

5. Open http://127.0.0.1:8000

- Register as an **Employer** to post jobs.
- Register as a **Job Seeker** to apply for jobs.
- Admin: /admin for full control.

## Notes

- Uses SQLite by default. To switch to Postgres, edit `DATABASES` in `pt_jobs/settings.py`.
- Static CSS is minimal and easily customizable at `static/styles.css`.
- This demo intentionally keeps resume uploads as text. Add `FileField` + media settings if you want uploads.
- Respect real website's branding & content — this demo is *not affiliated* with physiotherapyjobscanada.ca.
