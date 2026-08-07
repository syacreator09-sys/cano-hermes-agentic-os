"""K14 (plan HERMES-KICKOFF) -- aggregation behind `GET /api/dashboard/
finance`, `/api/dashboard/orders`, `/api/dashboard/offices`.

Kept out of `api/app.py` (which only wires HTTP) and out of `monitoring.py`
(which owns read-only host/Docker/Baserow *probes*, not sqlite
aggregation) so each dashboard's actual math is a plain, directly-testable
function -- the same split `GET /api/dashboard` (Prometeo F13) already
uses between `monitoring.py`'s probes and `app.py`'s `dashboard_data()`
assembly, just with the sqlite-heavy assembly pulled into its own module
since these three views do meaningfully more of it than F13's did.

Every function here takes its dependencies as plain arguments (a
`SQLiteStore`, a `BudgetService`) instead of importing `api.dependencies`
-- matches `monitoring.py`'s own "no framework imports" discipline, and is
what makes the K14 seeded-data test straightforward: build a throwaway
store, save a few rows, call the function directly, assert on the dict it
returns, with no FastAPI `TestClient` involved.

None of this does network I/O. `offices_dashboard` shells out to `docker`/
`hermes kanban` (via `monitoring`'s short-TTL caches) and touches the
filesystem (office.yaml, output dirs, the K9 usage-file mirror) -- every
one of those calls already degrades to a "sin_datos"/`None` shape instead
of raising, so a GET against this module is never the cause of a 500.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import yaml

from cano_hermes import monitoring
from cano_hermes.bridge import office_launcher, office_usage
from cano_hermes.domain.enums import OrderStatus, TaskStatus
from cano_hermes.governance.budget import BudgetService
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[2]

# Orders whose fan-out/fan-in hasn't finished one way or the other yet --
# mirrors OrderStatus's own docstring ("DONE/FAILED/BLOCKED... share DONE/
# FAILED/BLOCKED in spirit"), except BLOCKED stays "active" here: an order
# waiting on a human gate is still open work, not a terminal outcome, so it
# belongs on the operator's "what's in flight" view, not filtered out of it.
_ACTIVE_ORDER_STATUSES = frozenset({
    OrderStatus.RECEIVED, OrderStatus.DECOMPOSING, OrderStatus.DISPATCHED,
    OrderStatus.AGGREGATING, OrderStatus.BLOCKED,
})


def _execution_cost(execution: dict) -> float:
    """Same field-precedence BudgetService.ingest_usage_file already uses
    (estimated_cost_usd -> cost_usd -> total_cost_usd), applied to an
    execution row's `usage` dict instead of a usage-file's parsed JSON --
    the two shapes are identical by construction (`save_execution`'s
    `usage` argument round-trips whatever `ingest_usage_file` would have
    read from the same report)."""
    usage = execution.get("usage") or {}
    for field in BudgetService.USAGE_COST_FIELDS:
        value = usage.get(field)
        if isinstance(value, (int, float)):
            return float(value)
    return 0.0


def finance_dashboard(
    store: SQLiteStore, budget: BudgetService, *, workspace_root: Path | None = None,
) -> dict[str, Any]:
    """`GET /api/dashboard/finance`'s data: daily ledger, cost by order/
    task/executor/office, and a same-day linear projection against
    `default_daily_budget_usd`."""
    generated_at = dt.datetime.now(dt.UTC)

    try:
        # Best-effort K9 mirror (infrastructure/offices/data/<x>/output/ ->
        # storage/workspaces/office-<x>/) so `cost_by_office` below reflects
        # usage files an office wrote since the last daily_cycle.py run or
        # `offices_dashboard()` call, not just whatever was already
        # mirrored. Cheap (hardlink-or-copy, no network) and idempotent --
        # a failure here must never take the whole finance view down.
        office_usage.sync_office_usage_to_workspaces()
    except OSError:
        pass

    ledger_daily = []
    for row in store.list_budget_ledger(limit=30):
        limit = row["daily_limit_usd"]
        spent = row["spent_usd"]
        percent = (spent / limit) if limit > 0 else 0.0
        ledger_daily.append({
            "day": row["day"],
            "daily_limit_usd": limit,
            "spent_usd": spent,
            "remaining_usd": round(limit - spent, 4),
            "percent_used": round(percent, 4),
            "updated_at": row["updated_at"],
        })

    today = BudgetService.today()
    today_ledger = budget.ledger_for(today)
    percent_used = (today_ledger.spent_usd / today_ledger.daily_limit_usd) if today_ledger.daily_limit_usd > 0 else 0.0
    midnight = generated_at.replace(hour=0, minute=0, second=0, microsecond=0)
    # Floored at 1 second-of-day so the projection never divides by zero in
    # the instant right at UTC midnight -- at that instant spent_usd is
    # necessarily ~0 too, so the projection is ~0 either way, not a crash.
    elapsed_fraction = max((generated_at - midnight).total_seconds(), 1.0) / 86_400.0
    projected_spend = today_ledger.spent_usd / elapsed_fraction
    projected_percent = (projected_spend / today_ledger.daily_limit_usd) if today_ledger.daily_limit_usd > 0 else 0.0

    executions = store.list_executions()
    cost_by_executor: dict[str, float] = {}
    cost_by_task: dict[str, float] = {}
    executor_by_task: dict[str, str] = {}
    total_recorded = 0.0
    priced_count = 0
    for execution in executions:
        cost = _execution_cost(execution)
        executor_by_task.setdefault(execution["task_id"], execution["executor"])
        if cost <= 0:
            continue
        priced_count += 1
        total_recorded += cost
        cost_by_executor[execution["executor"]] = cost_by_executor.get(execution["executor"], 0.0) + cost
        cost_by_task[execution["task_id"]] = cost_by_task.get(execution["task_id"], 0.0) + cost

    tasks_by_id = {t.id: t for t in store.list_tasks()}
    cost_by_order: dict[str, float] = {}
    for task_id, cost in cost_by_task.items():
        task = tasks_by_id.get(task_id)
        parent = task.parent_task_id if task is not None else None
        if parent:
            cost_by_order[parent] = cost_by_order.get(parent, 0.0) + cost

    orders_by_id = {o.id: o for o in store.list_orders()}
    cost_by_order_rows = sorted(
        (
            {
                "order_id": order_id,
                "objective": (orders_by_id[order_id].objective[:120] if order_id in orders_by_id else None),
                "status": (orders_by_id[order_id].status.value if order_id in orders_by_id else None),
                "cost_usd": round(cost, 4),
            }
            for order_id, cost in cost_by_order.items()
        ),
        key=lambda row: row["cost_usd"], reverse=True,
    )

    cost_by_task_rows = sorted(
        (
            {"task_id": task_id, "executor": executor_by_task.get(task_id), "cost_usd": round(cost, 4)}
            for task_id, cost in cost_by_task.items()
        ),
        key=lambda row: row["cost_usd"], reverse=True,
    )[:20]

    cost_by_executor_rows = sorted(
        ({"executor": executor, "cost_usd": round(cost, 4)} for executor, cost in cost_by_executor.items()),
        key=lambda row: row["cost_usd"], reverse=True,
    )

    office_costs = monitoring.office_usage_costs(workspace_root)
    cost_by_office_rows = sorted(
        ({"office": name, "cost_usd": cost} for name, cost in office_costs.items()),
        key=lambda row: row["cost_usd"], reverse=True,
    )

    return {
        "generated_at": generated_at.isoformat(),
        "ledger_daily": ledger_daily,
        "today": {
            "day": today,
            "daily_limit_usd": today_ledger.daily_limit_usd,
            "spent_usd": today_ledger.spent_usd,
            "remaining_usd": round(today_ledger.remaining_usd, 4),
            "percent_used": round(percent_used, 4),
            "elapsed_fraction": round(elapsed_fraction, 4),
            "projected_spend_usd": round(projected_spend, 4),
            "projected_percent_used": round(projected_percent, 4),
        },
        "cost_by_executor": cost_by_executor_rows,
        "cost_by_office": cost_by_office_rows,
        "cost_by_order": cost_by_order_rows,
        "cost_by_task_top": cost_by_task_rows,
        "totals": {
            "all_time_recorded_cost_usd": round(total_recorded, 4),
            "executions_priced": priced_count,
            "executions_total": len(executions),
        },
    }


def orders_dashboard(store: SQLiteStore, *, active_limit: int = 50, throughput_days: int = 14) -> dict[str, Any]:
    """`GET /api/dashboard/orders`'s data: active orders with their
    resolved subtask tree, throughput, failure rate, and a queue-depth
    proxy.

    Queue depth has no single source of truth to read: `QueueService`
    (K3) keeps its live `asyncio.Queue` in-process with no accessor, so
    the closest honest proxy is what's already durable in sqlite --
    `executions` rows still `pending`/`running`, plus `tasks` rows
    `ready`/`running`. Documented here rather than treated as exact.
    """
    generated_at = dt.datetime.now(dt.UTC)
    all_orders = store.list_orders()
    all_tasks = store.list_tasks()
    all_executions = store.list_executions()

    tasks_by_parent: dict[str, list] = {}
    for task in all_tasks:
        if task.parent_task_id:
            tasks_by_parent.setdefault(task.parent_task_id, []).append(task)

    # `list_executions()` is newest-started-first, so the first hit per
    # task_id in this loop is that task's most recent execution.
    latest_execution_by_task: dict[str, dict] = {}
    for execution in all_executions:
        latest_execution_by_task.setdefault(execution["task_id"], execution)

    active_orders_all = [o for o in all_orders if o.status in _ACTIVE_ORDER_STATUSES]
    active_orders = []
    for order in active_orders_all[:active_limit]:
        children = tasks_by_parent.get(order.id, [])
        active_orders.append({
            "id": order.id,
            "objective": order.objective[:200],
            "status": order.status.value,
            "source": order.source,
            "created_at": order.created_at.isoformat(),
            "updated_at": order.updated_at.isoformat(),
            "tasks": [
                {
                    "id": child.id,
                    "title": child.title,
                    "status": child.status.value,
                    "route_profile": child.route_profile,
                    "assigned_agent": child.assigned_agent,
                    "executor": (latest_execution_by_task.get(child.id) or {}).get("executor"),
                }
                for child in children
            ],
        })

    by_day: dict[str, int] = {}
    for order in all_orders:
        day = order.created_at.date().isoformat()
        by_day[day] = by_day.get(day, 0) + 1
    orders_per_day = [{"date": day, "count": count} for day, count in sorted(by_day.items())][-throughput_days:]

    done_at_by_order = {event.task_id: event.created_at for event in store.list_events_by_kind("order.done")}
    durations_seconds = [
        (done_at_by_order[order.id] - order.created_at).total_seconds()
        for order in all_orders
        if order.id in done_at_by_order
    ]
    avg_seconds_to_done = (sum(durations_seconds) / len(durations_seconds)) if durations_seconds else None

    done_count = sum(1 for o in all_orders if o.status == OrderStatus.DONE)
    failed_count = sum(1 for o in all_orders if o.status in (OrderStatus.FAILED, OrderStatus.BLOCKED))
    terminal_count = done_count + failed_count
    failure_rate = (failed_count / terminal_count) if terminal_count else None

    pending_executions = sum(1 for e in all_executions if e["status"] == "pending")
    running_executions = sum(1 for e in all_executions if e["status"] == "running")
    tasks_ready = sum(1 for t in all_tasks if t.status == TaskStatus.READY)
    tasks_running = sum(1 for t in all_tasks if t.status == TaskStatus.RUNNING)

    return {
        "generated_at": generated_at.isoformat(),
        "active_orders": active_orders,
        "active_orders_count": len(active_orders_all),
        "orders_total_count": len(all_orders),
        "throughput": {
            "orders_per_day": orders_per_day,
            "avg_seconds_to_done": (round(avg_seconds_to_done, 2) if avg_seconds_to_done is not None else None),
            "avg_hours_to_done": (round(avg_seconds_to_done / 3600, 2) if avg_seconds_to_done is not None else None),
            "sample_size": len(durations_seconds),
        },
        "failure_rate": {
            "done_count": done_count,
            "failed_or_blocked_count": failed_count,
            "rate": (round(failure_rate, 4) if failure_rate is not None else None),
        },
        "queue": {
            "pending_executions": pending_executions,
            "running_executions": running_executions,
            "tasks_ready": tasks_ready,
            "tasks_running": tasks_running,
            "note": (
                "aproximación desde sqlite (executions.status pending/running + "
                "tasks.status ready/running) -- QueueService (K3) mantiene su "
                "asyncio.Queue en memoria de proceso, sin accessor de tamaño; "
                "esto es el proxy más cercano disponible sin tocar QueueService."
            ),
        },
    }


def _office_budget_daily_usd(kanban_profile: str | None, offices_root: Path | None = None) -> float | None:
    """`budget_daily.usd` from a K9 `offices/<profile>/office.yaml`, or
    None when the profile/file/field doesn't resolve -- mirrors
    `governance/auto_approval.load_office_never`'s own "missing manifest
    is not an error" contract."""
    if not kanban_profile:
        return None
    root = offices_root or (ROOT / "offices")
    manifest_path = root / kanban_profile / "office.yaml"
    if not manifest_path.is_file():
        return None
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    usd = (data.get("budget_daily") or {}).get("usd")
    return float(usd) if isinstance(usd, (int, float)) else None


def offices_dashboard(*, docker_stats_ttl: float = 30.0, kanban_stats_ttl: float = 30.0) -> dict[str, Any]:
    """`GET /api/dashboard/offices`'s data: up/down, last real run,
    artifacts produced, budget vs. actual spend, and (best-effort) kanban
    task count per K9 office.

    `docker stats`/`hermes kanban stats` are both real subprocess calls --
    routed through `monitoring`'s short-TTL caches (K14 decision: cache
    both at a 30s default rather than calling them fresh on every GET,
    since a dashboard left open and polling would otherwise hammer the
    Docker socket and spawn a `hermes` subprocess on every refresh; 30s is
    short enough that "an office just started" is visible within one
    refresh). Both degrade to a `status` field the caller can check instead
    of raising when Docker/hermes aren't available.
    """
    generated_at = dt.datetime.now(dt.UTC)

    try:
        office_usage.sync_office_usage_to_workspaces()
    except OSError:
        # Best-effort mirror (K9); a filesystem hiccup here must not take
        # down the whole dashboard -- `actual_spent_usd` below just reads
        # whatever was already mirrored on a prior successful sync.
        pass

    statuses = monitoring.office_container_status()
    costs = monitoring.office_usage_costs()
    docker_stats = monitoring.docker_stats_cached(docker_stats_ttl)
    kanban_stats = monitoring.kanban_board_stats_cached(ttl_seconds=kanban_stats_ttl)

    office_to_profile = {office: profile for profile, office in office_launcher.PROFILE_TO_OFFICE.items()}
    docker_ok = docker_stats.get("status") == "ok"
    stats_by_container_name = {c["name"]: c for c in docker_stats.get("containers", [])} if docker_ok else {}
    kanban_ok = kanban_stats.get("status") == "ok"
    # `by_assignee` (hermes kanban stats --json) is `{profile: {status:
    # count}}`, not a flat total -- e.g. {"hermes-monitor": {"done": 5}}.
    # Sum each profile's per-status counts into one "tasks in this
    # profile" number for the dashboard card; the full breakdown stays
    # available to anyone reading `check_kanban_board_stats()` directly.
    by_assignee_raw = kanban_stats.get("by_assignee") or {}
    by_assignee_total = {
        profile: sum(counts.values()) for profile, counts in by_assignee_raw.items()
        if isinstance(counts, dict)
    }

    offices = []
    for name in monitoring.OFFICE_NAMES:
        key = f"office-{name}"
        profile = office_to_profile.get(name)
        container_name = next((cn for cn in stats_by_container_name if key in cn), None)
        budget_daily_usd = _office_budget_daily_usd(profile)
        actual_spent_usd = costs.get(name, 0.0)
        offices.append({
            "office": name,
            "kanban_profile": profile,
            "status": statuses.get(key, "unknown"),
            "last_run": monitoring.office_last_run(name),
            "budget_daily_usd": budget_daily_usd,
            "actual_spent_usd": actual_spent_usd,
            "over_budget": bool(budget_daily_usd) and actual_spent_usd > budget_daily_usd,
            "docker_usage": stats_by_container_name.get(container_name) if container_name else None,
            "kanban_tasks_in_profile": (by_assignee_total.get(profile) if (kanban_ok and profile) else None),
        })

    return {
        "generated_at": generated_at.isoformat(),
        "offices": offices,
        "docker_stats_status": docker_stats.get("status"),
        "kanban_board_stats_status": kanban_stats.get("status"),
        "cache_ttl_seconds": {"docker_stats": docker_stats_ttl, "kanban_board_stats": kanban_stats_ttl},
    }
