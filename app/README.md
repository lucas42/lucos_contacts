# lucos Contacts - Django app
A list of contacts

## Dependencies
* django
* A database (and the relevant python libraries to use that database

## Environment Variables:

* **SECRET_KEY** a secret used by django for lots of its security mechanisms.  To generate a new one, run `docker-compose exec app python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
* **PRODUCTION** Set in a production environment, as it increases security protections.  Not setting it will give detailed debug pages on error.

## Running
Requires [docker-compose](https://docs.docker.com/compose/)
Run the following:

`SECRET_KEY=changeme docker-compose up --build`

This will spin up docker containers for the django app, database and web proxy.

## Running tests locally
Run the following:

`docker compose up test --build --exit-code-from test`

The tests also get run in circleCI - test failures there block deployment.

## Creating a new database migration

* Upgrade the approprite `models.py` files
* `docker-compose exec app python manage.py makemigrations`
* `docker cp contacts_app:/usr/src/app/lucosauth/migrations/ app/lucosauth/`
* `docker cp contacts_app:/usr/src/app/comms/migrations/ app/comms/`
* `docker cp contacts_app:/usr/src/app/agents/migrations/ app/agents/`
* Rebuild & restart the container for the migrations to take effect.
* Commit the new migration files to git

## Language support
The UI is available in English or Irish languages.  Irish is the default and this can be switched in the navigation bar.  The source files are written in English, with locale config provided for Irish in `locale/ga/LC_MESSAGE/django.po`.

## Updating Translations

* `docker-compose exec app django-admin makemessages --all`
* `docker cp lucos_contacts_app:/usr/src/app/locale app/`
* Update the `.po` files in the locale directory with the relevant languages
* Rebuild & restart the container for the translations to take effect.  (translations are compiled as part of the docker build process)
* Commit the locale files to git