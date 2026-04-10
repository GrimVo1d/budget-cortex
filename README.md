# budget-cortex

REST service for personal finance tracking: accounts, transactions, categories, budgets, multi-currency support, CSV bank-statement import, and PostgreSQL-powered analytics (window functions, CTEs, materialized views).

## Why

A pet project that exercises non-trivial PostgreSQL work: window functions (running balance), materialized views (monthly aggregates), CTEs for reports, partial indexes, and migrations with history.

## Stack

Python 3.12 · Django 5 · DRF · PostgreSQL 16 · Redis 7 · Celery 5 · Docker · GitHub Actions

## Quick start

```bash
cp .env.example .env
docker compose up -d
docker compose exec api python manage.py migrate
docker compose exec api python manage.py createsuperuser
# API:     http://localhost:8000/api/v1/
# OpenAPI: http://localhost:8000/api/schema/swagger-ui/
```

## Documentation

- [docs/ANALYTICS.md](docs/ANALYTICS.md) — query catalog (materialized views, recursive CTEs, indexes)
- [docs/RUNBOOK.md](docs/RUNBOOK.md) — operational playbook
