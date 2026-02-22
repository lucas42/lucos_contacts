# Lucos contact list

An app for keeping track of personal contacts

## Requirements
* Docker
* Docker Compose

## Architecture
Has three components:
* db - a postgres database
* app - a Django app served using gunicorn
* web - an nginx server for routing traffic to app and serving static files

## Running locally
`docker compose up --build`

## Running tests
`docker compose --profile test up test --build --exit-code-from test`

## Database commands
### Manually creating a backup
(on machine with docker installed)
* `docker exec lucos_contacts_db pg_dump --user postgres postgres > /tmp/contacts.sql`

### Wiping database clean so restore doesn't cause any conflicts
(on machine with docker & docker-compose installed)
* `docker compose exec db dropdb --user postgres postgres`
* `docker compose exec db createdb --user postgres postgres`

### Restoring from backup
(on machine with docker & docker-compose installed)
Assuming the backup file is available on the current machine's /tmp directory, run the following commands:

* `docker compose cp /tmp/contacts.sql db:/tmp/`
* `docker compose exec db sh -c 'dropdb --user postgres postgres && createdb --user postgres postgres'` (To wipe data, if there's an existing DB)
* `docker compose exec db sh -c 'psql --user postgres postgres < /tmp/contacts.sql'`


## Environment Variables:

* **SECRET_KEY** a secret used by django for lots of its security mechanisms.  To generate a new one, run `docker-compose exec app python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
* **PRODUCTION** Set in a production environment, as it increases security protections.  Not setting it will give detailed debug pages on error.