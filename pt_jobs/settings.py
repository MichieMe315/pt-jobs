import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

DEBUG = os.environ.get("DEBUG", "False").lower() in ("1", "true", "yes", "on")

# ----------------------------
# Hosts / CSRF (Railway + domain)
# ----------------------------
def _csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "")
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]

_env_allowed = _csv_env("ALLOWED_HOSTS")
if _env_allowed:
    ALLOWED_HOSTS = _env_allowed
else:
    # sensible defaults if env var not set
    ALLOWED_HOSTS = [
        "127.0.0.1",
        "localhost",
        ".railway.app",
        ".up.railway.app",
        "physiotherapyjobscanada.ca",
        ".physiotherapyjobscanada.ca",
    ]

# CSRF trusted origins (needed when DEBUG=False)
_env_csrf = _csv_env("CSRF_TRUSTED_ORIGINS")
if _env_csrf:
    CSRF_TRUSTED_ORIGINS = _env_csrf
else:
    CSRF_TRUSTED_ORIGINS = [
        "https://*.railway.app",
        "https://*.up.railway.app",
        "https://physiotherapyjobscanada.ca",
        "https://www.physiotherapyjobscanada.ca",
    ]

# If you're using a proxy/CDN (Cloudflare), keep this:
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ----------------------------
# Applications
# ----------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "import_export",
    "board.apps.BoardConfig",
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

# ----------------------------
# Database (Railway Postgres)
# ----------------------------
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
        conn_max_age=600,
        ssl_require=False,
    )
}

# ----------------------------
# Password validation
# ----------------------------
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

# ----------------------------
# Static files
# ----------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ----------------------------
# Media files (local dev OR R2 public URL)
# ----------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL", "").strip()
# If you’re using your custom domain for R2 public access (recommended):
# example: https://media.physiotherapyjobscanada.ca
if R2_PUBLIC_BASE_URL:
    # Ensure trailing slash
    if not R2_PUBLIC_BASE_URL.endswith("/"):
        R2_PUBLIC_BASE_URL += "/"

# ----------------------------
# Email (SendGrid / SMTP via Railway vars)
# ----------------------------
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes", "on")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@physiotherapyjobscanada.ca")

# Optional “site admin inbox” fallback (your templates already email admin via SiteSettings + ADMINS)
SITE_ADMIN_EMAIL = os.environ.get("SITE_ADMIN_EMAIL", "")

# ----------------------------
# Security (production)
# ----------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "True").lower() in ("1", "true", "yes", "on")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
