from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent


# =====================
# Core
# =====================

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

DEBUG = os.environ.get("DEBUG", "").strip() in ("1", "true", "True", "yes", "YES")

ALLOWED_HOSTS = []
if DEBUG:
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
else:
    # Railway provides the host header; allow all unless you want to lock it down.
    ALLOWED_HOSTS = ["*"]


# =====================
# Applications
# =====================

INSTALLED_APPS = [
    "storages",  # required for R2 (django-storages)
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "import_export",
    "board",
]


# =====================
# Middleware
# =====================

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


# =====================
# URLs / WSGI
# =====================

ROOT_URLCONF = "pt_jobs.urls"

WSGI_APPLICATION = "pt_jobs.wsgi.application"


# =====================
# Templates  (IMPORTANT: APP_DIRS must be True)
# =====================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,  # ✅ FIX: required so admin/import_export templates load
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# =====================
# Database
# =====================

# (Keep your existing DB env vars. This is a safe default.)
# If you already have DATABASES configured differently in your file,
# keep that exact block and do NOT change it.
DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.environ.get("DB_NAME", BASE_DIR / "db.sqlite3"),
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", ""),
        "PORT": os.environ.get("DB_PORT", ""),
    }
}


# =====================
# Auth / Sessions
# =====================

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

LOGIN_URL = "login"
LOGOUT_REDIRECT_URL = "home"


# =====================
# Email
# =====================

# Keep exactly what you said you have:
# EMAIL_BACKEND = "board.email_backend_sendgrid.SendGridAPIEmailBackend"
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "board.email_backend_sendgrid.SendGridAPIEmailBackend")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "info@physiotherapyjobscanada.ca")
SITE_ADMIN_EMAIL = os.environ.get("SITE_ADMIN_EMAIL", "info@physiotherapyjobscanada.ca")


# =====================
# Static & Media
# =====================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default (local dev) media settings.
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Cloudflare R2 (S3-compatible) media storage ---
# IMPORTANT: To use R2 in production, set USE_R2=1 and provide ALL env vars below.
# This is intentionally strict (no silent fallback) so media never "mysteriously" breaks.
USE_R2 = os.environ.get("USE_R2", "").strip() in ("1", "true", "True", "yes", "YES")

if USE_R2:
    try:
        from django.core.exceptions import ImproperlyConfigured
    except Exception:  # pragma: no cover
        ImproperlyConfigured = RuntimeError  # type: ignore

    R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL", "").strip()
    R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
    R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
    R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "").strip()
    # Public base URL where objects are served (R2 public bucket URL or your custom domain)
    R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL", "").strip().rstrip("/")

    missing = [k for k, v in {
        "R2_ENDPOINT_URL": R2_ENDPOINT_URL,
        "R2_ACCESS_KEY_ID": R2_ACCESS_KEY_ID,
        "R2_SECRET_ACCESS_KEY": R2_SECRET_ACCESS_KEY,
        "R2_BUCKET_NAME": R2_BUCKET_NAME,
        "R2_PUBLIC_BASE_URL": R2_PUBLIC_BASE_URL,
    }.items() if not v]

    if missing:
        raise ImproperlyConfigured("USE_R2=1 but missing required env vars: " + ", ".join(missing))

    # Media must resolve to R2, not /media/ on the app.
    MEDIA_URL = f"{R2_PUBLIC_BASE_URL}/"

# Django 5.x storage config:
# - staticfiles stays on the app via WhiteNoise
# - default (media) is local in dev, R2 in production when USE_R2=1
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}

if USE_R2:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "access_key": R2_ACCESS_KEY_ID,
            "secret_key": R2_SECRET_ACCESS_KEY,
            "bucket_name": R2_BUCKET_NAME,
            "endpoint_url": R2_ENDPOINT_URL,
            "region_name": "auto",
            "signature_version": "s3v4",
            "addressing_style": "virtual",
            "default_acl": None,
            "querystring_auth": False,
        },
    }


# =====================
# Security (production sane defaults)
# =====================

CSRF_TRUSTED_ORIGINS = []
if not DEBUG:
    # Add your real domain(s) here once DNS is done:
    # Example:
    # CSRF_TRUSTED_ORIGINS = ["https://physiotherapyjobscanada.ca", "https://www.physiotherapyjobscanada.ca"]
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
