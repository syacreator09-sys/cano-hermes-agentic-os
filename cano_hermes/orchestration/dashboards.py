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
import json
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from cano_hermes import monitoring
from cano_hermes.bridge import office_launcher, office_usage
from cano_hermes.content import dedup
from cano_hermes.domain.enums import OrderStatus, TaskStatus
from cano_hermes.finance import accounting
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


# --------------------------------------------------------------------------
# K17 -- content control matrix (`GET /api/dashboard/content`).
#
# Real, live-confirmed paths on this machine (checked before writing this
# module, not assumed from the plan's wording):
#   - factory-v5's REAL ledger is `storage/factory.db` (sqlite), not
#     `storage/campaign-packages/` -- confirmed live that path doesn't
#     exist at all on this host (`ls storage/campaign-packages` ->
#     "No existe el archivo o el directorio"; `storage/` only has
#     `factory.db` and an unrelated `cache/`). factory.db carries real
#     rows today: distribution_campaigns=4, publications=1, plan_items=2
#     (checked live, 2026-08-06).
#   - `upload_log_ugc.db` does not exist anywhere on this host (`find ~
#     -iname upload_log_ugc.db` -> nothing) -- exactly the state
#     office-publish/task.sh already documents (created at runtime by
#     command-center's uploader.py, never committed). Reported here as
#     "ledger_absent", the same status task.sh uses, not silently skipped.
#   - ugc-affiliate's `01-products-research/discovered/*.json` (command-
#     center, READ-ONLY per this repo's root CLAUDE.md) has 4 files / 139
#     real discovered products (checked live) -- pre-commitment research
#     candidates, not matrix rows: they carry no channel/campaign state of
#     ours, only a `categoria` and the SOURCE tiktok video's id (not one we
#     published), so they're surfaced as raw "idea"-stage material, never
#     written into the `contenido` table.
#   - this repo's own orders/tasks (K5-K7): checked live against
#     production `storage/hermes.db` -- 115 tasks, ZERO with
#     `route_profile` set to a content-producing office profile
#     (hermes-ugc/hermes-produccion/hermes-distribucion) or at all (every
#     row is `route_profile=None`). No order has been decomposed through
#     K6 into an office-routed subtask yet in production, so this source
#     is real but currently empty -- reported as such, not padded.
# --------------------------------------------------------------------------

FACTORY_V5_DB_PATH = Path.home() / "repos/factory-ia-channel-v5/storage/factory.db"
FACTORY_V5_CAMPAIGN_PACKAGES_DIR = Path.home() / "repos/factory-ia-channel-v5/storage/campaign-packages"
UGC_DISCOVERED_DIR = (
    Path.home() / "repos/cano-ai-command-center/01-offices/ugc-affiliate/01-products-research/discovered"
)
# Same path office-publish/task.sh's LEDGER_DB already uses (K9) -- kept
# in sync deliberately, this is the one real ledger location, not a
# second guess at where it "should" live.
UPLOAD_LOG_UGC_DB_PATH = Path.home() / "repos/cano-ai-command-center/01-offices/ugc-affiliate/upload_log_ugc.db"

_CONTENT_TASK_PROFILES = frozenset({"hermes-ugc", "hermes-produccion", "hermes-distribucion"})


def _factory_v5_snapshot(db_path: Path | None = None, *, limit: int = 20) -> dict[str, Any]:
    """Read-only snapshot of factory-v5's real campaign ledger. Never
    raises -- a missing/locked/corrupt sqlite file degrades to a
    "ausente"/"error" status, same contract as every other dashboard
    source in this module."""
    path = db_path or FACTORY_V5_DB_PATH
    empty = {"campaigns": [], "publications": [], "plan_items": [],
              "totals": {"campaigns": 0, "publications": 0, "plan_items": 0}}
    if not path.is_file():
        return {"status": "ausente", "detail": f"{path} no existe en este host", **empty}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        campaigns = [dict(r) for r in conn.execute(
            "SELECT id, name, scope, status, publish_mode, start_date, end_date "
            "FROM distribution_campaigns ORDER BY created_at DESC LIMIT ?", (limit,),
        )]
        publications = [dict(r) for r in conn.execute(
            "SELECT id, channel_id, platform, status, scheduled_at, published_at, external_id "
            "FROM publications ORDER BY created_at DESC LIMIT ?", (limit,),
        )]
        plan_items = [dict(r) for r in conn.execute(
            "SELECT id, plan_id, channel_id, title, format, status, planned_at, budget_usd "
            "FROM plan_items ORDER BY created_at DESC LIMIT ?", (limit,),
        )]
        conn.close()
    except sqlite3.Error as exc:
        return {"status": "error", "detail": f"{exc.__class__.__name__}: {exc}", **empty}

    return {
        "status": "ok", "detail": None,
        "campaigns": campaigns, "publications": publications, "plan_items": plan_items,
        "totals": {
            "campaigns": len(campaigns), "publications": len(publications), "plan_items": len(plan_items),
        },
    }


def _campaign_packages_snapshot(directory: Path | None = None) -> dict[str, Any]:
    """`storage/campaign-packages/` is the path the K17 mandate names --
    confirmed live it does not exist at all on this machine today (only
    `storage/factory.db` and an unrelated `cache/` dir are there).
    Reported honestly rather than silently substituted by
    `_factory_v5_snapshot` above (both are surfaced to the caller
    separately)."""
    dir_path = directory or FACTORY_V5_CAMPAIGN_PACKAGES_DIR
    if not dir_path.is_dir():
        return {"status": "ausente", "detail": f"{dir_path} no existe", "package_count": 0}
    packages = [p.name for p in dir_path.iterdir() if p.is_file() or (p.is_dir() and p.name != "cache")]
    return {
        "status": "ok" if packages else "vacio",
        "detail": None if packages else f"{dir_path} existe pero no tiene paquetes todavia (solo cache/)",
        "package_count": len(packages),
    }


def _ugc_discovered_snapshot(directory: Path | None = None, *, per_file_sample: int = 3) -> dict[str, Any]:
    """Read-only snapshot of ugc-affiliate's discovered-product research
    files (command-center, F9's own source). Each file is a JSON list of
    candidate products -- pre-commitment research, not matrix rows."""
    dir_path = directory or UGC_DISCOVERED_DIR
    if not dir_path.is_dir():
        return {"status": "ausente", "detail": f"{dir_path} no existe", "files": [],
                "totals": {"files": 0, "products": 0}}

    files_summary: list[dict[str, Any]] = []
    total_products = 0
    for path in sorted(dir_path.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            files_summary.append({"file": path.name, "status": "error", "detail": str(exc), "product_count": 0})
            continue
        if not isinstance(data, list):
            files_summary.append({
                "file": path.name, "status": "error",
                "detail": "se esperaba una lista JSON", "product_count": 0,
            })
            continue
        total_products += len(data)
        sample = [
            {
                "nombre": (item.get("nombre") or "")[:80] if isinstance(item, dict) else None,
                "categoria": item.get("categoria") if isinstance(item, dict) else None,
                "plataforma": item.get("plataforma") if isinstance(item, dict) else None,
                "video_id_fuente": item.get("video_id") if isinstance(item, dict) else None,
            }
            for item in data[:per_file_sample]
        ]
        files_summary.append({
            "file": path.name, "status": "ok", "product_count": len(data), "sample": sample,
        })

    return {
        "status": "ok", "detail": None, "files": files_summary,
        "totals": {"files": len(files_summary), "products": total_products},
    }


def _upload_log_ugc_snapshot(db_path: Path | None = None) -> dict[str, Any]:
    """Same read-only query office-publish/task.sh already runs (only rows
    with status=success and a real, non-placeholder req_id count as
    "published") -- mirrored here so the dashboard and the dedup gate
    agree on what "already published" means."""
    path = db_path or UPLOAD_LOG_UGC_DB_PATH
    if not path.parent.is_dir():
        return {"status": "ledger_dir_not_mounted", "detail": f"{path.parent} no existe en este host", "rows": []}
    if not path.is_file():
        return {
            "status": "ledger_absent",
            "detail": (
                f"{path} no existe -- se crea en runtime por uploader.py (command-center); "
                "aun no hay ninguna escritura real en este host (F9/reel-dedup-check)."
            ),
            "rows": [],
        }
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = [
            dict(zip(("canal", "slug", "fecha", "status", "req_id"), r, strict=True))
            for r in conn.execute(
                "SELECT canal, slug, fecha, status, req_id FROM uploads ORDER BY fecha DESC LIMIT 20"
            )
        ]
        conn.close()
    except sqlite3.Error as exc:
        return {"status": "error", "detail": f"{exc.__class__.__name__}: {exc}", "rows": []}
    return {"status": "ok", "detail": None, "rows": rows}


def content_dashboard(
    store: SQLiteStore, *,
    factory_db_path: Path | None = None,
    campaign_packages_dir: Path | None = None,
    ugc_discovered_dir: Path | None = None,
    upload_log_path: Path | None = None,
) -> dict[str, Any]:
    """`GET /api/dashboard/content`'s data (K17) -- the content control
    matrix: single point of truth for "what content exists and in what
    state, on any channel or campaign", aggregating the Baserow
    `contenido` table (cano_hermes.content.dedup) with every other real
    source the K17 mandate named. Every source below degrades to an
    explicit status/detail on missing-file/unreachable/bad-data instead of
    raising -- same contract `finance_dashboard`/`offices_dashboard`
    already use.

    All keyword paths are overridable purely for tests (fixtures instead
    of the real host paths); production callers (the HTTP route) pass
    none and get the real, live-confirmed locations documented on the
    module-level constants above.
    """
    generated_at = dt.datetime.now(dt.UTC)

    baserow = dedup.fetch_rows()
    baserow_rows = [
        {
            "id": row.get("id"),
            "canal": row.get("canal"),
            "oficina_productora": row.get("oficina_productora"),
            "estado": dedup.estado_value(row),
            "video_id": row.get("video_id"),
            "costo_usd": row.get("costo_usd"),
            "link_artifact": row.get("link_artifact"),
            "fecha": row.get("fecha"),
            "dedup_key": row.get("dedup_key"),
        }
        for row in baserow.get("rows", [])
    ] if baserow["status"] == "ok" else []

    factory = _factory_v5_snapshot(factory_db_path)
    campaign_packages = _campaign_packages_snapshot(campaign_packages_dir)
    ugc_discovered = _ugc_discovered_snapshot(ugc_discovered_dir)
    upload_log = _upload_log_ugc_snapshot(upload_log_path)

    all_tasks = store.list_tasks()
    content_tasks = [
        {
            "id": t.id, "title": t.title[:120], "status": t.status.value,
            "route_profile": t.route_profile, "parent_task_id": t.parent_task_id,
        }
        for t in all_tasks if t.route_profile in _CONTENT_TASK_PROFILES
    ]

    factory_has_data = factory["status"] == "ok" and sum(factory["totals"].values()) > 0
    sources_summary = {
        "baserow_contenido": {
            "has_data": bool(baserow_rows), "count": len(baserow_rows), "status": baserow["status"],
        },
        "factory_v5_ledger_db": {
            "has_data": factory_has_data, "status": factory["status"], "totals": factory["totals"],
            "detail": "storage/factory.db, NO storage/campaign-packages/ (vacio, ver campaign_packages_dir)",
        },
        "factory_v5_campaign_packages_dir": {
            "has_data": campaign_packages["status"] == "ok", "status": campaign_packages["status"],
            "detail": campaign_packages["detail"],
        },
        "ugc_discovered_json": {
            "has_data": ugc_discovered["totals"]["products"] > 0, "status": ugc_discovered["status"],
            "totals": ugc_discovered["totals"],
        },
        "upload_log_ugc_db": {
            "has_data": upload_log["status"] == "ok" and bool(upload_log["rows"]),
            "status": upload_log["status"], "detail": upload_log["detail"],
        },
        "orders_tasks_k5_k7": {
            "has_data": bool(content_tasks), "count": len(content_tasks),
            "detail": "tasks con route_profile en {hermes-ugc, hermes-produccion, hermes-distribucion}",
        },
    }

    return {
        "generated_at": generated_at.isoformat(),
        "baserow_contenido": {
            "status": baserow["status"], "detail": baserow.get("detail"), "rows": baserow_rows,
        },
        "factory_v5": factory,
        "factory_v5_campaign_packages": campaign_packages,
        "ugc_discovered": ugc_discovered,
        "upload_log_ugc": upload_log,
        "content_tasks": content_tasks,
        "sources_summary": sources_summary,
    }


# --------------------------------------------------------------------------
# K18 -- unified accounting (`GET /api/dashboard/accounting`). Extends K14's
# `finance_dashboard` (agent/engine spend ledger, `BudgetService`) rather
# than duplicating it -- this view imports and reuses that function
# directly, then adds the second ledger K14 never covered: real business
# accounting (CASS / Cano Digital / LUZYA / otro) from the `contabilidad`
# Baserow table (`cano_hermes.finance.accounting`, K18).
# --------------------------------------------------------------------------
def accounting_dashboard(
    store: SQLiteStore, budget: BudgetService, *, business_rows: list[dict] | None = None,
) -> dict[str, Any]:
    """Both ledgers, side by side, cut by negocio and by month:
      - `agent_ledger`: exactly `finance_dashboard`'s own return shape
        (daily BudgetService ledger, cost by executor/order/task/office) --
        not recomputed, just imported and reused, per the K18 mandate
        ("reusa lo que K14 ya calcula, impórtalo").
      - `business_ledger`: `contabilidad` rows aggregated by
        `finance.accounting.cash_position` (running balance per negocio)
        + a per-negocio/per-month ingreso/gasto breakdown this function
        computes directly (the one aggregation `cash_position`/
        `finance_close` don't already provide standalone).

    `business_rows` is test-only (a fixture list skips the live Baserow
    fetch entirely, same convention as `content_dashboard`'s path
    overrides); production callers (the HTTP route) pass none and get
    `accounting.fetch_rows()`."""
    generated_at = dt.datetime.now(dt.UTC)

    agent_ledger = finance_dashboard(store, budget)

    if business_rows is not None:
        baserow_status, baserow_detail, rows = "ok", None, business_rows
    else:
        fetched = accounting.fetch_rows()
        baserow_status = fetched["status"]
        baserow_detail = fetched.get("detail")
        rows = fetched["rows"] if baserow_status == "ok" else []

    position = accounting.cash_position(rows)

    by_negocio_month: dict[str, dict[str, dict[str, float]]] = {}
    for row in rows:
        negocio = accounting.select_value(row, "negocio") or "otro"
        tipo = accounting.select_value(row, "tipo")
        monto = accounting.numeric_value(row.get("monto"))
        if monto is None or tipo not in ("ingreso", "gasto"):
            continue
        month = (row.get("fecha") or "")[:7] or "(sin fecha)"
        bucket = by_negocio_month.setdefault(negocio, {}).setdefault(month, {"ingresos_usd": 0.0, "gastos_usd": 0.0})
        bucket["ingresos_usd" if tipo == "ingreso" else "gastos_usd"] += monto

    movements_by_negocio_month = [
        {
            "negocio": negocio, "month": month,
            "ingresos_usd": round(values["ingresos_usd"], 4),
            "gastos_usd": round(values["gastos_usd"], 4),
            "flujo_neto_usd": round(values["ingresos_usd"] - values["gastos_usd"], 4),
        }
        for negocio, months in by_negocio_month.items()
        for month, values in sorted(months.items())
    ]

    return {
        "generated_at": generated_at.isoformat(),
        "agent_ledger": agent_ledger,
        "business_ledger": {
            "baserow_status": baserow_status,
            "baserow_detail": baserow_detail,
            "movements_total": len(rows),
            "cash_position": position,
            "by_negocio_and_month": movements_by_negocio_month,
        },
    }


# --------------------------------------------------------------------------
# C3 (plan StarHome, tras el cierre de HERMES-KICKOFF) -- connections
# dashboard (`GET /api/dashboard/connections`). Combines the C0 key
# registry (`config/key_registry.yaml`, 273 vault keys mirrored by NAME
# only -- its own `_meta.nota` says "Ningún valor de llave vive en este
# archivo", and nothing here ever reads or surfaces a value either) with
# the most recent connection-matrix audit written by
# `scripts/connection_matrix.py`. Reads `monitoring.
# latest_connection_matrix_summary()` -- the on-disk JSON mirror -- rather
# than calling any provider live: same "a GET must stay instant, the
# batch job already paid the network cost" contract `monitoring.py`'s own
# module docstring establishes for `offices_dashboard`. A registry that
# fails to parse or a matrix that has never run both degrade to an
# explicit empty/"sin_datos" section instead of raising, matching every
# other function in this module.
# --------------------------------------------------------------------------
KEY_REGISTRY_PATH = ROOT / "config" / "key_registry.yaml"


def _load_key_registry(path: Path | None = None) -> dict[str, Any]:
    """Read-only parse of `config/key_registry.yaml`. Missing file, bad
    YAML, or a `llaves` key that isn't a list all degrade to an empty
    list with an explanatory `status`/`detail` -- never a raised
    exception, since a stale/corrupt registry mirror must not take down
    the whole dashboard."""
    registry_path = path or KEY_REGISTRY_PATH
    if not registry_path.is_file():
        return {"status": "ausente", "detail": f"{registry_path} no existe", "llaves": []}
    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        return {"status": "error", "detail": f"{exc.__class__.__name__}: {exc}", "llaves": []}
    llaves = data.get("llaves")
    if not isinstance(llaves, list):
        return {"status": "error", "detail": "'llaves' no es una lista en el registry", "llaves": []}
    return {"status": "ok", "detail": None, "llaves": llaves}


def connections_dashboard(*, registry_path: Path | None = None) -> dict[str, Any]:
    """`GET /api/dashboard/connections`'s data: the registry-of-keys
    summary (count by `dominio`, keys with no detected `consumidores`,
    keys flagged `rotacion_pendiente`) crossed with the latest
    `connection_matrix.py` audit (per-provider ✓/✗/—/policy-skip status,
    latency, quota, plus the run's own totals and date).

    `registry_path` is test-only (a tmp_path fixture instead of the real
    vault mirror, same convention `content_dashboard`'s path overrides
    use); production callers (the HTTP route) pass none and get the real
    `config/key_registry.yaml`. There is no equivalent override for the
    matrix -- it's always read via `monitoring.
    latest_connection_matrix_summary()`, so tests patch that function
    directly rather than the filesystem underneath it.
    """
    generated_at = dt.datetime.now(dt.UTC)

    registry = _load_key_registry(registry_path)
    llaves = registry["llaves"]

    by_domain: dict[str, int] = {}
    for llave in llaves:
        domain = llave.get("dominio") or "sin-dominio"
        by_domain[domain] = by_domain.get(domain, 0) + 1

    unclaimed_keys = sorted(
        (
            {"nombre": llave.get("nombre"), "proveedor": llave.get("proveedor"), "dominio": llave.get("dominio")}
            for llave in llaves
            if not llave.get("consumidores")
        ),
        key=lambda row: row["nombre"] or "",
    )

    rotation_pending = sorted(
        (
            {
                "nombre": llave.get("nombre"),
                "proveedor": llave.get("proveedor"),
                "dominio": llave.get("dominio"),
                "riesgo": llave.get("riesgo"),
                "rotacion_motivo": llave.get("rotacion_motivo"),
            }
            for llave in llaves
            if llave.get("rotacion_pendiente")
        ),
        key=lambda row: row["nombre"] or "",
    )

    matrix = monitoring.latest_connection_matrix_summary()
    if matrix is not None:
        validators = [
            {
                "provider": provider,
                "status": info.get("status"),
                "detail": info.get("detail"),
                "latency_ms": info.get("latency_ms"),
                "quota": info.get("quota"),
            }
            for provider, info in sorted((matrix.get("validators") or {}).items())
        ]
        matrix_summary = {
            "status": "ok",
            "date": matrix.get("date"),
            "report_path": matrix.get("report_path"),
            "validators": validators,
            "validators_totals": matrix.get("validators_totals") or {},
            "totals": matrix.get("totals") or {},
            "apify": matrix.get("apify"),
            "rapidapi": matrix.get("rapidapi"),
        }
    else:
        # No audit has ever run in this environment -- "sin datos", not a
        # failure (mirrors `latest_connection_matrix_summary`'s own
        # docstring contract).
        matrix_summary = {
            "status": "sin_datos",
            "date": None,
            "report_path": None,
            "validators": [],
            "validators_totals": {},
            "totals": {},
            "apify": None,
            "rapidapi": None,
        }

    return {
        "generated_at": generated_at.isoformat(),
        "registry": {
            "status": registry["status"],
            "detail": registry["detail"],
            "total_keys": len(llaves),
            "by_domain": dict(sorted(by_domain.items())),
        },
        "unclaimed_keys": unclaimed_keys,
        "unclaimed_keys_count": len(unclaimed_keys),
        "rotation_pending": rotation_pending,
        "rotation_pending_count": len(rotation_pending),
        "matrix": matrix_summary,
    }
