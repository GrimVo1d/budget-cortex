# Runbook

Краткие сценарии реагирования на алерты. Все команды предполагают
`docker compose` окружение; для prod — заменить на kubectl exec.

## 1. MV refresh failure

**Симптом:** алерт `mv_refresh_failed`, отчёты "застряли" на старых данных.

**Действия:**
1. `docker compose logs worker | tail -100` — найти причину (lock, OOM,
   transient).
2. Если CONCURRENTLY упал из-за lock conflict — задача сама fallback'нет
   на блокирующий REFRESH в следующем тике.
3. Если стабильно падает: проверить наличие unique-индексов на MV
   (`\d mv_monthly_cashflow` в psql).

## 2. Import job hang (status='parsing' > 10 min)

**Симптом:** `CsvImport.status = parsing` дольше 10 минут.

**Действия:**
1. Проверить worker liveness (`docker compose ps`).
2. Найти job: `select id, file_path from imports_app_csvimport where status='parsing';`
3. Если worker умер — переставить статус в `pending` и перепоставить:
   `tasks.imports.parse_csv_import.delay(<id>)`.

## 3. FX fetch stale (rate > 36h)

**Симптом:** `fx_rate_stale` алерт.

**Действия:**
1. `docker compose logs worker | grep fx`.
2. Если внешний провайдер недоступен — fallback на stub до восстановления:
   `FX_PROVIDER=stub` в env, рестарт worker.

## 4. Audit log gap

**Симптом:** мутирующие операции есть, в `audit_log` — нет записей.

**Действия:**
1. Проверить, что `AuditMiddleware` присутствует в `MIDDLEWARE`.
2. Проверить, что соответствующая модель зарегистрирована в
   `apps/core/audit.py` (signal-handlers).

## 5. Overrun false-positive

**Симптом:** пользователь жалуется, что бюджет помечен overrun, но он
точно вписался.

**Действия:**
1. Возможно, MV ещё не обновился. Принудительный refresh:
   `docker compose exec api python manage.py shell -c
   "from tasks.analytics import refresh_materialized_views as r; r()"`.
2. Если расхождение остаётся — проверить, что `budget.currency`
   совпадает с currency транзакций (overrun-отчёт сравнивает только
   одинаковые валюты).
