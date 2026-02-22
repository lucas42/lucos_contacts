---
description: How to set up the project environment
---
This project should be set up using either Docker (preferred) or a local Python virtual environment.
When interacting with this project, do not attempt to invoke global `python` or `pipenv` directly if they are not explicitly configured. Instead, follow one of the two approaches below.

## Approach 1: Docker & Docker Compose (Preferred)

The preferred approach for reproducible environments is to use Docker and Docker Compose. You can run commands against the `app` service or the `test` service in the `docker-compose.yml`.

Example of running a simple Django command:

```bash
# Wait to see if containers need to be built/started, or just run a one-off command:
docker compose run --rm app python manage.py check

# If you need to run the test suite:
docker compose --profile test up test --build --exit-code-from test
```

## Approach 2: Virtual Environment with System Python

If you need to interact with Python locally, use the system Python (which might only be available as `python3` instead of `python`). The exact python version might not match the project's python version perfectly, but you can create a local `venv` and install the project dependencies specified in the `Pipfile` and `Pipfile.lock`.

Here is a turbo-all enabled script to do this:

```bash
// turbo-all
# navigate to the directory containing the Pipfile
cd app

# create the venv using system python3
python3 -m venv .venv

# activate the venv
source .venv/bin/activate

# ensure pipenv is installed in the venv, and install deps
pip install pipenv
pipenv sync

# Note for MacOS users/agents: If the system lacks postgres C libraries (`libpq`),
# psycopg won't load properly and will raise an ImportError. 
# Fix this by installing the pre-compiled binary:
pip install "psycopg[binary]"

# Export the environment variables required by Django from the root .env file
export $(grep -v '^#' ../.env | xargs)

# Now you can run django commands locally
python manage.py check
```
