from pathlib import Path
import os

import dj_database_url
from django.contrib.messages import constants as messages

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-please-change-this")

# In Railway set DJANGO_DEBUG="0"
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# Hosts
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Railway public domain (Railway sets this on the web service once you generate a domain)
railway_public_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_public_domain:
    ALLOWED_HOSTS.append(railway_public_domain)

# Optional: comma-separated extra hosts you want
# e.g. DJANGO_ALLOWED_HOSTS="physiotherapyjobscanada.ca,www.physiotherapyjobscanada.ca"
extra_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
if extra_hosts:
    ALLOWED_HOSTS += [h.strip() for h in extra_hosts.split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

# Add Railway https domain to CSRF if present
if railway_public_domain:
    CSRF_TRUSTED_ORIGINS.append(f"https://{railway_public_domain}")

# Optional: comma-separated extra CSRF trusted origins
# e.g. DJANGO_CSRF_TRUSTED_ORIGINS="https://physiotherapyjobscanada.ca,https://www.physiotherapyjobscanada.ca"
extra_csrf = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "")
if extra_csrf:
    CSRF_TRUSTED_ORIGINS += [o.strip() for o in extra_csrf.split(",") if o.strip()]

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "import_export",
    # Local
    "board",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pt_jobs.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # inject SiteSettings everywhere
                "board.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "pt_jobs.wsgi.application"

# ------------------------------------------------------------
# DATABASES (Railway Postgres via DATABASE_URL, local fallback)
# ------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if DATABASE_URL:
    # Railway Postgres usually requires SSL
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    # Local/dev fallback
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}

LOGIN_URL = "login"
LOGOUT_REDIRECT_URL = "/"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "no-reply@physiotherapyjobscanada.ca"
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = "[PT Jobs] "
