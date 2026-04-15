.PHONY: help up down logs ps migrate makemigrations shell dbshell refresh-views \
        tools lint fmt typecheck test test-pg lock clean

COMPOSE := docker compose
TOOLS   := $(COMPOSE) run --rm --no-deps tools
TOOLS_DB := $(COMPOSE) run --rm tools
UV_IMAGE := ghcr.io/astral-sh/uv:python3.12-bookworm-slim

help:
	@echo "Stack:"
	@echo "  up               build and start api, worker, beat, db, redis"
	@echo "  down             stop the stack"
	@echo "  logs / ps        follow logs / list services"
	@echo "  migrate          apply migrations"
	@echo "  makemigrations   create new migrations"
	@echo "  shell / dbshell  django shell / psql"
	@echo "  refresh-views    refresh analytics materialized views now"
	@echo "Checks (run in the tools container):"
	@echo "  lint             ruff check + ruff format --check + mypy"
	@echo "  fmt              ruff format + ruff check --fix"
	@echo "  test             pytest on SQLite"
	@echo "  test-pg          pytest on PostgreSQL (includes requires_postgres tests)"
	@echo "  lock             regenerate requirements/*.txt from pyproject.toml"
	@echo "  clean            remove local caches"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=200

ps:
	$(COMPOSE) ps

migrate:
	$(COMPOSE) exec api python manage.py migrate

makemigrations:
	$(COMPOSE) exec api python manage.py makemigrations

shell:
	$(COMPOSE) exec api python manage.py shell

dbshell:
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

refresh-views:
	$(COMPOSE) exec api python manage.py refresh_views

tools:
	$(COMPOSE) build tools

lint:
	$(TOOLS) sh -c 'ruff check . && ruff format --check . && mypy src'

fmt:
	$(TOOLS) sh -c 'ruff format . && ruff check --fix .'

test:
	$(TOOLS) pytest

test-pg:
	$(TOOLS_DB) sh -c 'TEST_DATABASE_URL="$$PG_TEST_DATABASE_URL" pytest'

lock:
	docker run --rm -v "$(CURDIR)":/src -w /src $(UV_IMAGE) sh -c '\
	  uv pip compile pyproject.toml --python-version 3.12 --generate-hashes -o requirements/runtime.txt -q && \
	  uv pip compile pyproject.toml --extra dev --python-version 3.12 --generate-hashes -o requirements/dev.txt -q'

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov
