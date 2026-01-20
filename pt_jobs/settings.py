from pathlib import Path
import os

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes", "on")

# Allow Railway + your domains
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    ".railway.app",
]

# If you set a custom domain, add it here (and keep it even if DEBUG=False)
# e.g. physiotherapyjobscanada.ca, www.physiotherapyjobscanada.ca
CUSTOM_DOMAIN = os.environ.get("CUSTOM_DOMAIN", "").strip()
if CUSTOM_DOMAIN:
    ALLOWED_HOSTS.append(CUSTOM_DOMAIN)
    ALLOWED_HOSTS.append(f"www.{CUSTOM_DOMAIN}")

CSRF_TRUSTED_ORIGINS = []
if CUSTOM_DOMAIN:
    CSRF_TRUSTED_ORIGINS += [
        f"https://{CUSTOM_DOMAIN}",
        f"https://www.{CUSTOM_DOMAIN}",
    ]
# Railway URL (optional but helpful)
RAILWAY_PUBLIC_URL = os.environ.get("RAILWAY_PUBLIC_URL", "").strip()
if RAILWAY_PUBLIC_URL.startswith("https://"):
    CSRF_TRUSTED_ORIGINS.append(RAILWAY_PUBLIC_URL)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "storages",
    "import_export",
    # Local
    "board",
]

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
                "board.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "pt_jobs.wsgi.application"

# Database (Railway uses DATABASE_URL)
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
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

LANGUAGE_CODE = "en-ca"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ============================================================
# EMAIL
# ============================================================
# You told me you are using the SendGrid Web API backend class we created:
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "board.email_backend_sendgrid.SendGridAPIEmailBackend",
)

# Web API backend needs SENDGRID_API_KEY (or SENDGRID_API_KEY in Railway)
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "").strip()

# IMPORTANT: default FROM should be info@ unless you override in env vars
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "info@physiotherapyjobscanada.ca")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# If your backend uses these (safe to keep even if not used)
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", "10"))

# ============================================================
# MEDIA: Cloudflare R2 (django-storages)
# ------------------------------------------------------------
# This project uses Cloudflare R2 for user-uploaded media (logos, hero images, resumes).
#
# Env vars supported (Railway):
#   R2_ACCOUNT_ID
#   R2_BUCKET_NAME
#   R2_ACCESS_KEY_ID
#   R2_SECRET_ACCESS_KEY
#   R2_PUBLIC_BASE_URL   (e.g. https://media.physiotherapyjobscanada.ca)
# Optional/alternate names also supported:
#   AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_STORAGE_BUCKET_NAME
#   AWS_S3_ENDPOINT_URL / R2_ENDPOINT_URL
#   AWS_S3_CUSTOM_DOMAIN / R2_CUSTOM_DOMAIN
#
# IMPORTANT: If these env vars are missing locally, we fall back to local FileSystemStorage
# so dev can run without R2. In production, set the env vars so media URLs are NOT /media/*.
# ------------------------------------------------------------
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "").strip()
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", os.environ.get("AWS_STORAGE_BUCKET_NAME", "")).strip()

# Credentials (support either R2_* or AWS_* env var names)
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", os.environ.get("AWS_ACCESS_KEY_ID", "")).strip()
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", os.environ.get("AWS_SECRET_ACCESS_KEY", "")).strip()

# Endpoint URL (Cloudflare R2 S3-compatible endpoint)
R2_ENDPOINT_URL = (
    os.environ.get("R2_ENDPOINT_URL")
    or os.environ.get("AWS_S3_ENDPOINT_URL")
    or (f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if R2_ACCOUNT_ID else "")
).strip()

# Public base URL (your custom domain / public bucket URL)
R2_PUBLIC_BASE_URL = (
    os.environ.get("R2_PUBLIC_BASE_URL")
    or os.environ.get("R2_PUBLIC_URL")
    or os.environ.get("R2_CUSTOM_DOMAIN")
    or os.environ.get("AWS_S3_CUSTOM_DOMAIN")
    or ""
).strip()

# Enable R2 if the minimum required pieces exist
USE_R2 = bool(R2_BUCKET_NAME and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_ENDPOINT_URL)

# Django 5+ storage config
if USE_R2:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": R2_BUCKET_NAME,
                "access_key": R2_ACCESS_KEY_ID,
                "secret_key": R2_SECRET_ACCESS_KEY,
                "endpoint_url": R2_ENDPOINT_URL,
                "region_name": "auto",
                # If you have a public/custom domain, this makes .url() return that domain
                # (preferred, so media doesn't point at /media/ on your app).
                **({"custom_domain": R2_PUBLIC_BASE_URL.replace("https://", "").replace("http://", "")} if R2_PUBLIC_BASE_URL else {}),
                "default_acl": None,
                "querystring_auth": False,
            },
        },
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

    # Helpful in templates; storage handles ImageField.url either way.
    MEDIA_URL = (R2_PUBLIC_BASE_URL.rstrip("/") + "/") if R2_PUBLIC_BASE_URL else "/"
else:
    # Local/dev fallback
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

# Security (production)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth redirects
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
