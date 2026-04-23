"""PostgreSQL-only paths: materialized views, raw-SQL reports, PG DDL.

Run with ``make test-pg``; skipped on SQLite.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.models import ProtectedError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analytics.queries.by_category import by_category_report
from apps.analytics.queries.cashflow import cashflow_report
from apps.analytics.queries.overruns import overruns_report
from apps.budgets.models import Budget, BudgetPeriod
from apps.core.models import AuditAction, AuditLog
from apps.ledger.services import TransferRequest, create_transfer
from tasks.analytics import refresh_materialized_views
from tests.factories import make_account, make_category, make_tx

pytestmark = [pytest.mark.requires_postgres, pytest.mark.django_db(transaction=True)]

APRIL = datetime(2026, 4, 10, tzinfo=UTC)


@pytest.fixture
def ledger(user: Any) -> dict[str, Any]:
    food = make_category(user, "Food")
    cafe = make_category(user, "Cafe", parent=food)
    salary = make_category(user, "Salary", kind="income")
    acc = make_account(user)
    make_tx(acc, "-60.00", APRIL, food)
    make_tx(acc, "-70.00", APRIL, cafe)
    make_tx(acc, "1000.00", APRIL, salary)
    make_tx(acc, "-5.00", datetime(2026, 5, 3, tzinfo=UTC), food)
    return {"food": food, "cafe": cafe, "salary": salary, "account": acc}


def test_first_refresh_populates_then_refreshes_concurrently(ledger: dict[str, Any]) -> None:
    first = refresh_materialized_views()
    second = refresh_materialized_views()
    assert set(first.values()) == {"populated"}
    assert set(second.values()) == {"ok"}


def test_cashflow_report(user: Any, ledger: dict[str, Any]) -> None:
    refresh_materialized_views()
    rows = cashflow_report(user.pk, date(2026, 4, 1), date(2026, 6, 1))
    assert [(r.month, r.income, r.expense, r.net) for r in rows] == [
        (date(2026, 4, 1), Decimal("1000.00"), Decimal("130.00"), Decimal("870.00")),
        (date(2026, 5, 1), Decimal("0.00"), Decimal("5.00"), Decimal("-5.00")),
    ]


def test_cashflow_counts_uncategorized_and_skips_transfers(
    user: Any, ledger: dict[str, Any]
) -> None:
    acc = ledger["account"]
    make_tx(acc, "-40.00", APRIL)  # e.g. a CSV import row: no category
    make_tx(acc, "15.00", APRIL)
    create_transfer(
        TransferRequest(
            user_id=user.pk,
            from_account=acc,
            to_account=make_account(user, name="Savings"),
            amount=Decimal("500.00"),
            occurred_at=APRIL,
        )
    )
    refresh_materialized_views()
    [april] = cashflow_report(user.pk, date(2026, 4, 1), date(2026, 5, 1))
    assert (april.income, april.expense, april.net) == (
        Decimal("1015.00"),
        Decimal("170.00"),
        Decimal("845.00"),
    )


def test_by_category_rolls_children_up_to_root(user: Any, ledger: dict[str, Any]) -> None:
    refresh_materialized_views()
    rows = by_category_report(user.pk, date(2026, 4, 1), date(2026, 5, 1))
    by_name = {r.category_name: r for r in rows}
    assert by_name["Cafe"].root_name == "Food"
    assert by_name["Cafe"].total_expense == Decimal("70.00")
    assert by_name["Food"].total_expense == Decimal("60.00")
    assert "Salary" not in by_name


def test_overruns_include_child_categories(user: Any, ledger: dict[str, Any]) -> None:
    Budget.objects.create(
        user=user,
        category=ledger["food"],
        period=BudgetPeriod.MONTHLY,
        period_start=datetime(2026, 4, 1, tzinfo=UTC),
        period_end=datetime(2026, 5, 1, tzinfo=UTC),
        limit_amount=Decimal("100.00"),
        currency="RUB",
    )
    refresh_materialized_views()
    [row] = overruns_report(user.pk)
    assert row.spent_amount == Decimal("130.00")
    assert row.overrun_pct == Decimal("130.00")


def test_overruns_cover_budgets_not_aligned_to_months(user: Any, ledger: dict[str, Any]) -> None:
    Budget.objects.create(
        user=user,
        category=ledger["food"],
        period=BudgetPeriod.CUSTOM,
        period_start=datetime(2026, 4, 1, tzinfo=UTC),
        period_end=datetime(2026, 4, 28, tzinfo=UTC),
        limit_amount=Decimal("100.00"),
        currency="RUB",
    )
    refresh_materialized_views()
    [row] = overruns_report(user.pk)
    assert row.spent_amount == Decimal("130.00")


def test_reports_api_end_to_end(client: APIClient, ledger: dict[str, Any]) -> None:
    refresh_materialized_views()
    resp = client.get("/api/v1/reports/cashflow/", {"from": "2026-04", "to": "2026-05"})
    assert resp.json()[0]["net"] == "870.00"
    bad = client.get("/api/v1/reports/cashflow/", {"from": "2026-05", "to": "2026-04"})
    assert bad.json()["code"] == "invalid_range"


def test_reports_answer_503_until_views_are_built(
    client: APIClient, ledger: dict[str, Any]
) -> None:
    refresh_materialized_views()
    with connection.cursor() as cur:
        cur.execute("REFRESH MATERIALIZED VIEW mv_monthly_cashflow WITH NO DATA")
    resp = client.get("/api/v1/reports/cashflow/", {"from": "2026-04", "to": "2026-05"})
    assert resp.status_code == 503
    assert resp.json()["code"] == "report_not_ready"
    assert refresh_materialized_views()["mv_monthly_cashflow"] == "populated"


def test_budget_overlap_is_enforced_by_database(user: Any) -> None:
    food = make_category(user)
    common = {
        "user": user,
        "category": food,
        "period": BudgetPeriod.CUSTOM,
        "limit_amount": Decimal("1"),
        "currency": "RUB",
    }
    Budget.objects.create(
        **common, period_start=APRIL, period_end=datetime(2026, 4, 20, tzinfo=UTC)
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        Budget.objects.create(
            **common,
            period_start=datetime(2026, 4, 15, tzinfo=UTC),
            period_end=datetime(2026, 4, 30, tzinfo=UTC),
        )
    # A soft-deleted budget no longer blocks the period.
    Budget.objects.update(is_deleted=True, deleted_at=timezone.now())
    Budget.objects.create(
        **common,
        period_start=datetime(2026, 4, 15, tzinfo=UTC),
        period_end=datetime(2026, 4, 30, tzinfo=UTC),
    )


def test_pg_only_indexes_exist() -> None:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'ledger_transaction'"
        )
        indexes = dict(cur.fetchall())
    assert "USING brin" in indexes["tx_occurred_at_brin"]


def test_audit_log_is_append_only(other_user: Any) -> None:
    entry = AuditLog.objects.create(
        actor=other_user, model="Account", object_id="1", action=AuditAction.CREATE
    )
    for attempt in (
        lambda: AuditLog.objects.filter(pk=entry.pk).update(after={"forged": True}),
        lambda: AuditLog.objects.filter(pk=entry.pk).update(actor=None),
        lambda: AuditLog.objects.filter(pk=entry.pk).delete(),
    ):
        with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
            attempt()

    # The actor cannot be deleted from under the log either.
    with pytest.raises(ProtectedError):
        other_user.delete()
    entry.refresh_from_db()
    assert entry.actor_id == other_user.pk

    with connection.cursor() as cur:
        cur.execute("SELECT proconfig FROM pg_proc WHERE proname = 'core_auditlog_append_only'")
        assert cur.fetchone()[0] == ["search_path=pg_catalog, pg_temp"]
