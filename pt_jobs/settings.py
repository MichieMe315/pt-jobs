from pathlib import Path
import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


# ==============================================================================
# Core
# ==============================================================================
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes", "on")

# Your canonical domain (no scheme)
CUSTOM_DOMAIN = (os.environ.get("CUSTOM_DOMAIN") or "physiotherapyjobscanada.ca").strip()


# ==============================================================================
# Hosts / CSRF (fixes Bad Request 400 / DisallowedHost)
# ==============================================================================
def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


# Railway provides one or more public domains depending on config
RAILWAY_PUBLIC_DOMAIN = (os.environ.get("RAILWAY_PUBLIC_DOMAIN") or "").strip()
RAILWAY_STATIC_URL = (os.environ.get("RAILWAY_STATIC_URL") or "").strip()  # sometimes exists
RAILWAY_URL = (os.environ.get("RAILWAY_URL") or "").strip()               # sometimes exists

allowed = set(["localhost", "127.0.0.1", "[::1]"])
allowed.update(_split_csv(os.environ.get("ALLOWED_HOSTS", "")))

if CUSTOM_DOMAIN:
    allowed.add(CUSTOM_DOMAIN)
    allowed.add(f"www.{CUSTOM_DOMAIN}")

for v in (RAILWAY_PUBLIC_DOMAIN, RAILWAY_STATIC_URL, RAILWAY_URL):
    if v:
        # env var might include scheme; strip it
        v = v.replace("https://", "").replace("http://", "").strip().strip("/")
        if v:
            allowed.add(v)

ALLOWED_HOSTS = sorted(allowed)

CSRF_TRUSTED_ORIGINS = []
if CUSTOM_DOMAIN:
    CSRF_TRUSTED_ORIGINS += [
        f"https://{CUSTOM_DOMAIN}",
        f"https://www.{CUSTOM_DOMAIN}",
    ]
for v in (RAILWAY_PUBLIC_DOMAIN, RAILWAY_STATIC_URL, RAILWAY_URL):
    if v:
        v = v.strip().strip("/")
        if v.startswith("http"):
            CSRF_TRUSTED_ORIGINS.append(v)
        else:
            CSRF_TRUSTED_ORIGINS.append(f"https://{v}")

# Behind Railway proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True


# ==============================================================================
# Apps
# ==============================================================================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

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
    },
]

WSGI_APPLICATION = "pt_jobs.wsgi.application"


# ==============================================================================
# Database
# ==============================================================================
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600, ssl_require=True)}
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
# Static files
# ==============================================================================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise (compressed static)
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ==============================================================================
# Media files (Cloudflare R2) — FIXES LOGOS/HERO 404
# IMPORTANT: In production, we DO NOT silently fall back to /media/.
# ==============================================================================
R2_BUCKET_NAME = (os.environ.get("R2_BUCKET_NAME") or "").strip()
R2_ACCESS_KEY_ID = (os.environ.get("R2_ACCESS_KEY_ID") or "").strip()
R2_SECRET_ACCESS_KEY = (os.environ.get("R2_SECRET_ACCESS_KEY") or "").strip()
R2_ENDPOINT_URL = (os.environ.get("R2_ENDPOINT_URL") or "").strip()
R2_PUBLIC_BASE_URL = (os.environ.get("R2_PUBLIC_BASE_URL") or "").strip()  # e.g. https://pub-xxxx.r2.dev

USE_R2 = all([R2_BUCKET_NAME, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL, R2_PUBLIC_BASE_URL])

if not USE_R2 and not DEBUG:
    raise ImproperlyConfigured(
        "R2 media is not configured in production. Set R2_BUCKET_NAME, R2_ACCESS_KEY_ID, "
        "R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL, and R2_PUBLIC_BASE_URL."
    )

if USE_R2:
    AWS_ACCESS_KEY_ID = R2_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = R2_SECRET_ACCESS_KEY
    AWS_STORAGE_BUCKET_NAME = R2_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = R2_ENDPOINT_URL
    AWS_S3_REGION_NAME = "auto"
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=31536000"}
    AWS_LOCATION = ""  # keep root of bucket

    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "endpoint_url": AWS_S3_ENDPOINT_URL,
            "region_name": AWS_S3_REGION_NAME,
            "signature_version": AWS_S3_SIGNATURE_VERSION,
            "querystring_auth": AWS_QUERYSTRING_AUTH,
            "default_acl": AWS_DEFAULT_ACL,
        },
    }

    # This is what ImageField.url will use — MUST be the public base URL.
    MEDIA_URL = R2_PUBLIC_BASE_URL.rstrip("/") + "/"
else:
    # Local dev only
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"


# ==============================================================================
# Email (SendGrid)
# ==============================================================================
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "board.email_backend_sendgrid.SendGridAPIEmailBackend",
)

# IMPORTANT: Password reset + all Django emails use DEFAULT_FROM_EMAIL unless overridden.
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@physiotherapyjobscanada.ca")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# For your internal admin notifications
SITE_ADMIN_EMAIL = os.environ.get("SITE_ADMIN_EMAIL", "info@physiotherapyjobscanada.ca")

# Used by your SendGrid backend module (if it reads this env var)
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")


# ==============================================================================
# Security (production hardening - safe defaults)
# ==============================================================================
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0") or "0")
    SECURE_HSTS_INCLUDE_SUBDOMAINS = bool(int(os.environ.get("SECURE_HSTS_INCLUDE_SUBDOMAINS", "0") or "0"))
    SECURE_HSTS_PRELOAD = bool(int(os.environ.get("SECURE_HSTS_PRELOAD", "0") or "0"))


# ==============================================================================
# Misc
# ==============================================================================
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
