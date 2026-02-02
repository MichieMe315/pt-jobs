# pt_jobs/settings.py
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")

DEBUG = os.environ.get("DEBUG", "0") == "1"

allowed_hosts_env = os.environ.get("DJANGO_ALLOWED_HOSTS", "")
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(",") if h.strip()]

CSRF_TRUSTED_ORIGINS = []
csrf_origins_env = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "")
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins_env.split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "board",
]

# --- OPTIONAL: django-storages (only if installed) ---
# We do NOT hard-require it (to avoid breaking local if not installed).
try:
    import storages  # noqa: F401

    if "storages" not in INSTALLED_APPS:
        INSTALLED_APPS.append("storages")
except Exception:
    pass

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serves /static/ in production (including Django admin CSS)
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

# ---------------------------------------------------------------------
# DATABASE
# - Local default stays sqlite.
# - Production MUST use Railway's DATABASE_URL automatically when present.
# ---------------------------------------------------------------------
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

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if DATABASE_URL:
    try:
        import dj_database_url

        DATABASES["default"] = dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "600")),
            # Railway internal postgres often does not require sslmode=require.
            # If you have a public URL that requires SSL, set DB_SSL_REQUIRE=1.
            ssl_require=os.environ.get("DB_SSL_REQUIRE", "0") == "1",
        )
    except Exception:
        # If dj_database_url isn't available for some reason, we keep the fallback DATABASES above.
        pass

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

# ---------------------------------------------------------------------
# STATIC (Admin styling depends on this)
# ---------------------------------------------------------------------
STATIC_URL = "/static/"  # MUST be absolute
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# WhiteNoise storage for hashed static files
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------------------------------------------------
# MEDIA (Local filesystem by default; R2 if env vars exist)
# ---------------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# If R2 is configured, use it for DEFAULT file storage (media uploads)
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "").strip()
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "").strip()
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL", "").strip()
R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL", "").strip()

USE_R2 = all([R2_BUCKET_NAME, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT_URL, R2_PUBLIC_BASE_URL])

if USE_R2:
    # Only configure if django-storages is available
    try:
        import storages  # noqa: F401

        # Django 5+ preferred storage config
        STORAGES = {
            "default": {
                "BACKEND": "storages.backends.s3.S3Storage",
                "OPTIONS": {
                    "bucket_name": R2_BUCKET_NAME,
                    "access_key": R2_ACCESS_KEY_ID,
                    "secret_key": R2_SECRET_ACCESS_KEY,
                    "endpoint_url": R2_ENDPOINT_URL,
                    # R2 recommends region_name="auto" for S3-compatible clients
                    "region_name": os.environ.get("R2_REGION_NAME", "auto"),
                    # Ensure generated URLs point to the public base
                    "custom_domain": R2_PUBLIC_BASE_URL.replace("https://", "").replace("http://", "").rstrip("/"),
                },
            },
            "staticfiles": {
                "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
            },
        }

        # Make MEDIA_URL point to the public bucket base so ImageField.url is correct
        MEDIA_URL = R2_PUBLIC_BASE_URL.rstrip("/") + "/"
    except Exception:
        # If storages isn't installed, do not crash; keep local MEDIA settings
        pass
else:
    # Ensure STORAGES exists if something else references it
    STORAGES = {
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------
# Proxy / HTTPS (Railway behind proxy)
# ---------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# If you forgot to set CSRF_TRUSTED_ORIGINS in Railway, we can safely add your domain in production
if not DEBUG and not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = [
        "https://physiotherapyjobscanada.ca",
        "https://www.physiotherapyjobscanada.ca",
    ]

# ---------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "board.email_backend_sendgrid.SendGridAPIEmailBackend")

_raw_from = os.environ.get("DEFAULT_FROM_EMAIL", "info@physiotherapyjobscanada.ca").strip()
if _raw_from and "<" not in _raw_from and ">" not in _raw_from:
    DEFAULT_FROM_EMAIL = f"Physiotherapy Jobs Canada <{_raw_from}>"
else:
    DEFAULT_FROM_EMAIL = _raw_from or "Physiotherapy Jobs Canada <info@physiotherapyjobscanada.ca>"

SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
