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

## Running
`PRODUCTION=true SECRET_KEY=<secret> nice -19 docker-compose up -d --no-build`


## Database commands
### Manually creating a backup
(on machine with docker installed)
* `docker exec lucos_contacts_db_1 pg_dump --user postgres postgres > /tmp/contacts.sql`

### Wiping database clean so restore doesn't cause any conflicts
(on machine with docker & docker-compose installed)
* `docker-compose exec db dropdb --user postgres postgres`
* `docker-compose exec db createdb --user postgres postgres`

### Restoring from backup
(on machine with docker & docker-compose installed)
Assuming the backup file is available over ssh on another machine, run the following commands:

* `docker-compose exec db apk add openssh-client`
* `docker-compose exec db scp <user@hostname>:/tmp/contacts.sql /tmp/contacts.sql`
* `docker-compose exec db sh -c 'psql --user postgres postgres < /tmp/contacts.sql'`
