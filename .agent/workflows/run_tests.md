---
description: How to run the tests for this project
---
This project uses Docker Compose to run tests, ensuring all dependencies and database hostnames are correctly configured.

## Prerequisites
* Docker
* Docker Compose

## Running the Tests
To run the full test suite, use the following command from the root of the project:

// turbo
```bash
docker compose --profile test up test --build --exit-code-from test
```

### Expected Output
The test suite should run and all tests should pass successfully.

```text
Found ... test(s).
...
Ran ... tests in ...s

OK
```

### Why use Docker?
Some tests rely on database queries, and the Django settings connect to a database hostname (`db`) which is defined in `docker-compose.yml`. Running tests outside of Docker is convoluted and discouraged.
