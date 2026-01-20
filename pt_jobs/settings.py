import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# =====================
# Core security
# =====================
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

DEBUG = os.environ.get("DEBUG", "0") == "1"

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    ".railway.app",
    ".up.railway.app",
    "physiotherapyjobscanada.ca",
    "www.physiotherapyjobscanada.ca",
]

railway_domain = (
    os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    or os.environ.get("RAILWAY_STATIC_URL")
)
if railway_domain:
    ALLOWED_HOSTS.append(railway_domain)

CSRF_TRUSTED_ORIGINS = [
    "https://*.railway.app",
    "https://*.up.railway.app",
    "https://physiotherapyjobscanada.ca",
    "https://www.physiotherapyjobscanada.ca",
]

# =====================
# Applications
# =====================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "import_export",

    # Local
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

ROOT_URLCONF = "pt_jobs.urls"

# =====================
# Templates
# =====================
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

# =====================
# Database
# =====================
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
# Auth / Passwords
# =====================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# =====================
# Locale / Time
# =====================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

# =====================
# Static & Media
# =====================
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# =====================
# Proxy / SSL
# =====================
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "0") == "1"
SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
CSRF_COOKIE_SECURE = os.environ.get("CSRF_COOKIE_SECURE", "0") == "1"

X_FRAME_OPTIONS = "SAMEORIGIN"

# =====================
# WhiteNoise
# =====================
if not DEBUG:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =====================
# EMAIL — CRITICAL
# =====================
EMAIL_SUBJECT_PREFIX = "[Physiotherapy Jobs Canada] "

DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "info@physiotherapyjobscanada.ca",
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

ON_RAILWAY = bool(
    os.environ.get("RAILWAY_ENVIRONMENT")
    or os.environ.get("RAILWAY_PROJECT_ID")
    or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
)

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "board.email_backend_sendgrid.SendGridAPIEmailBackend"
    if ON_RAILWAY
    else "django.core.mail.backends.console.EmailBackend",
)

# SMTP fallback (not used with SendGrid API backend)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587")) if os.environ.get("EMAIL_PORT") else 587
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
