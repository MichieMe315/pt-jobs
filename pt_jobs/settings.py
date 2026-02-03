from pathlib import Path
import os

import dj_database_url
from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def require_any_env(*names: str) -> str:
    """
    Strict: require at least one of the provided env var names.
    (No silent fallback to unrelated defaults in production.)
    """
    for n in names:
        v = os.environ.get(n)
        if v is not None and v.strip() != "":
            return v.strip()
    raise ImproperlyConfigured(f"Missing required environment variable (any of): {', '.join(names)}")


# ------------------------------------------------------------
# Core
# ------------------------------------------------------------
# Railway commonly uses DEBUG=0/1; you also have DJANGO_DEBUG.
# Treat either as authoritative.
DEBUG = env_bool("DJANGO_DEBUG", os.environ.get("DEBUG", "0"))

# Production: require secret key (Railway has SECRET_KEY per your screenshot).
# Local dev: allow a fallback ONLY when DEBUG=1.
if DEBUG:
    SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or os.environ.get("SECRET_KEY") or "dev-insecure-please-change-this"
else:
    SECRET_KEY = require_any_env("SECRET_KEY", "DJANGO_SECRET_KEY")

# Hosts
ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".railway.app"]

railway_public_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if railway_public_domain:
    ALLOWED_HOSTS.append(railway_public_domain)

# Optional: comma-separated hosts
extra_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
if extra_hosts:
    ALLOWED_HOSTS += [h.strip() for h in extra_hosts.split(",") if h.strip()]

# CSRF
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
    # Third-party (keep as-is if it worked before)
    "import_export",
    # Local
    "board",
]


# ------------------------------------------------------------
# Media storage (local dev OK, prod uses R2)
# ------------------------------------------------------------
# Production: require R2.
# Local: filesystem media by default; can force R2 with USE_R2_MEDIA=1.
USE_R2_MEDIA = (not DEBUG) or env_bool("USE_R2_MEDIA", "0")

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if USE_R2_MEDIA:
    if "storages" not in INSTALLED_APPS:
        INSTALLED_APPS.append("storages")

    # R2 env vars
    R2_ACCESS_KEY_ID = require_any_env("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY = require_any_env("R2_SECRET_ACCESS_KEY")
    R2_BUCKET_NAME = require_any_env("R2_BUCKET_NAME")
    R2_ENDPOINT_URL = require_any_env("R2_ENDPOINT_URL")
    R2_PUBLIC_BASE_URL = require_any_env("R2_PUBLIC_BASE_URL").rstrip("/")

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

                # MUST MATCH your existing board/context_processors.py
                "board.context_processors.site_settings",
            ],
        },
    },
]

WSGI_APPLICATION = "pt_jobs.wsgi.application"


# ------------------------------------------------------------
# Database
# ------------------------------------------------------------
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Production should have DATABASE_URL; local can fall back.
if not DEBUG and not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set in production (DEBUG=0).")

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
# Static files (deploy-safe)
# ------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Only include STATICFILES_DIRS if the folder exists (prevents collectstatic blowups)
_static_dir = BASE_DIR / "static"
STATICFILES_DIRS = [_static_dir] if _static_dir.exists() else []

# Deploy-safe storage (avoids manifest-missing failures)
STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"


# ------------------------------------------------------------
# Security toggles (optional env overrides)
# ------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Respect your Railway vars if you set them; otherwise default based on DEBUG.
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", "0" if DEBUG else "1")
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", "0" if DEBUG else "1")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", "0" if DEBUG else "1")


# ------------------------------------------------------------
# Email
# ------------------------------------------------------------
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@physiotherapyjobscanada.ca")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_SUBJECT_PREFIX = "[PT Jobs] "
