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
ADMIN_MEDIA_PREFIX = '/media/'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = [
	'django.template.loaders.filesystem.Loader',
	'django.template.loaders.app_directories.Loader',
]

MIDDLEWARE_CLASSES = (
	'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

ROOT_URLCONF = 'contacts.urls'

TEMPLATE_DIRS = (
	os.path.join(PROJECT_PATH, 'templates')
    # Put strings here, like "/home/html/django_templates" or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'agents',
    'django.contrib.admin',
)

# Need newer version of django for logging to work
'''LOGGING = {
    'handlers': {
        'null': {
            'level':'ERROR',
            'class':'django.utils.log.NullHandler',
            'stream': sys.stdout
        },
    },
	'loggers': {
		'django': {
			'handlers':['null'],
			'propagate': False,
			'level':'CRITICAL',
		},
		'django.request': {
			'level': 'CRITICAL',
			'handlers': ['null'],
			'propagate': False,
		},
	}
}'''
