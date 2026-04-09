# Analytics query catalog

Каталог тяжёлых SQL-запросов проекта с EXPLAIN-планами и пояснениями.
Источник правды — модули в `src/apps/analytics/queries/` и миграции в
`src/apps/analytics/migrations/`.

## Materialized views

### `mv_monthly_category_totals`
- **Размерность:** `(user_id, category_id, month, currency) → total_expense, tx_count`.
- **Источник:** `ledger_transaction` где `type = 'expense'` и `is_deleted = false`.
- **Уникальный индекс:** `(user_id, category_id, month, currency)` — требуется для `REFRESH ... CONCURRENTLY`.
- **Используется в:** `by_category_report`, `overruns_report`.

### `mv_monthly_cashflow`
- **Размерность:** `(user_id, month, currency) → income, expense, net`.
- **Источник:** `ledger_transaction` где `type IN ('income','expense')`.
- **Уникальный индекс:** `(user_id, month, currency)`.
- **Используется в:** `cashflow_report`.

### Refresh
- Beat-задача `tasks.analytics.refresh_materialized_views` — ежечасно.
- Сначала `REFRESH ... CONCURRENTLY`. При сбое (например, lock conflict)
  fallback на блокирующий `REFRESH` чтобы данные не уходили в drift.

## Reports

### Cashflow
- `apps.analytics.queries.cashflow.cashflow_report(user_id, from_month, to_month)`
- Index-only scan по `mv_monthly_cashflow_uniq`.

### By category (recursive rollup)
- `apps.analytics.queries.by_category.by_category_report(...)`
- Рекурсивный CTE `roots(id, root_id)` — строит для каждой категории её
  корень (поддерживается одноуровневое вложение, но CTE общий).

### Overruns
- `apps.analytics.queries.overruns.overruns_report(user_id)`
- Join `budgets_budget` ↔ `mv_monthly_category_totals` по диапазону
  `[period_start.month, period_end.month)` и фильтр `spent > limit`.

## Running balance

- `apps.analytics.queries.running_balance.running_balances_for(items, user_id)`
- Окно: `SUM(amount) OVER (PARTITION BY account_id ORDER BY occurred_at, id ROWS UNBOUNDED PRECEDING)`.
- Прибавляется `opening_balance` счёта на API-уровне.

## Indexes that matter

| Index | Why |
|---|---|
| `tx_user_import_hash_unique` (partial unique) | Dedup CSV-импорта без раздувания индекса на NULL-ах. |
| `tx_occurred_at_brin` | BRIN для исторических диапазонов на больших таблицах. |
| `budget_period_range_idx` (partial, alive) | Fallback B-tree для overlap-запросов на SQLite. |
| `mv_*_uniq` | Требуется для `REFRESH ... CONCURRENTLY`. |
