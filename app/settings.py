import os
import sys
# Django settings for contacts project.

# Include environment specific settings, such a DB credentials and API_KEY
from local_settings import *

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

MIDDLEWARE_CLASSES = (
	'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
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
    'django.contrib.admin',
    'django.contrib.staticfiles',
    'django.contrib.messages',
)

AUTHENTICATION_BACKENDS = (
    'lucosauth.models.LucosAuthBackend',
)

SECURE_PROXY_SSL_HEADER = (
	'HTTP_X_FORWARDED_PROTO', 'https'
)

'''LOGGING = {
    'version': 1,
    'handlers': {
        'null': {
            'level':'ERROR',
            'class':'django.utils.log.NullHandler',
        },
        'console': {
            'level':'ERROR',
            'class':'logging.StreamHandler',
            'stream': sys.stderr
        },
    },
	'loggers': {
        'django': {
            'handlers': ['null'],
            'propagate': False,
            'level': 'CRITICAL',
        },
		'django.request': {
			'level': 'CRITICAL',
			'handlers': ['null'],
			'propagate': False,
		},
    }
}'''

# This prevents warning about old test runners
TEST_RUNNER = 'django.test.runner.DiscoverRunner'
