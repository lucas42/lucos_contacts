---
description: How to create and apply database migrations
---
To create and apply new database migrations, follow these steps:

1. Ensure the docker containers are running:
```bash
docker compose up -d
```

2. Run makemigrations inside the running container:
// turbo
```bash
docker compose exec app python manage.py makemigrations
```

3. Copy the newly created migration files from the container back to the host system:
// turbo
```bash
docker cp lucos_contacts_app:/usr/src/app/agents/migrations/ app/agents/
```
(Note: Replace `agents` with the appropriate module if migrations were created elsewhere.)

4. Rebuild and restart the container for the migrations to take effect:
```bash
docker compose up --build -d
```

5. Verify tests pass:
```bash
docker compose up test --build --exit-code-from test
```
