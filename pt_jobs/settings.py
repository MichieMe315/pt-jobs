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
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# Production: require secret key. Local: allow fallback.
if DEBUG:
    SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-please-change-this")
else:
    SECRET_KEY = require_env("DJANGO_SECRET_KEY")


# ------------------------------------------------------------
# Hosts / CSRF
# ------------------------------------------------------------
ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".railway.app"]

railway_public_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_public_domain:
    ALLOWED_HOSTS.append(railway_public_domain)

extra_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
if extra_hosts:
    ALLOWED_HOSTS += [h.strip() for h in extra_hosts.split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://*.railway.app",
]

if railway_public_domain:
    CSRF_TRUSTED_ORIGINS.append(f"https://{railway_public_domain}")

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
# Media storage (LOCAL dev works; PROD uses R2 and is required)
# ------------------------------------------------------------
# Production: R2 ON and REQUIRED.
# Local dev: R2 OFF by default (so it runs without env vars).
# You can force R2 locally with USE_R2_MEDIA=1 + vars.
USE_R2_MEDIA = (not DEBUG) or env_bool("USE_R2_MEDIA", "0")

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if USE_R2_MEDIA:
    # storages MUST be installed & enabled when using R2
    if "storages" not in INSTALLED_APPS:
        INSTALLED_APPS.append("storages")

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


# ------------------------------------------------------------
# Middleware / URLs / Templates
# ------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

                # CRITICAL: must match your existing context_processors.py function name
                "board.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "pt_jobs.wsgi.application"


# ------------------------------------------------------------
# Database (Railway Postgres via DATABASE_URL, local fallback)
# ------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

if not DEBUG and not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set in production (DJANGO_DEBUG=0).")

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
# Static files (DEPLOY-SAFE)
# ------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Only include STATICFILES_DIRS if the folder exists in the repo (prevents collectstatic failures)
_static_dir = BASE_DIR / "static"
STATICFILES_DIRS = [_static_dir] if _static_dir.exists() else []

# DEPLOY-SAFE: avoids "Missing staticfiles manifest entry" failures during collectstatic
# (you can switch back to Manifest later once you're 100% sure all references exist)
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"


# ------------------------------------------------------------
# Security
# ------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG


# ------------------------------------------------------------
# Email
# ------------------------------------------------------------
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@physiotherapyjobscanada.ca")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = "[PT Jobs] "
