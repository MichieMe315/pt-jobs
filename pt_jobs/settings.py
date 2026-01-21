# pt_jobs/settings.py
from __future__ import annotations

import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# ==============================================================================
# Core
# ==============================================================================
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    # Allow local dev without env var, but require in production
    if os.environ.get("DEBUG", "").lower() in ("1", "true", "yes", "on"):
        SECRET_KEY = "dev-secret-key-change-me"
    else:
        raise ImproperlyConfigured("SECRET_KEY is required in production.")

DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes", "on")


# ==============================================================================
# Hosts / CSRF (fixes DisallowedHost -> 400)
# ==============================================================================
PRIMARY_DOMAIN = os.environ.get("PRIMARY_DOMAIN", "physiotherapyjobscanada.ca").strip()
WWW_DOMAIN = f"www.{PRIMARY_DOMAIN}"

# Railway app hostname (optional but helpful)
RAILWAY_PUBLIC_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()  # e.g. 4nle1arz.up.railway.app

# Comma-separated override if you want to control exactly:
# ALLOWED_HOSTS="physiotherapyjobscanada.ca,www.physiotherapyjobscanada.ca,4nle1arz.up.railway.app"
allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "").strip()

if allowed_hosts_env:
    ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]
else:
    ALLOWED_HOSTS = [
        PRIMARY_DOMAIN,
        WWW_DOMAIN,
        "localhost",
        "127.0.0.1",
        "[::1]",
    ]
    if RAILWAY_PUBLIC_DOMAIN:
        ALLOWED_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)

# CSRF trusted origins MUST include scheme
CSRF_TRUSTED_ORIGINS = []
csrf_env = os.environ.get("CSRF_TRUSTED_ORIGINS", "").strip()
if csrf_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_env.split(",") if o.strip()]
else:
    # Add the canonical production origins
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
        # Your project-level templates folder:
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "pt_jobs.wsgi.application"


# ==============================================================================
# Database
# ==============================================================================
DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=not DEBUG)}
else:
    # Local dev fallback
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ==============================================================================
# Auth / sessions
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = []
if not DEBUG:
    AUTH_PASSWORD_VALIDATORS = [
        {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
        {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
        {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
        {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    ]

LANGUAGE_CODE = "en-ca"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

LOGIN_URL = "login"


# ==============================================================================
# Static files (WhiteNoise)
# ==============================================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise compressed manifest storage
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"


# ==============================================================================
# Media / Uploads (Cloudflare R2)
# ==============================================================================
# IMPORTANT:
# - If USE_R2 is true, ImageField.url will be an R2 URL (NOT /media/... on your Django domain).
# - If you want /media/... on your main domain, that must be done at Cloudflare (Worker/Proxy) — not Django settings.
USE_R2 = os.environ.get("USE_R2", "1" if not DEBUG else "0").lower() in ("1", "true", "yes", "on")

if USE_R2:
    R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "").strip()
    R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL", "").strip()  # like https://<accountid>.r2.cloudflarestorage.com
    R2_REGION = os.environ.get("R2_REGION", "auto").strip()
    R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL", "").strip()  # like https://media.yourdomain.com OR https://pub-xxxx.r2.dev

    missing = [k for k, v in {
        "R2_ACCESS_KEY_ID": R2_ACCESS_KEY_ID,
        "R2_SECRET_ACCESS_KEY": R2_SECRET_ACCESS_KEY,
        "R2_BUCKET_NAME": R2_BUCKET_NAME,
        "R2_ENDPOINT_URL": R2_ENDPOINT_URL,
        "R2_PUBLIC_BASE_URL": R2_PUBLIC_BASE_URL,
    }.items() if not v]

    if missing:
        raise ImproperlyConfigured(f"USE_R2 is enabled but missing env vars: {', '.join(missing)}")

    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_REGION_NAME = R2_REGION
    AWS_S3_ENDPOINT_URL = R2_ENDPOINT_URL
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_ADDRESSING_STYLE = "virtual"
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False

    # This is what controls the URL returned by ImageField.url
    MEDIA_URL = R2_PUBLIC_BASE_URL.rstrip("/") + "/"
else:
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"


# ==============================================================================
# Email (SendGrid custom backend)
# ==============================================================================
# You said your backend is exactly:
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "board.email_backend_sendgrid.SendGridAPIEmailBackend",
)

# This is the critical part you keep fighting:
# DEFAULT_FROM_EMAIL must be info@... (since no-reply doesn't exist for you)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", f"info@{PRIMARY_DOMAIN}")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# The SendGrid backend should read this:
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "").strip()
if not DEBUG and "SendGrid" in EMAIL_BACKEND and not SENDGRID_API_KEY:
    raise ImproperlyConfigured("SENDGRID_API_KEY is required in production for SendGrid email backend.")


# ==============================================================================
# Security (production)
# ==============================================================================
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # If Railway/Cloudflare is already enforcing HTTPS, this is OK.
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "1").lower() in ("1", "true", "yes", "on")

    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0") or "0")
    SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "0").lower() in ("1", "true", "yes", "on")
    SECURE_HSTS_PRELOAD = os.environ.get("SECURE_HSTS_PRELOAD", "0").lower() in ("1", "true", "yes", "on")


# ==============================================================================
# Logging (so you can see real failures in Railway logs)
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


# ==============================================================================
# Misc
# ==============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
