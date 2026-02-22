# Agent Instructions

This directory contains instructions and workflows for AI agents working on the Lucos Contacts project.

## Workflows
- [Setup Environment](./workflows/setup_environment.md) - How to set up the project (Docker or Local).
- [Run Tests](./workflows/run_tests.md) - How to run the test suite using Docker Compose.

## Key Rules
- Always use Docker for running tests (`docker compose --profile test up test ...`).
- Some tests require a database connection which is handled by the Docker network.
