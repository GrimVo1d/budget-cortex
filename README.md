# budget-cortex

REST-сервис для учёта личных финансов: счета, транзакции, категории, бюджеты, мультивалютность, импорт банковских CSV-выписок и аналитика поверх PostgreSQL (window functions, CTE, materialized views).

## Зачем

Pet-проект, демонстрирующий нетривиальную работу с PostgreSQL: оконные функции (running balance), материализованные представления (месячные сводки), CTE для отчётов, partial-индексы, миграции с историей.

## Стек

Python 3.12 · Django 5 · DRF · PostgreSQL 16 · Redis 7 · Celery 5 · Docker · GitHub Actions

## Быстрый старт (после реализации)

```bash
cp .env.example .env
docker compose up -d
docker compose exec api python manage.py migrate
docker compose exec api python manage.py createsuperuser
# API:     http://localhost:8000/api/v1/
# OpenAPI: http://localhost:8000/api/schema/swagger-ui/
```

## Документация

- [docs/SPEC.md](docs/SPEC.md) — техническое задание
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — компоненты и потоки данных
- [docs/ROADMAP.md](docs/ROADMAP.md) — пошаговый план реализации
