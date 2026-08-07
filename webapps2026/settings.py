import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_flag(name, default):
    """Read a boolean from the environment ('1', 'true', 'yes' are all true)."""
    return os.environ.get(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


# Debug is off unless explicitly enabled, so that an accidental deployment of
# this repository does not serve tracebacks and settings to the internet.
DEBUG = _env_flag('DJANGO_DEBUG', False)

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError(
            'DJANGO_SECRET_KEY must be set when DEBUG is off.\n'
            'For local work, run the command with DJANGO_DEBUG=True.\n'
            'Otherwise generate a key with:\n'
            '  python -c "from django.core.management.utils import get_random_secret_key; '
            'print(get_random_secret_key())"'
        )
    # Development only. This value is public, so it must never reach production
    # — the branch above is what stops it.
    SECRET_KEY = 'django-insecure-local-dev-only'

# Comma-separated list, e.g. DJANGO_ALLOWED_HOSTS="example.com,www.example.com".
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',')
    if host.strip()
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'crispy_forms',
    'crispy_bootstrap5',
    'django_extensions',
    'register',
    'payapp',
    'conversionservice',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'webapps2026.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'webapps2026.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'webapps.db',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/webapps2026/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOGIN_URL = '/webapps2026/login/'
LOGIN_REDIRECT_URL = '/webapps2026/dashboard/'
LOGOUT_REDIRECT_URL = '/webapps2026/login/'

# ── Security ─────────────────────────────────────────────────────────────────

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Set to False only if you are deliberately serving over plain HTTP, e.g. with
# `manage.py runserver` instead of run_https.sh. Secure cookies are not sent
# over HTTP, so leaving this True on an HTTP server silently breaks login.
USE_HTTPS = _env_flag('DJANGO_USE_HTTPS', True)

SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# runserver_plus terminates TLS itself, so redirecting would loop in development.
SECURE_SSL_REDIRECT = USE_HTTPS and not DEBUG

# HSTS is only asserted outside development. Sending a one-year preload header
# from localhost pins the developer's browser to HTTPS on localhost for every
# other project too.
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Self-signed certificate paths (used by run_https.sh / runserver_plus).
SSL_CERTIFICATE = BASE_DIR / 'certs' / 'cert.pem'
SSL_PRIVATE_KEY = BASE_DIR / 'certs' / 'key.pem'

# ── Conversion service ───────────────────────────────────────────────────────

# The conversion service is part of this same project but is consumed over HTTP
# to keep the service boundary explicit. Override the URL if you run the server
# on a different host or port, or split the service out.
CONVERSION_SERVICE_URL = os.environ.get(
    'DJANGO_CONVERSION_SERVICE_URL', 'https://localhost:8000/webapps2026/conversion'
)
CONVERSION_SERVICE_TIMEOUT = float(os.environ.get('DJANGO_CONVERSION_TIMEOUT', '3'))

# Off by default because the development server uses a self-signed certificate.
# Turn on once the service is behind a certificate the client can verify.
CONVERSION_SERVICE_VERIFY_TLS = _env_flag('DJANGO_CONVERSION_VERIFY_TLS', False)

#: Amount credited to a new member account, converted into their currency.
INITIAL_BALANCE_GBP = os.environ.get('DJANGO_INITIAL_BALANCE_GBP', '500.00')

# ── Logging ──────────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '{levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        # Warns when a payment falls back to local rates because the REST
        # service could not be reached.
        'conversionservice': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'payapp': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}
