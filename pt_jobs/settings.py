import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()]
if not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]

CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
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
            ],
        },
    },
]

WSGI_APPLICATION = "pt_jobs.wsgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Railway provides an internal hostname (postgres.railway.internal) that only resolves
# inside Railway's private network. If you run commands locally via `railway run`
# on Windows/macOS, that internal hostname may not resolve. In that case, prefer
# a public/proxy URL if provided.
if DATABASE_URL and "railway.internal" in DATABASE_URL:
    try:
        import platform as _platform
        if _platform.system().lower() in ("windows", "darwin"):
            _public = (
                os.environ.get("DATABASE_PUBLIC_URL")
                or os.environ.get("DATABASE_URL_PUBLIC")
                or os.environ.get("DATABASE_PROXY_URL")
                or ""
            ).strip()
            if _public:
                DATABASE_URL = _public
    except Exception:
        pass

if not DATABASE_URL:
    # Local dev fallback
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    # Basic DATABASE_URL parsing without extra deps.
    # Expected: postgresql://user:pass@host:port/dbname
    import urllib.parse

    parsed = urllib.parse.urlparse(DATABASE_URL)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured("DATABASE_URL must be postgres/postgresql.")

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": parsed.username,
            "PASSWORD": parsed.password,
            "HOST": parsed.hostname,
            "PORT": parsed.port or 5432,
            "CONN_MAX_AGE": 60,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.environ.get("TIME_ZONE", "America/Toronto")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Admin contacts (fallback used by views for approval/signup notifications)
ADMINS = [("Admin", os.environ.get("ADMIN_EMAIL", "info@physiotherapyjobscanada.ca"))]

# Comma-separated list or Python list of admin notification emails.
ADMIN_EMAILS = os.environ.get("ADMIN_EMAILS", "").strip()

# Email (SendGrid SMTP by default)
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "").strip() or "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "").strip() or "smtp.sendgrid.net"
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "").strip() or "apikey"
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "").strip() or os.environ.get("SENDGRID_API_KEY", "").strip()

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "info@physiotherapyjobscanada.ca").strip()
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL).strip()

if not DEBUG:
    # In production, enforce that credentials exist so email works reliably.
    if not EMAIL_HOST_PASSWORD:
        raise ImproperlyConfigured("Missing EMAIL_HOST_PASSWORD or SENDGRID_API_KEY in production environment.")

# Security
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() in ("1", "true", "yes") and not DEBUG
