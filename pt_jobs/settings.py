# pt_jobs/settings.py
from pathlib import Path
import os

import dj_database_url
from django.contrib.messages import constants as messages

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-please-change-this")

# In Railway set DJANGO_DEBUG="0"
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def _split_csv(v: str) -> list[str]:
    return [x.strip() for x in (v or "").split(",") if x.strip()]


def _is_local_host(h: str) -> bool:
    return h in ("127.0.0.1", "localhost") or h.startswith("127.") or h == ""


# ------------------------------------------------------------
# HOSTS / CSRF (Railway + custom domains)
# ------------------------------------------------------------
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]

# Railway public domain (sometimes present, sometimes not)
railway_public_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_public_domain:
    ALLOWED_HOSTS.append(railway_public_domain)

# IMPORTANT:
# Support BOTH env names (you’ve used ALLOWED_HOSTS in Railway UI)
extra_hosts = (
    os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip()
    or os.environ.get("ALLOWED_HOSTS", "").strip()
)
if extra_hosts:
    ALLOWED_HOSTS += [h.strip() for h in extra_hosts.split(",") if h.strip()]

# CSRF trusted origins MUST include scheme (https://...)
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

# Add Railway https domain to CSRF if present
if railway_public_domain:
    CSRF_TRUSTED_ORIGINS.append(f"https://{railway_public_domain}")

# Auto-add https://<host> for every allowed host (except local / wildcards)
# This prevents the “403 CSRF verification failed” problem on Railway/admin.
for host in ALLOWED_HOSTS:
    if _is_local_host(host):
        continue
    # ignore leading-dot cookie-style domains or wildcards
    if host.startswith(".") or "*" in host:
        continue
    origin_https = f"https://{host}"
    if origin_https not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin_https)

# Optional: comma-separated extra CSRF trusted origins
# We support BOTH env names for convenience.
extra_csrf = (
    os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
    or os.environ.get("CSRF_TRUSTED_ORIGINS", "").strip()
)
if extra_csrf:
    CSRF_TRUSTED_ORIGINS += [o.strip() for o in extra_csrf.split(",") if o.strip()]

# ------------------------------------------------------------
# Proxy/HTTPS settings (Railway/Cloudflare)
# ------------------------------------------------------------
# IMPORTANT:
# Railway/Cloudflare terminate HTTPS before your container. Django must trust
# X-Forwarded-Proto or you get CSRF/session weirdness in production.
#
# We enable these whenever DEBUG is False OR whenever we're clearly on Railway.
ON_RAILWAY = bool(os.environ.get("RAILWAY_PUBLIC_DOMAIN")) or bool(os.environ.get("RAILWAY_ENVIRONMENT"))

if (not DEBUG) or ON_RAILWAY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

    # Cookies secure in prod-like environments
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Optional but recommended once your domain is HTTPS:
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"

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
    "storages",  # django-storages for R2
    # Local
    "board.apps.BoardConfig",
]

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

# WhiteNoise static file storage (hashed filenames + compression)
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ------------------------------------------------------------
# MEDIA: Cloudflare R2 (django-storages/boto3)
# ------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "").strip()
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "").strip()
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL", "").strip()  # e.g. https://media.physiotherapyjobscanada.ca

# Only enable R2 storage if configured
USE_R2 = all([R2_ACCOUNT_ID, R2_BUCKET_NAME, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_PUBLIC_BASE_URL])

if USE_R2:
    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME

    AWS_S3_ENDPOINT_URL = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    AWS_S3_REGION_NAME = "auto"

    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False  # IMPORTANT so URLs are public and don't require auth signatures

    AWS_S3_OBJECT_PARAMETERS = {
        "CacheControl": "max-age=31536000, public",
    }

    # Django 5+ STORAGES setting
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

    # Your public custom domain for R2
    MEDIA_URL = R2_PUBLIC_BASE_URL.rstrip("/") + "/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----------------
# Email (IMPORTANT)
# ----------------
EMAIL_SUBJECT_PREFIX = "[PT Jobs] "
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@physiotherapyjobscanada.ca")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Local dev: print emails to console so password reset works without SMTP.
# For live: set EMAIL_BACKEND and SMTP env vars in Railway.
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend",
)

# Optional SMTP settings (only used if you switch EMAIL_BACKEND to SMTP)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587")) if os.environ.get("EMAIL_PORT") else 587
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
