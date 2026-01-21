from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")

# -------------------------------------------------
# ENV / DEBUG
# -------------------------------------------------
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes", "on")
if os.environ.get("RAILWAY_ENVIRONMENT_NAME", "").lower() == "production":
    DEBUG = False

# -------------------------------------------------
# HOSTS / CSRF  (THIS FIXES THE 400 ERROR)
# -------------------------------------------------
CUSTOM_DOMAIN = "physiotherapyjobscanada.ca"
CUSTOM_DOMAIN_WWW = "www.physiotherapyjobscanada.ca"

RAILWAY_PUBLIC_URL = os.environ.get("RAILWAY_PUBLIC_URL", "").strip()
RAILWAY_PUBLIC_HOST = (
    RAILWAY_PUBLIC_URL.replace("https://", "").replace("http://", "").strip("/")
    if RAILWAY_PUBLIC_URL
    else ""
)

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    CUSTOM_DOMAIN,
    CUSTOM_DOMAIN_WWW,
    ".railway.app",
]

if RAILWAY_PUBLIC_HOST:
    ALLOWED_HOSTS.append(RAILWAY_PUBLIC_HOST)

CSRF_TRUSTED_ORIGINS = [
    f"https://{CUSTOM_DOMAIN}",
    f"https://{CUSTOM_DOMAIN_WWW}",
]

if RAILWAY_PUBLIC_HOST:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_PUBLIC_HOST}")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# -------------------------------------------------
# APPS
# -------------------------------------------------
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

# -------------------------------------------------
# MIDDLEWARE
# -------------------------------------------------
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

# -------------------------------------------------
# TEMPLATES
# -------------------------------------------------
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

# -------------------------------------------------
# DATABASE
# -------------------------------------------------
if os.environ.get("DATABASE_URL"):
    import dj_database_url
    DATABASES = {
        "default": dj_database_url.config(
            default=os.environ["DATABASE_URL"],
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# -------------------------------------------------
# AUTH
# -------------------------------------------------
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

# -------------------------------------------------
# STATIC
# -------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# -------------------------------------------------
# EMAIL — SENDGRID WEB API
# -------------------------------------------------
EMAIL_BACKEND = "board.email_backend_sendgrid.SendGridAPIEmailBackend"
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")

DEFAULT_FROM_EMAIL = "info@physiotherapyjobscanada.ca"
SITE_ADMIN_EMAIL = DEFAULT_FROM_EMAIL

# -------------------------------------------------
# MEDIA — CLOUDFLARE R2 (DOES NOT WIPE FILES)
# -------------------------------------------------
USE_R2 = True

R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT_URL = os.environ.get("R2_ENDPOINT_URL")
R2_PUBLIC_BASE_URL = os.environ.get("R2_PUBLIC_BASE_URL")

if USE_R2 and all([
    R2_BUCKET_NAME,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_ENDPOINT_URL,
]):
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
                "addressing_style": "path",
                **({"custom_domain": custom_domain} if custom_domain else {}),
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

    MEDIA_URL = (
        R2_PUBLIC_BASE_URL.rstrip("/") + "/"
        if R2_PUBLIC_BASE_URL
        else "/media/"
    )
else:
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------
# LOGGING (VISIBLE IN RAILWAY)
# -------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR"},
        "board": {"handlers": ["console"], "level": "INFO"},
    },
}
