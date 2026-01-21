import os
from pathlib import Path
from urllib.parse import urlparse

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.contrib.messages import constants as messages

BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# Core
# ==============================================================================
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
if not SECRET_KEY:
    # Local dev fallback only
    SECRET_KEY = "dev-secret-key-change-me"

DEBUG = os.environ.get("DEBUG", "0").lower() in ("1", "true", "yes", "on")

PRIMARY_DOMAIN = os.environ.get("PRIMARY_DOMAIN", "physiotherapyjobscanada.ca").strip()
WWW_DOMAIN = os.environ.get("WWW_DOMAIN", f"www.{PRIMARY_DOMAIN}").strip()

# Railway host (set this in Railway env if you can, otherwise it’s optional)
# Example: 4nle1arz.up.railway.app
RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()

# ==============================================================================
# Hosts (fixes DisallowedHost / Bad Request 400)
# ==============================================================================
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
if not DEBUG:
    # Always allow your real domains in production
    ALLOWED_HOSTS += [PRIMARY_DOMAIN, WWW_DOMAIN]

    # Allow Railway public host if provided
    if RAILWAY_PUBLIC_DOMAIN:
        ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)

    # If you ever temporarily need broad allowance while debugging:
    # ALLOWED_HOSTS.append(".up.railway.app")

# ==============================================================================
# Applications
# ==============================================================================
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Third-party
    "import_export",
    "storages",
    # Local
    "board",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static on Railway
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
                "board.context_processors.site_settings",
            ],
        },
    }
]

WSGI_APPLICATION = "pt_jobs.wsgi.application"

# ==============================================================================
# Database (Railway uses DATABASE_URL)
# ==============================================================================
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=False)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ==============================================================================
# Password validation
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ==============================================================================
# i18n
# ==============================================================================
LANGUAGE_CODE = "en-ca"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

# ==============================================================================
# Messages (bootstrap classes)
# ==============================================================================
MESSAGE_TAGS = {
    messages.DEBUG: "secondary",
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}

# ==============================================================================
# Auth
# ==============================================================================
LOGIN_URL = "login"
LOGOUT_REDIRECT_URL = "/"

# ==============================================================================
# Static files (WhiteNoise)
# ==============================================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}

# ==============================================================================
# MEDIA / Uploads (Cloudflare R2) — FIXES logos/hero breaking
# ==============================================================================
R2_BUCKET_NAME = (os.environ.get("R2_BUCKET_NAME") or "").strip()
R2_ACCESS_KEY_ID = (os.environ.get("R2_ACCESS_KEY_ID") or "").strip()
R2_SECRET_ACCESS_KEY = (os.environ.get("R2_SECRET_ACCESS_KEY") or "").strip()

# Prefer explicit endpoint, but allow account-id construction
R2_ACCOUNT_ID = (os.environ.get("R2_ACCOUNT_ID") or "").strip()
R2_ENDPOINT_URL = (os.environ.get("R2_ENDPOINT_URL") or "").strip()
if not R2_ENDPOINT_URL and R2_ACCOUNT_ID:
    R2_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

# This is CRITICAL: this is what ImageField.url should use publicly
# Examples:
#   https://pub-xxxx.r2.dev
#   https://media.physiotherapyjobscanada.ca
R2_PUBLIC_BASE_URL = (os.environ.get("R2_PUBLIC_BASE_URL") or "").strip()

USE_R2 = all([R2_BUCKET_NAME, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL, R2_PUBLIC_BASE_URL])

if not DEBUG and not USE_R2:
    raise ImproperlyConfigured(
        "R2 media is not configured in production. Set: "
        "R2_BUCKET_NAME, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL (or R2_ACCOUNT_ID), "
        "and R2_PUBLIC_BASE_URL."
    )

if USE_R2:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": R2_BUCKET_NAME,
            "access_key": R2_ACCESS_KEY_ID,
            "secret_key": R2_SECRET_ACCESS_KEY,
            "endpoint_url": R2_ENDPOINT_URL,
            "region_name": "auto",
            "signature_version": "s3v4",
            "querystring_auth": False,
            "default_acl": None,
        },
    }

    # This controls URL returned by employer.logo.url / sitesettings.hero_image.url, etc.
    MEDIA_URL = R2_PUBLIC_BASE_URL.rstrip("/") + "/"

    # Also ensure storage uses your public domain host for .url() construction
    # (This prevents raw R2 endpoint URLs in some cases)
    AWS_S3_CUSTOM_DOMAIN = urlparse(R2_PUBLIC_BASE_URL).netloc

else:
    # Local dev only
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"
    STORAGES["default"] = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

# ==============================================================================
# Email (SendGrid Web API backend)
# ==============================================================================
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "board.email_backend_sendgrid.SendGridAPIEmailBackend",
)

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "").strip()

# You said NO "no-reply". Your real sender is info@
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", f"info@{PRIMARY_DOMAIN}").strip()
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL).strip()

EMAIL_SUBJECT_PREFIX = os.environ.get("EMAIL_SUBJECT_PREFIX", "[PT Jobs] ").strip()

# ==============================================================================
# CSRF / Security (fixes Referer checking failed + proxy https)
# ==============================================================================
CSRF_TRUSTED_ORIGINS = []
csrf_env = os.environ.get("CSRF_TRUSTED_ORIGINS", "").strip()
if csrf_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_env.split(",") if o.strip()]
else:
    # MUST include scheme+host
    CSRF_TRUSTED_ORIGINS = [
        f"https://{PRIMARY_DOMAIN}",
        f"https://{WWW_DOMAIN}",
    ]
    if RAILWAY_PUBLIC_DOMAIN:
        CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")

    # Local dev convenience
    if DEBUG:
        CSRF_TRUSTED_ORIGINS.extend(
            [
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ]
        )

# Behind Cloudflare/Railway proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Keep redirect controllable by env (avoid surprise loops)
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "0").lower() in ("1", "true", "yes", "on")

# ==============================================================================
# Logging (so failures show clearly in Railway logs)
# ==============================================================================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "board": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
