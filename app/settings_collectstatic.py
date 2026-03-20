"""
Minimal settings for the collectstatic build step.

Only declares what collectstatic needs — no database, no auth, no
third-party apps that require environment variables at import time.
"""

import os

PROJECT_PATH = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = 'build-time-placeholder'

INSTALLED_APPS = [
    'django.contrib.staticfiles',
]

STATIC_URL = '/resources/'
STATIC_ROOT = os.path.join(PROJECT_PATH, 'static')
STATICFILES_DIRS = [
    os.path.join(PROJECT_PATH, 'templates/resources'),
]
