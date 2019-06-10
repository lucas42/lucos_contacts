#!/bin/sh
set -e
python manage.py collectstatic --noinput
python manage.py migrate
gunicorn --bind :80 --timeout 30 agents.wsgi:application --access-logfile=/dev/stdout --access-logformat="%(t)s %(h)s \"%(r)s\" %(s)s %(b)s \"%(a)s\" %(D)sμs"