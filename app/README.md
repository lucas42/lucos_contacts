# lucos Contacts - Django app
A list of contacts

## Dependencies
* django
* A database (and the relevant python libraries to use that database

## Environment Variables:

* **SECRET_KEY** a secret used by django for lots of its security mechanisms
* **PRODUCTION** Set in a production environment, as it increases security protections.  Not setting it will give detailed debug pages on error.

## Running
The web server is designed to be run within lucos_services, but can be run standalone (see django documentation for details)

## Language support
Some fields support having values in different languages.  Currently this is limited to:
* English
* Irish
* Scottish Gaelic
* Welsh
These are hardcoded values, so can only be change by make source code changes in several places.  Obviously this isn't very scabable, but a scalable solution would require a more complicated database schema and I wasn't sure if there was enough demand for this.

## Creating a new database migration

* Upgrade the approprite `models.py` files
* `docker-compose exec app python manage.py makemigrations`
* `docker cp contacts_app:/usr/src/app/lucosauth/migrations/ app/lucosauth/migrations/`
* `docker cp contacts_app:/usr/src/app/agents/migrations/ app/agents/`
* Commit the new migration files to git
* Rebuild & restart the container for the migrations to take effect.