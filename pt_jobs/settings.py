from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

# Railway sets RAILWAY_ENVIRONMENT_NAME=production in prod
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes", "on")
ENV_NAME = os.environ.get("RAILWAY_ENVIRONMENT_NAME", "").lower()
if ENV_NAME == "production":
    DEBUG = False

# -----------------------------
# Hosts / CSRF (fix 400 + Cloudflare)
# -----------------------------
CUSTOM_DOMAIN = os.environ.get("CUSTOM_DOMAIN", "").strip()  # e.g. physiotherapyjobscanada.ca
CUSTOM_DOMAIN_WWW = f"www.{CUSTOM_DOMAIN}" if CUSTOM_DOMAIN else ""

# Railway sometimes gives you a public URL like https://xxxx.up.railway.app
RAILWAY_PUBLIC_URL = os.environ.get("RAILWAY_PUBLIC_URL", "").strip()
RAILWAY_PUBLIC_HOST = (
    RAILWAY_PUBLIC_URL.replace("https://", "").replace("http://", "").strip("/")
    if RAILWAY_PUBLIC_URL
    else ""
)

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    ".railway.app",
]

if CUSTOM_DOMAIN:
    ALLOWED_HOSTS += [CUSTOM_DOMAIN, CUSTOM_DOMAIN_WWW]

if RAILWAY_PUBLIC_HOST:
    ALLOWED_HOSTS += [RAILWAY_PUBLIC_HOST]

# Optional extra hosts (comma-separated) if you ever need quick hotfix without code edits
EXTRA_ALLOWED_HOSTS = os.environ.get("EXTRA_ALLOWED_HOSTS", "").strip()
if EXTRA_ALLOWED_HOSTS:
    ALLOWED_HOSTS += [h.strip() for h in EXTRA_ALLOWED_HOSTS.split(",") if h.strip()]

# CSRF trusted origins (must be full scheme+host)
CSRF_TRUSTED_ORIGINS = []
if CUSTOM_DOMAIN:
    CSRF_TRUSTED_ORIGINS += [f"https://{CUSTOM_DOMAIN}", f"https://{CUSTOM_DOMAIN_WWW}"]
if RAILWAY_PUBLIC_HOST:
    CSRF_TRUSTED_ORIGINS += [f"https://{RAILWAY_PUBLIC_HOST}"]

# If you ever test via http locally, Django doesn’t need CSRF_TRUSTED_ORIGINS for localhost.

# If you're behind a proxy (Railway/Cloudflare), keep these:
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "board",
    "storages",
    "import_export",
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
            ],
        },
    },
]

WSGI_APPLICATION = "pt_jobs.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql"
        if os.environ.get("DATABASE_URL")
        else "django.db.backends.sqlite3",
        "NAME": os.environ.get("PGDATABASE", BASE_DIR / "db.sqlite3"),
        "USER": os.environ.get("PGUSER", ""),
        "PASSWORD": os.environ.get("PGPASSWORD", ""),
        "HOST": os.environ.get("PGHOST", ""),
        "PORT": os.environ.get("PGPORT", ""),
    }
}

if os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES["default"] = dj_database_url.config(
        default=os.environ["DATABASE_URL"], conn_max_age=600, ssl_require=True
    )

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

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Always use WhiteNoise hashed static in production-like deploys
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# -----------------------------
# Email (SendGrid Web API backend)
# -----------------------------
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "board.email_backend_sendgrid.SendGridAPIEmailBackend"
)

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")

# You explicitly want info@ as the default sender:
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL", "info@physiotherapyjobscanada.ca"
)

# Optional admin recipient fallback if SiteSettings.contact_email isn't set:
SITE_ADMIN_EMAIL = os.environ.get("SITE_ADMIN_EMAIL", DEFAULT_FROM_EMAIL)

# -----------------------------
# Media / R2 (Cloudflare R2)
# -----------------------------
USE_R2 = os.environ.get("USE_R2", "1").lower() in ("1", "true", "yes", "on")

R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL", "")  # e.g. https://<accountid>.r2.cloudflarestorage.com
R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL", "").strip()  # e.g. https://media.yourdomain.com OR https://<bucket>.<acct>.r2.dev

# Django 5+ storage config
if USE_R2 and R2_BUCKET_NAME and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_ENDPOINT_URL:
    # custom_domain must be just the host (no scheme)
    custom_domain = ""
    if R2_PUBLIC_BASE_URL:
        custom_domain = (
            R2_PUBLIC_BASE_URL.replace("https://", "")
            .replace("http://", "")
            .strip("/")
        )

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": R2_BUCKET_NAME,
                "access_key": R2_ACCESS_KEY_ID,
                "secret_key": R2_SECRET_ACCESS_KEY,
                "endpoint_url": R2_ENDPOINT_URL,
                "region_name": "auto",
                "default_acl": None,
                "querystring_auth": False,
                "addressing_style": "path",  # safest with R2/custom domains
                **({"custom_domain": custom_domain} if custom_domain else {}),
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

    # IMPORTANT: Never set MEDIA_URL="/" — that can break routing/templates.
    if R2_PUBLIC_BASE_URL:
        MEDIA_URL = R2_PUBLIC_BASE_URL.rstrip("/") + "/"
    else:
        MEDIA_URL = "/media/"

else:
    # Local/dev fallback
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -----------------------------
# Logging (so you can see failures in Railway logs)
# -----------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": True},
        "board": {"handlers": ["console"], "level": "INFO", "propagate": True},
    },
}
