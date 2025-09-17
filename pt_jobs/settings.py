from pathlib import Path
import os

# ------------------------------------------------------------------------------
# Core
# ------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-secret-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    # Add your prod hostnames or IPs here, e.g. "physiotherapyjobscanada.com"
] + os.environ.get("DJANGO_ALLOWED_HOSTS", "").split()

# ------------------------------------------------------------------------------
# Installed apps
# ------------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "import_export",  # admin import/export

    # Local
    "board",
]

# ------------------------------------------------------------------------------
# Middleware / URL / Templates
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
        # Project-level templates: put your *.html under BASE_DIR / "templates"
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,  # also load app templates (e.g., board/templates/…)
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

# ------------------------------------------------------------------------------
# Database
# ------------------------------------------------------------------------------
# SQLite for local/dev. Swap to Postgres for production via env vars if needed.
if os.environ.get("DATABASE_URL"):
    # Optional: dj_database_url parse if you use it. Otherwise configure manually.
    # import dj_database_url
    # DATABASES = {"default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=600)}
    raise RuntimeError("DATABASE_URL provided, but no parser configured in settings.py. Add dj_database_url or manual config.")
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ------------------------------------------------------------------------------
# Password validation
# ------------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ------------------------------------------------------------------------------
# Internationalization
# ------------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Toronto"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------------------
# Static & Media
# ------------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",  # place your project-level static here if you have any
]
STATIC_ROOT = BASE_DIR / "staticfiles"  # collectstatic destination

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ------------------------------------------------------------------------------
# Auth
# ------------------------------------------------------------------------------
# Allow login using either email OR username (case-insensitive)
AUTHENTICATION_BACKENDS = [
    "board.auth_backends.EmailOrUsernameModelBackend",
    "django.contrib.auth.backends.ModelBackend",
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "post_login_redirect"
LOGOUT_REDIRECT_URL = "home"

# ------------------------------------------------------------------------------
# Email
# ------------------------------------------------------------------------------
# Configure these in your environment for real email sending.
EMAIL_BACKEND = os.environ.get("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@example.com")

# SMTP example (uncomment and set env vars if you use SMTP):
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.sendgrid.net")
# EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
# EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
# EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
# EMAIL_USE_TLS = True

# ------------------------------------------------------------------------------
# Stripe (keys pulled from environment; safe test defaults)
# ------------------------------------------------------------------------------
STRIPE_PUBLIC_KEY = os.environ.get("STRIPE_PUBLIC_KEY", "pk_test_123")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "sk_test_123")

# ------------------------------------------------------------------------------
# Django Import-Export
# ------------------------------------------------------------------------------
IMPORT_EXPORT_USE_TRANSACTIONS = True

# ------------------------------------------------------------------------------
# Security/dev niceties
# ------------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1",
    "http://localhost",
    # add prod origins like "https://physiotherapyjobscanada.com"
]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if os.environ.get("USE_PROXY_SSL", "") else None

# ------------------------------------------------------------------------------
# Default primary key type
# ------------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
