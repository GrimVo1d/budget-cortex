# budget-cortex

A personal-finance REST API: accounts, transactions, categories, tags, budgets,
transfers between accounts, multi-currency amounts, bank-statement CSV import and
monthly reports.

It is a pet project. The point is the PostgreSQL work behind the endpoints rather
than the CRUD itself:

- running account balance computed with a window function;
- monthly aggregates kept in materialized views, refreshed `CONCURRENTLY` by Celery beat;
- spending rolled up the category tree with a recursive CTE;
- partial and BRIN indexes, a GiST exclusion constraint that forbids overlapping budgets;
- PostgreSQL-only migrations gated by `connection.vendor`, so the test suite also runs on SQLite.

## Features

- JWT auth (register, token, refresh with rotation, logout via blacklist), throttled auth endpoints.
- Every row belongs to a user. Other users' ids behave exactly like non-existent ones (404 or
  "does not exist"), and `DELETE` is a soft delete.
- Atomic transfers, including cross-currency ones with an explicit rate.
- Budgets with a live `status` endpoint (spent, remaining, utilization).
- Reports: monthly cashflow, spending by category with roll-up to the root category,
  budget overruns.
- CSV export (streamed, protected against spreadsheet formula injection).
- CSV import (generic, Tinkoff, Sberbank formats) processed by a Celery worker, idempotent per line.
- Audit log of every create, update and delete of accounts, categories, transactions and
  budgets, attributed to the acting user.
- OpenAPI schema with Swagger UI.

## Stack

Python 3.12, Django 5.2 LTS, Django REST framework, simplejwt, django-filter,
drf-spectacular, Celery 5 with Redis, PostgreSQL 16, gunicorn, Docker Compose.

## Quick start

Requires Docker with Compose v2 and `make`.

```bash
cp .env.example .env
make up                                   # api, worker, beat, db, redis
make migrate
docker compose exec api python manage.py createsuperuser   # optional, for /admin/
```

- API: `http://localhost:8000/api/v1/`
- Swagger UI: `http://localhost:8000/api/schema/swagger-ui/`
- Health: `http://localhost:8000/health/live`, `http://localhost:8000/health/ready`

A walk-through of the API with `curl` is in [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md).

## Checks

Linters and tests run in the `tools` container built from the same Dockerfile; nothing
is installed on the host.

```bash
make lint      # ruff check, ruff format --check, mypy --strict
make test      # pytest on SQLite (PostgreSQL-only tests are skipped)
make test-pg   # pytest on the compose PostgreSQL, including the materialized-view tests
```

## Documentation

- [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md): configuration, make targets, API walk-through.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): apps, data model, SQL techniques, background
  jobs, security.
- [docs/ADR/](docs/ADR/): architecture decision records.
