from pathlib import Path
import os

import dj_database_url
from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def require_env(name: str) -> str:
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return val.strip()


# ------------------------------------------------------------
# Core
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# Apps
# ------------------------------------------------------------
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


# ------------------------------------------------------------
# Media storage (LOCAL dev works; PROD locked to R2)
#
# Rules:
# - If DJANGO_DEBUG=0 => require R2 vars + enable django-storages
# - If DJANGO_DEBUG=1 => local filesystem media by default
# - You can still enable R2 locally by setting USE_R2_MEDIA=1 + providing vars
# ------------------------------------------------------------
USE_R2_MEDIA = (not DEBUG) or env_bool("USE_R2_MEDIA", "0")

if USE_R2_MEDIA:
    # Require storages app only when using R2
    if "storages" not in INSTALLED_APPS:
        INSTALLED_APPS.append("storages")

    # Required R2 env vars (locked in production; optional only if you toggle USE_R2_MEDIA locally)
    R2_ACCESS_KEY_ID = require_env("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY = require_env("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME = require_env("R2_BUCKET_NAME")
    R2_ENDPOINT_URL = require_env("R2_ENDPOINT_URL")
    # Public base URL where media is served from (CDN/custom domain or r2.dev URL)
    R2_PUBLIC_BASE_URL = require_env("R2_PUBLIC_BASE_URL").rstrip("/")

    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = R2_ENDPOINT_URL
    AWS_S3_REGION_NAME = "auto"
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False

    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

    MEDIA_URL = f"{R2_PUBLIC_BASE_URL}/"
    MEDIA_ROOT = BASE_DIR / "media"  # not used in R2 mode, but harmless
else:
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"


# ------------------------------------------------------------
# Middleware / URLs / Templates
# ------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # REQUIRED for Railway static/admin
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
                # DO NOT CHANGE: must match your existing board/context_processors.py
                # It defines def site_settings(...) and returns {"sitesettings": ...}
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
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=False,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ------------------------------------------------------------
# Auth / Locale / Messages
# ------------------------------------------------------------
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

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ------------------------------------------------------------
# Static files
# ------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# ------------------------------------------------------------
# Email
# ------------------------------------------------------------
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@physiotherapyjobscanada.ca")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = "[PT Jobs] "
