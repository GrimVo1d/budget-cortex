.PHONY: help up down restart logs ps migrate makemigrations shell dbshell test test-unit test-integration lint fmt refresh-views clean

COMPOSE := docker compose

help:
	@echo "Targets:"
	@echo "  up                docker compose up -d"
	@echo "  down              docker compose down"
	@echo "  restart           restart api + worker"
	@echo "  logs              tail logs from all services"
	@echo "  ps                list running services"
	@echo "  migrate           run django migrations"
	@echo "  makemigrations    create new migrations"
	@echo "  shell             open django shell"
	@echo "  dbshell           open psql against the db service"
	@echo "  test              run full pytest suite"
	@echo "  test-unit         run unit tests only"
	@echo "  test-integration  run integration tests only"
	@echo "  lint              ruff + black --check + mypy"
	@echo "  fmt               black + isort + ruff --fix"
	@echo "  refresh-views     refresh all materialized views"
	@echo "  clean             remove caches and pyc"

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart api worker

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
	$(COMPOSE) exec db psql -U bc -d budget_cortex

test:
	pytest -q

test-unit:
	pytest -q tests/unit

test-integration:
	pytest -q tests/integration

lint:
	ruff check src tests
	black --check src tests
	mypy src

fmt:
	isort src tests
	black src tests
	ruff check --fix src tests

refresh-views:
	$(COMPOSE) exec api python manage.py refresh_views

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .mypy_cache .ruff_cache .pytest_cache .coverage htmlcov
