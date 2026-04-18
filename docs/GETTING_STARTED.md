# Getting started

Everything runs in Docker: the stack through Docker Compose, linters and tests in the
`tools` container. You need Docker with Compose v2 and `make`; the `curl` examples
below also use `jq`.

## 1. Configure

```bash
cp .env.example .env
```

The defaults work for local use as they are. The `dev-insecure-*` secrets are
accepted only by the development settings; production settings refuse to start
with them.

## 2. Start the stack

```bash
make up        # build the image, start api, worker, beat, db, redis
make migrate   # apply migrations to PostgreSQL
make ps        # api should be "healthy" after a few seconds
```

| Service  | What it runs                                         | Published on                     |
|----------|------------------------------------------------------|----------------------------------|
| `api`    | gunicorn, Django development settings                | `127.0.0.1:${API_PORT:-8000}`    |
| `worker` | Celery worker on the `default` and `low` queues      | —                                |
| `beat`   | Celery beat (schedule in [ARCHITECTURE](ARCHITECTURE.md#background-jobs)) | —     |
| `db`     | PostgreSQL 16                                        | `127.0.0.1:${DB_PORT:-5432}`     |
| `redis`  | Redis 7 with a password: cache, broker, results      | not published                    |

Ports are bound to `127.0.0.1` only. Uploaded CSV files live in the `media` volume,
the database in `pgdata`.

Optionally create an admin user for `/admin/` (users, groups and the token blacklist; the
API does not need it):

```bash
docker compose exec api python manage.py createsuperuser
```

## 3. Try the API

The interactive schema is at `http://localhost:8000/api/schema/swagger-ui/`. The same
flow from a shell:

```bash
API=http://localhost:8000/api/v1
json=(-H 'Content-Type: application/json')

# Register and get a token pair (access: 15 min, refresh: 7 days).
curl -s "${json[@]}" -d '{"username":"alice","email":"alice@mail.internal","password":"Corr3ct-Horse-Battery"}' \
  $API/auth/register/
TOKENS=$(curl -s "${json[@]}" -d '{"username":"alice","password":"Corr3ct-Horse-Battery"}' $API/auth/token/)
auth=(-H "Authorization: Bearer $(jq -r .access <<<"$TOKENS")")

# Accounts and categories.
CARD=$(curl -s "${auth[@]}" "${json[@]}" -d '{"name":"Card","type":"debit","currency":"RUB","opening_balance":"1000.00"}' \
  $API/accounts/ | jq .id)
SAVINGS=$(curl -s "${auth[@]}" "${json[@]}" -d '{"name":"Savings","type":"savings","currency":"USD"}' \
  $API/accounts/ | jq .id)
FOOD=$(curl -s "${auth[@]}" "${json[@]}" -d '{"name":"Food","kind":"expense"}' $API/categories/ | jq .id)
CAFE=$(curl -s "${auth[@]}" "${json[@]}" -d "{\"name\":\"Cafe\",\"kind\":\"expense\",\"parent\":$FOOD}" \
  $API/categories/ | jq .id)

# Transactions: signed amounts, negative is an outflow.
curl -s "${auth[@]}" "${json[@]}" -d "{\"account\":$CARD,\"amount\":\"-300.00\",\"currency\":\"RUB\",
  \"category\":$FOOD,\"occurred_at\":\"2026-10-02T12:00:00Z\"}" $API/transactions/
curl -s "${auth[@]}" "${json[@]}" -d "{\"account\":$CARD,\"amount\":\"-450.50\",\"currency\":\"RUB\",
  \"category\":$CAFE,\"occurred_at\":\"2026-10-03T13:00:00Z\"}" $API/transactions/

# The list carries the running balance of the account after each transaction.
curl -s "${auth[@]}" "$API/transactions/?account=$CARD&ordering=occurred_at" \
  | jq '.results[] | {occurred_at, amount, running_balance}'

# Cross-currency transfer: the rate is required, both legs are created atomically.
curl -s "${auth[@]}" "${json[@]}" -d "{\"from_account\":$CARD,\"to_account\":$SAVINGS,\"amount\":\"185.00\",
  \"fx_rate\":\"0.0108108108\",\"occurred_at\":\"2026-10-04T10:00:00Z\"}" $API/transactions/transfer/

# A monthly budget for Food (children included) and its live status.
BUDGET=$(curl -s "${auth[@]}" "${json[@]}" -d "{\"category\":$FOOD,\"period\":\"monthly\",
  \"period_start\":\"2026-10-01T00:00:00Z\",\"period_end\":\"2026-11-01T00:00:00Z\",
  \"limit_amount\":\"500.00\",\"currency\":\"RUB\"}" $API/budgets/ | jq .id)
curl -s "${auth[@]}" $API/budgets/$BUDGET/status/

# Import a bank statement. The worker parses it; poll the job until "done".
printf 'date,amount,description\n2026-10-06,-120.00,Groceries\n2026-10-07,-80.00,Bakery\n' > /tmp/bank.csv
JOB=$(curl -s "${auth[@]}" -F account=$CARD -F fmt=generic -F file=@/tmp/bank.csv $API/imports/ | jq .id)
curl -s "${auth[@]}" $API/imports/$JOB/

# Reports read materialized views; beat refreshes them hourly, or do it now.
make refresh-views
curl -s "${auth[@]}" "$API/reports/cashflow/?from=2026-10&to=2026-11"
curl -s "${auth[@]}" "$API/reports/by-category/?from=2026-10&to=2026-11"
curl -s "${auth[@]}" $API/reports/overruns/

# CSV export takes the same filters as the list.
curl -s "${auth[@]}" "$API/transactions/export/?account=$CARD" -o transactions.csv

# Refresh rotates the pair; logout blacklists a refresh token.
NEW=$(curl -s "${json[@]}" -d "{\"refresh\":\"$(jq -r .refresh <<<"$TOKENS")\"}" $API/auth/token/refresh/)
curl -s "${auth[@]}" "${json[@]}" -d "{\"refresh\":\"$(jq -r .refresh <<<"$NEW")\"}" $API/auth/logout/
```

Report months are half-open: `from=2026-10&to=2026-11` means October only.

Errors always have the same shape, with a stable `code` to branch on:

```json
{"code": "invalid_month", "detail": "'from' must be YYYY-MM, got '2026-13'"}
{"code": "validation_error", "detail": {"amount": ["This field is required."]}}
{"code": "not_found", "detail": "No Transaction matches the given query."}
```

Codes that need a client reaction: `report_not_ready` (503, the materialized views have not
been refreshed since `migrate`; run `make refresh-views`), `queue_unavailable` (503, the
broker is down; upload the file again later), `category_has_children` (409, delete or move
the children first), `conflict` (409, a uniqueness rule caught by the database).

Transaction filters `occurred_from` and `occurred_to` are both inclusive. Lists are ordered
by `-occurred_at` by default; `ordering` accepts other fields and always ends with the id.

### CSV formats

| `fmt`      | Layout                                                                 |
|------------|------------------------------------------------------------------------|
| `generic`  | Header row with `date` and `amount`, optional `currency` and `description`, any column order. ISO 8601 dates. |
| `tinkoff`  | `;`-separated: `DD.MM.YYYY HH:MM:SS;amount;currency;description`, decimal comma allowed. The first line is a header and is skipped. |
| `sberbank` | `DD.MM.YYYY,amount,description`, always RUB. The first line is a header and is skipped. |

Rows without a currency take the account's currency. Times without a zone are UTC.
Re-uploading the same file returns `409 duplicate_file`, unless its earlier import
failed: then the same job is retried. An overlapping statement only inserts the lines
that are new. Files over `IMPORT_MAX_BYTES` get `413`. A job that stays `pending` for a
day (the worker never picked it up) is marked `failed` by the weekly cleanup.

## 4. Make targets

| Target           | What it does                                                        |
|------------------|---------------------------------------------------------------------|
| `up` / `down`    | Build and start the stack / stop it                                 |
| `logs` / `ps`    | Follow logs / list services                                         |
| `migrate`        | `manage.py migrate` in the api container                            |
| `makemigrations` | `manage.py makemigrations` in the api container                     |
| `shell`          | Django shell                                                        |
| `dbshell`        | `psql` in the db container                                          |
| `refresh-views`  | Refresh the analytics materialized views now                        |
| `tools`          | Build the `tools` image (linters, test stack)                       |
| `lint`           | `ruff check`, `ruff format --check`, `mypy` (strict)                |
| `fmt`            | `ruff format` and `ruff check --fix`                                |
| `test`           | pytest on in-memory SQLite                                          |
| `test-pg`        | pytest against the compose PostgreSQL, PostgreSQL-only tests included |
| `lock`           | Regenerate the hash-pinned `requirements/*.txt` from `pyproject.toml` |
| `clean`          | Remove local caches                                                 |

`make test-pg` starts `db` if needed and uses a separate `test_*` database, so it does
not touch the stack's data.

The image entrypoint takes a role as its first argument: `api` (gunicorn on :8000),
`worker [queues]` (default `default,low`), `beat`, `migrate`; anything else is executed
as a command.

## 5. Configuration reference

Application settings (read by Django from the environment or `.env`):

| Variable | Default | Notes |
|----------|---------|-------|
| `DJANGO_SETTINGS_MODULE` | `budget_cortex.settings.prod` in the image, `.dev` in compose | `dev`, `prod` or `test` |
| `SECRET_KEY` | dev value in `dev` | `prod`: required, ≥ 32 chars, not `dev-insecure*` |
| `JWT_SIGNING_KEY` | dev value in `dev` | `prod`: same rules, must differ from `SECRET_KEY` |
| `DEBUG` | `1` in `dev` | always off in `prod` |
| `ALLOWED_HOSTS` | `localhost`, `127.0.0.1`, `[::1]` in `dev` | `prod`: required, e.g. `api.budget-cortex.internal` |
| `DATABASE_URL` | SQLite file | compose builds it from `POSTGRES_*`; `prod`: required |
| `REDIS_URL` | `redis://localhost:6379/0` | Django cache (FX rates, throttling); `prod`: required |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis db 1 / db 2 | `prod`: required |
| `MEDIA_ROOT` | `./media` | uploaded CSV files go to `MEDIA_ROOT/imports/` |
| `IMPORT_MAX_BYTES` | `5242880` | upload size limit; set the proxy's body limit a little above it |
| `FX_PROVIDER` | `stub` | the only shipped provider (fixed rates) |
| `FX_BASE_CURRENCY` | `RUB` | target of the daily FX fetch |
| `THROTTLE_ANON` / `THROTTLE_USER` / `THROTTLE_AUTH` | `60/min` / `600/min` / `10/min` | `auth` applies to register, token, refresh, logout |
| `NUM_PROXIES` | `0` | trusted reverse proxies in front of the API; throttling reads the client address from `X-Forwarded-For` only when this is set |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `plain` | `json` is forced in `prod` |
| `SECURE_SSL_REDIRECT` / `SECURE_HSTS_SECONDS` | `1` / one year | `prod` only; `/health/*` is never redirected |
| `TEST_DATABASE_URL` | in-memory SQLite | `test` settings; `make test-pg` points it at PostgreSQL |

Compose and container variables:

| Variable | Default | Notes |
|----------|---------|-------|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `bc` / `bc` / `budget_cortex` | |
| `REDIS_PASSWORD` | `bc` | |
| `API_PORT` / `DB_PORT` | `8000` / `5432` | host ports on 127.0.0.1 |
| `GUNICORN_WORKERS` / `GUNICORN_TIMEOUT` | `4` / `30` | `api` role |
| `CELERY_CONCURRENCY` / `CELERY_LOG_LEVEL` | `4` / `INFO` | `worker` and `beat` roles |

## 6. Production settings

`budget_cortex.settings.prod` is the image default. It expects TLS to terminate at a
reverse proxy that sets `X-Forwarded-Proto`, redirects plain HTTP (except `/health/`),
sends HSTS and secure cookies, and logs JSON. Set `NUM_PROXIES=1` behind a single proxy,
otherwise every client shares the proxy's throttle bucket. The OpenAPI schema and Swagger
UI are served to staff users only. It fails at startup when a secret, `ALLOWED_HOSTS`,
`DATABASE_URL`, `REDIS_URL` or a Celery URL is missing. A quick way to check a
configuration:

```bash
docker compose run --rm --no-deps \
  -e DJANGO_SETTINGS_MODULE=budget_cortex.settings.prod \
  -e SECRET_KEY="$(openssl rand -hex 32)" -e JWT_SIGNING_KEY="$(openssl rand -hex 32)" \
  -e ALLOWED_HOSTS=api.budget-cortex.internal \
  -e REDIS_URL=redis://redis:6379/0 -e CELERY_BROKER_URL=redis://redis:6379/1 \
  -e CELERY_RESULT_BACKEND=redis://redis:6379/2 \
  api python manage.py check --deploy
```

It reports two warnings, `SECURE_HSTS_INCLUDE_SUBDOMAINS` and `SECURE_HSTS_PRELOAD`: both
commit the whole domain to HTTPS, so they are left for the deployment to decide.
