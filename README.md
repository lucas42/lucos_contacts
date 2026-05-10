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
(on machine with docker & docker compose installed)
* `docker compose exec db dropdb --user postgres postgres`
* `docker compose exec db createdb --user postgres postgres`

### Restoring from backup
(on machine with docker & docker compose installed)
Assuming the backup file is available on the current machine's /tmp directory, run the following commands:

* `docker compose cp /tmp/contacts.sql db:/tmp/`
* `docker compose exec db sh -c 'dropdb --user postgres postgres && createdb --user postgres postgres'` (To wipe data, if there's an existing DB)
* `docker compose exec db sh -c 'psql --user postgres postgres < /tmp/contacts.sql'`


## Relationship Audit Command

`python manage.py audit_relationship_closure`

This one-time management command audits the `Relationship` table for consistency with the
inference engine.  It computes the full inference closure of the existing data and compares
it against what is actually stored in the database, reporting:

* **Missing rows** — inferences the engine should have materialised but which are absent
  (e.g. due to historical bugs or data imported before the engine existed).
* **Extraneous rows** — rows present in the database that the engine could not produce from
  the remaining data.

By default the command is read-only (safe to run at any time).  Pass `--apply-missing` to
automatically create the missing rows; extraneous rows are always left for human review.

**This command must be run (and any extraneous rows reconciled with @lucas42) before the
deletion-semantics change described in ADR-0001 and issue #691 is enabled in production.**

Cross-reference: [docs/adr/0001-relationship-deletion-semantics.md](docs/adr/0001-relationship-deletion-semantics.md).

To run against the live app container:

```sh
docker compose exec app python manage.py audit_relationship_closure
docker compose exec app python manage.py audit_relationship_closure --apply-missing
```

## Environment Variables:

* **SECRET_KEY** a secret used by django for lots of its security mechanisms.  To generate a new one, run `docker compose exec app python manage.py shell -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
* **PRODUCTION** Set in a production environment, as it increases security protections.  Not setting it will give detailed debug pages on error.