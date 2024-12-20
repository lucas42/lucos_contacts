import os
import sys
from django.utils.translation import gettext_lazy as _
# Django settings for contacts project.

PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))

ADMINS = (
    # ('Your Name', 'your_email@domain.com'),
)

MANAGERS = ADMINS

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'Europe/London'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'ga-gb'
LANGUAGES = [
    ('ga', _('Irish')),
    ('en', _('English')),
]

LOCALE_PATHS = (os.path.join(PROJECT_PATH, "locale"),)

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
STATIC_URL = '/resources/'

STATICFILES_DIRS = [
    os.path.join(PROJECT_PATH, "templates/resources"),
]
STATIC_ROOT = os.path.join(PROJECT_PATH, "static")

MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(PROJECT_PATH, 'templates'),
        ],
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

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'agents',
    'lucosauth',
    'comms',
    'phonenumber_field',
    'django.contrib.admin',
    'django.contrib.staticfiles',
    'django.contrib.messages',
    'django.contrib.humanize',
)

SECRET_KEY = os.environ["SECRET_KEY"]

AUTHENTICATION_BACKENDS = (
    'lucosauth.models.LucosAuthBackend',
)
AUTH_DOMAIN = 'auth.l42.eu'

SECURE_PROXY_SSL_HEADER = (
	'HTTP_X_FORWARDED_PROTO', 'https'
)

ALLOWED_HOSTS = ["contacts.l42.eu", "localhost", "host.docker.internal"]

if os.environ.get("PRODUCTION"):
    DEBUG = False
else:
    DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql', # Add 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'postgres',              # Or path to database file if using sqlite3.
        'USER': 'postgres',              # Not used with sqlite3.
        'HOST': 'db',                    # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler'
        },
    },
    'loggers': {
        '': {  # 'catch all' loggers by referencing it with the empty string
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

# This prevents warning about old test runners
TEST_RUNNER = 'django.test.runner.DiscoverRunner'


## Phone Number Settings
PHONENUMBER_DB_FORMAT = 'E164'
PHONENUMBER_DEFAULT_REGION = 'GB' # NB: there's some hardcoded logic in models.py which assumes this
PHONENUMBER_DEFAULT_FORMAT = 'E164'