import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local development overrides from .env. On Render the environment is
# injected directly by the platform, so there is no .env file and this is a
# no-op. .env is git-ignored and must never be committed.
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "local-development-secret-key-change-this-before-production-7f3a9c2e1d",
)
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.environ.get(
    "ALLOWED_HOSTS", "localhost,127.0.0.1,.onrender.com"
).split(",") if host.strip()]
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.environ.get(
    "CSRF_TRUSTED_ORIGINS", ""
).split(",") if origin.strip()]
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
if RENDER_EXTERNAL_URL and RENDER_EXTERNAL_URL not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.append(RENDER_EXTERNAL_URL)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "website",
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

ROOT_URLCONF = "jobspace.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "website.context_processors.dashboard_badges",
            ],
        },
    },
]

WSGI_APPLICATION = "jobspace.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# If DATABASE_URL is missing or malformed, dj_database_url either falls back to
# the SQLite default above or — when it is set but empty — returns an empty
# dict. Either way the site would come up with no real database: every request
# fails, or worse, an empty SQLite file silently appears. That is the failure
# mode where a deploy looks successful and all the production data is simply
# not there. Refusing to start turns it into an obvious error instead.
if not DEBUG and not DATABASES["default"].get("ENGINE"):
    raise RuntimeError(
        "DATABASE_URL is missing, empty or unparseable, so no database is "
        "configured. Set it in /var/www/jobspace/.env to a valid PostgreSQL "
        "URL, for example "
        "postgresql://jobspace:PASSWORD@127.0.0.1:5432/jobspace"
    )

if not DEBUG and DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    raise RuntimeError(
        "SQLite is configured while DEBUG is False. DATABASE_URL must point at "
        "PostgreSQL in production. Set it in /var/www/jobspace/.env, for "
        "example "
        "postgresql://jobspace:PASSWORD@127.0.0.1:5432/jobspace"
    )

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# STORAGES replaces the STATICFILES_STORAGE setting (deprecated in Django 5.1).
# CompressedManifest = gzipped files with content-hashed names, so nginx and
# WhiteNoise can serve them with long-lived cache headers and a deploy never
# serves a stale stylesheet.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATICFILES_DIRS = [BASE_DIR / "static"]
LOGIN_URL = "/signin/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Password rules. This list was previously empty, which let accounts be created
# with blank or trivially guessable passwords — a real problem now that the
# project holds CVs and payment records. These run on signup and on any
# password change, including in the admin.
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ── Flutterwave payment gateway ──────────────────────────────────────────────
FLUTTERWAVE_PUBLIC_KEY   = os.environ.get("FLUTTERWAVE_PUBLIC_KEY", "")
FLUTTERWAVE_SECRET_KEY   = os.environ.get("FLUTTERWAVE_SECRET_KEY", "")
FLUTTERWAVE_WEBHOOK_HASH = os.environ.get("FLUTTERWAVE_WEBHOOK_HASH", "")

# ── Reverse proxy / TLS ─────────────────────────────────────────────────────
# nginx terminates TLS and forwards plain HTTP to gunicorn over a Unix socket.
# Without this header Django believes every request arrived over http, so it
# builds `http://` URLs, emits a redirect to the insecure scheme, and marks
# cookies insecure. Trusting the header nginx sets is what makes Django
# correctly treat the request as HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Keyed to DEBUG so local development over http keeps working. On the VPS
# DEBUG is False, so both are True automatically — no extra configuration.
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# nginx already redirects http -> https (the port 80 block returns 301). This
# flag is a second, in-app safety net. It must NOT default to True, or the
# very first request to a brand-new server would bounce forever before the
# certificate exists. Enable it via .env once HTTPS is live.
SECURE_SSL_REDIRECT = os.environ.get(
    "SECURE_SSL_REDIRECT", "False"
).lower() == "true"

# 0 in .env until HTTPS is confirmed working, then 31536000. Read the Django
# HSTS deployment checklist first: once a browser has cached this header it
# cannot be withdrawn until the max-age expires, and a broken certificate
# afterwards becomes unfixable for those browsers.
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_HSTS_PRELOAD = SECURE_HSTS_SECONDS > 0
