#!/usr/bin/env python3
"""Plan Prometeo F13 — ciclo diario autónomo de StarHome OS.

Corre en secuencia, todo read-only/gratis (cero llamadas de pago, cero
publicación):

  1. `scripts/connection_matrix.py` (F2) — salud de conexiones/credenciales.
  2. Salud: StarHome API (`/api/health`), `hermes status`, `nexus doctor`,
     `docker stats --no-stream` sobre lo que esté arriba de F11.
  3. Performance UGC (F9) — clasificación ESCALAR/MANTENER/MATAR si hubiera
     datos reales; F9 fue un dry-run con fixtures, así que esto documenta
     "sin datos suficientes" en vez de inventar cifras.
  4. Costos — cualquier `usage-*.json` bajo `storage/workspaces` (F3's
     BudgetService las produce), + el estado del `BudgetLedger` del día,
     + créditos Higgsfield si existiera un tracker en algún repo de
     contrato (no existe hoy — documentado, no inventado).
  5. Auditoría — `scripts/validate.py` como proxy PASS/FLAG.
  6. Memoria (K11/K15) — candidatos pendientes en `memory_candidates`
     (`MemoryCandidateService.list(status="candidate")`): solo visibiliza,
     NUNCA auto-aprueba ni promueve al vault (regla 9 del `CLAUDE.md` raíz:
     "Store durable lessons as candidates; never mutate approved memory
     directly" -- la promoción sigue siendo 100% humana, vía `POST
     /api/memory/candidates/{id}/resolve`).
  7. Escribe cada métrica a la tabla `metricas_diarias` de Baserow (F11,
     vía su API REST con `BASEROW_TOKEN` del vault) y un reporte markdown
     en `reports/daily/<fecha>.md`, con un `⚠️ ATENCIÓN:` arriba del
     documento si algo de salud falló o el presupuesto del día superó 80%.

Se invoca por cron real vía `hermes cron create --script ... --no-agent`
(mismo patrón que los jobs `heartbeat-salud`/`backup-diario-vault` ya
registrados en este mismo hermes-agent) — ver
`~/.hermes/scripts/daily-cycle-starhome.sh` y el reporte F13 para el
comando exacto usado.
"""
from __future__ import annotations

import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cano_hermes import monitoring  # noqa: E402
from cano_hermes.config import settings  # noqa: E402
from cano_hermes.governance.budget import BudgetService  # noqa: E402
from cano_hermes.governance.memory_candidates import MemoryCandidateService  # noqa: E402
from cano_hermes.orchestration import dashboards  # noqa: E402
from cano_hermes.storage.sqlite import SQLiteStore  # noqa: E402

BUDGET_ALERT_THRESHOLD = 0.8

# C5 -- where `scripts/connection_matrix.py`'s `compute_and_render()` writes
# its daily JSON mirror (`reports/connection-matrix-<fecha>.json`, see that
# module's `REPO_ROOT / "reports"`). Read-only from here.
REPORTS_DIR = ROOT / "reports"
CONNECTION_MATRIX_DATE_RE = re.compile(r"^connection-matrix-(\d{4}-\d{2}-\d{2})\.json$")


def _load_previous_connection_matrix(
    today: str, reports_dir: Path | None = None
) -> dict[str, Any] | None:
    """C5 -- best-effort load of the most recent `connection-matrix-<fecha>.json`
    strictly before `today`, for the regression alert below. Prefers yesterday's
    exact date (`today - 1 day`); if that specific file doesn't exist, falls back
    to the next most recent one available in `reports/` (excluding today's own
    file, which may already have been written by a previous invocation this same
    day). Returns `None` -- never raises -- when there is no prior report at all
    (first day of the system) or the directory/file can't be read/parsed: a
    missing history must not break the cycle."""
    reports_dir = reports_dir or REPORTS_DIR
    try:
        today_date = datetime.date.fromisoformat(today)
    except ValueError:
        today_date = datetime.date.today()
    yesterday = (today_date - datetime.timedelta(days=1)).isoformat()

    candidate_path: Path | None = None
    yesterday_path = reports_dir / f"connection-matrix-{yesterday}.json"
    if yesterday_path.is_file():
        candidate_path = yesterday_path
    elif reports_dir.is_dir():
        dated: list[tuple[str, Path]] = []
        for path in reports_dir.glob("connection-matrix-*.json"):
            m = CONNECTION_MATRIX_DATE_RE.match(path.name)
            if not m:
                continue
            date_str = m.group(1)
            if date_str >= today:
                continue
            dated.append((date_str, path))
        if dated:
            dated.sort(key=lambda pair: pair[0])
            candidate_path = dated[-1][1]

    if candidate_path is None:
        return None
    try:
        return json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _detect_connection_regressions(
    today_connections: Any, previous_matrix: dict[str, Any] | None
) -> list[str]:
    """C5 -- pure comparison, split out from `run_cycle()` so it's directly
    unit-testable without running the full cycle: providers whose `validators[
    provider]["status"]` was `"✓"` in `previous_matrix` and is `"✗"` in
    `today_connections["validators"]`, sorted. Degrades to `[]` (never
    raises, never a false alert) when there's no prior report, or either
    side is missing/malformed (e.g. today's connections step itself errored,
    or an old-format JSON with no `validators` key at all)."""
    if previous_matrix is None or not isinstance(today_connections, dict):
        return []
    today_validators = today_connections.get("validators") or {}
    previous_validators = previous_matrix.get("validators") or {}
    regressed = [
        provider
        for provider, previous_info in previous_validators.items()
        if isinstance(previous_info, dict)
        and previous_info.get("status") == "✓"
        and isinstance(today_validators.get(provider), dict)
        and today_validators[provider].get("status") == "✗"
    ]
    return sorted(regressed)


def _key_registry_summary() -> dict[str, Any]:
    """C5 -- read-only counts from `config/key_registry.yaml` (C0) for the
    daily report and Baserow metrics: keys with no detected consumer
    (`consumidores` empty) and keys flagged `rotacion_pendiente`. Reuses
    `dashboards._load_key_registry()` -- same registry the C3
    `/dashboard/connections` view reads, same "never raise" contract (a
    missing/corrupt registry degrades to zero counts with a `status`/
    `detail` explaining why, not an exception that kills the cycle)."""
    try:
        registry = dashboards._load_key_registry()
    except Exception as exc:  # noqa: BLE001 -- one failing step must not kill the cycle
        return {
            "status": "error", "detail": str(exc),
            "unclaimed_count": 0, "rotation_pending_count": 0,
        }
    llaves = registry.get("llaves") or []
    unclaimed_count = sum(1 for llave in llaves if not llave.get("consumidores"))
    rotation_pending_count = sum(1 for llave in llaves if llave.get("rotacion_pendiente"))
    return {
        "status": registry.get("status", "ok"),
        "detail": registry.get("detail"),
        "unclaimed_count": unclaimed_count,
        "rotation_pending_count": rotation_pending_count,
    }


def memory_candidates_snapshot(store: SQLiteStore) -> dict[str, Any]:
    """K15 -- read-only visibility for `scripts/daily_cycle.py` into K11's
    `memory_candidates` table via `MemoryCandidateService.list(status=
    "candidate")` ("candidate" is the real status string `add_memory_
    candidate` writes at insert time -- see `SQLiteStore.list_memory_
    candidates`). NEVER resolves/promotes anything: the only path in the
    codebase that writes to the vault from a candidate stays `MemoryCandi
    dateService.resolve(..., decision="approved", ...)`, reachable only via
    the human-gated `POST /api/memory/candidates/{id}/resolve` (root
    CLAUDE.md rule 9: "Store durable lessons as candidates; never mutate
    approved memory directly"). Never raises -- a broken vault path or a
    corrupt row must not kill the rest of the cycle, same contract as every
    other step in `run_cycle`."""
    try:
        service = MemoryCandidateService(store, settings.vault_path)
        pending = service.list(status="candidate")
    except Exception as exc:  # noqa: BLE001 -- one failing step must not kill the cycle
        return {"status": "error", "detail": str(exc)}
    return {
        "status": "ok",
        "pending_count": len(pending),
        "pending": [
            {"id": c["id"], "namespace": c["namespace"], "created_at": c["created_at"]}
            for c in pending
        ],
    }


def run_cycle() -> dict[str, Any]:
    today = datetime.date.today().isoformat()
    result: dict[str, Any] = {"date": today}

    # 1. Connection matrix (F2) -- actually runs it (not the cached
    # summary the dashboard reads) so today's report is fresh.
    try:
        result["connections"] = monitoring.run_connection_matrix()
    except Exception as exc:  # noqa: BLE001 -- one failing step must not kill the cycle
        result["connections"] = {"status": "error", "detail": str(exc)}

    # 1b. Key registry (C0) counts -- unclaimed / rotation-pending, surfaced
    # in the report and Baserow (C5).
    result["key_registry"] = _key_registry_summary()

    # 2. Health.
    result["health"] = {
        "starhome_api": monitoring.check_starhome_health(),
        "hermes_status": monitoring.check_hermes_status(),
        "nexus_doctor": monitoring.check_nexus_doctor(),
        "docker_stats": monitoring.check_docker_stats(),
        "offices": monitoring.office_container_status(),
    }

    # 3. UGC performance (F9) -- honest "sin datos suficientes".
    result["ugc_performance"] = monitoring.ugc_performance_summary()

    # 4. Costs -- usage-*.json + BudgetLedger of the day + Higgsfield.
    store = SQLiteStore(settings.database_url)
    budget_service = BudgetService(store)
    ledger = budget_service.ledger_for(today)
    ingested_today = budget_service.ingest_workspace(day=today)
    percent_used = (
        (ledger.spent_usd / ledger.daily_limit_usd) if ledger.daily_limit_usd > 0 else 0.0
    )
    result["costs"] = {
        "usage_files": monitoring.usage_files_summary(),
        "budget": {
            "day": today,
            "daily_limit_usd": ledger.daily_limit_usd,
            "spent_usd": ledger.spent_usd,
            "remaining_usd": ledger.remaining_usd,
            "percent_used": round(percent_used, 4),
            "ingested_from_workspaces_this_run_usd": ingested_today,
        },
        "higgsfield_credits": monitoring.higgsfield_credits_summary(),
    }

    # 5. Audit proxy.
    result["audit"] = monitoring.run_validate()

    # 6. Memory candidates pending human review (K11 built the reader/
    # promoter, `memory_candidates` table + `MemoryCandidateService`; K15
    # wires it into the daily cycle so pending candidates surface here too,
    # not only via `GET /api/memory/candidates?status=candidate`).
    result["memory_candidates"] = memory_candidates_snapshot(store)

    # Alerts (presentation-only, per the F13 mandate -- no push).
    alerts: list[str] = []
    if result["health"]["starhome_api"]["status"] != "ok":
        alerts.append("StarHome API (/api/health) no respondió correctamente.")
    if result["health"]["hermes_status"]["status"] == "error":
        alerts.append("`hermes status` devolvió error.")
    if result["health"]["nexus_doctor"]["status"] == "error":
        alerts.append("`nexus doctor` devolvió error.")
    if result["audit"]["status"] != "PASS":
        alerts.append("`scripts/validate.py` marcó FLAG (ver sección Auditoría).")
    if result["memory_candidates"]["status"] == "ok" and result["memory_candidates"]["pending_count"] > 0:
        alerts.append(
            f"{result['memory_candidates']['pending_count']} candidato(s) de memoria "
            "esperando revisión humana (ver sección Memoria)."
        )
    if percent_used > BUDGET_ALERT_THRESHOLD:
        alerts.append(
            f"Presupuesto del día al {percent_used * 100:.0f}% "
            f"(${ledger.spent_usd:.2f} de ${ledger.daily_limit_usd:.2f})."
        )

    # C5 -- regression alert: compare today's live validators against the
    # most recent prior connection-matrix JSON. This is the central piece
    # of C5 ("eso es lo que de verdad hay que ver a tiempo"): a provider
    # that was ✓ yesterday and is ✗ today is worth a human's attention even
    # when nothing else in the cycle flagged a problem. No prior report
    # (first day, or the connections step itself errored today) means no
    # comparison is possible -- that degrades to "nothing to compare",
    # never a false alert.
    previous_matrix = _load_previous_connection_matrix(today)
    regressed_providers = _detect_connection_regressions(result.get("connections"), previous_matrix)
    result["connections_regression"] = {
        "previous_report_found": previous_matrix is not None,
        "regressed_providers": regressed_providers,
    }
    if regressed_providers:
        alerts.append(
            "⚠️ ATENCIÓN: proveedor(es) que estaban ✓ ayer y hoy están ✗: "
            + ", ".join(regressed_providers) + "."
        )

    result["alerts"] = alerts

    return result


def _fmt_status(value: Any) -> str:
    return str(value)


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    if result["alerts"]:
        lines.append("⚠️ ATENCIÓN:")
        for alert in result["alerts"]:
            lines.append(f"- {alert}")
        lines.append("")

    lines.append(f"# Ciclo diario StarHome OS — {result['date']}")
    lines.append("")
    lines.append("Generado por `scripts/daily_cycle.py` (plan Prometeo, fase F13). "
                  "Todo read-only/gratis.")
    lines.append("")

    conn = result["connections"]
    lines.append("## 1. Conexiones (F2)")
    lines.append("")
    if conn.get("status") == "error":
        lines.append(f"- **error**: {conn.get('detail')}")
    else:
        totals = conn.get("totals", {})
        lines.append(f"- Reporte: `{conn.get('report_path')}`")
        lines.append(
            f"- Totales: ✓{totals.get('✓', '?')} ✗{totals.get('✗', '?')} —{totals.get('—', '?')}"
        )
        lines.append(f"- Apify: {conn.get('apify', {}).get('status')} — {conn.get('apify', {}).get('detail')}")
        lines.append(f"- RapidAPI: {conn.get('rapidapi', {}).get('status')} — {conn.get('rapidapi', {}).get('detail')}")

        # C5 -- validadores en vivo (~30 proveedores, scripts/validators/registry.py
        # vía connection_matrix.py). `detail` de estos validadores nunca contiene
        # valores de llave (solo nombres de variable de entorno / texto
        # descriptivo -- ver scripts/validators/registry.py), así que es seguro
        # imprimirlo aquí tal cual.
        validators_totals = conn.get("validators_totals") or {}
        lines.append(
            f"- Validadores en vivo: ✓{validators_totals.get('✓', '?')} "
            f"✗{validators_totals.get('✗', '?')} —{validators_totals.get('—', '?')} "
            f"policy-skip{validators_totals.get('policy-skip', '?')}"
        )
        validators = conn.get("validators") or {}
        failed_validators = sorted(
            (name, info) for name, info in validators.items()
            if isinstance(info, dict) and info.get("status") == "✗"
        )
        if failed_validators:
            lines.append("- Proveedores en ✗ (validador en vivo):")
            for name, info in failed_validators:
                lines.append(f"  - `{name}`: {info.get('detail')}")
        else:
            lines.append("- Proveedores en ✗ (validador en vivo): ninguno.")

    key_registry = result.get("key_registry", {})
    lines.append(
        f"- Llaves sin consumidor (`config/key_registry.yaml`): "
        f"**{key_registry.get('unclaimed_count', 0)}**"
    )
    lines.append(
        f"- Llaves con rotación pendiente (`config/key_registry.yaml`): "
        f"**{key_registry.get('rotation_pending_count', 0)}**"
    )
    lines.append("")

    health = result["health"]
    lines.append("## 2. Salud")
    lines.append("")
    lines.append(f"- StarHome API: {_fmt_status(health['starhome_api']['status'])}")
    lines.append(f"- `hermes status`: {_fmt_status(health['hermes_status']['status'])}")
    lines.append(f"- `nexus doctor`: {_fmt_status(health['nexus_doctor']['status'])}")
    docker_stats = health["docker_stats"]
    if docker_stats.get("status") == "ok":
        containers = docker_stats.get("containers", [])
        if containers:
            lines.append(f"- `docker stats`: {len(containers)} contenedor(es) arriba:")
            for c in containers:
                lines.append(f"  - {c['name']}: cpu={c['cpu']} mem={c['mem_usage']} ({c['mem_percent']})")
        else:
            lines.append("- `docker stats`: ningún contenedor arriba en este momento (esperado — F11 son on-demand).")
    else:
        lines.append(f"- `docker stats`: {docker_stats.get('status')} — {docker_stats.get('detail', '')}")
    lines.append("- Oficinas F11 (`docker ps`):")
    for name, state in health["offices"].items():
        lines.append(f"  - {name}: {state}")
    lines.append("")

    ugc = result["ugc_performance"]
    lines.append("## 3. Performance UGC (F9)")
    lines.append("")
    lines.append(f"- Clasificación: **{ugc['classification']}**")
    lines.append(f"- {ugc['note']}")
    lines.append("")

    costs = result["costs"]
    lines.append("## 4. Costos")
    lines.append("")
    uf = costs["usage_files"]
    lines.append(f"- Archivos `usage-*.json` encontrados: {uf['usage_files_found']} "
                 f"(total ${uf['total_cost_usd']:.4f})")
    b = costs["budget"]
    lines.append(
        f"- Presupuesto del día: ${b['spent_usd']:.2f} / ${b['daily_limit_usd']:.2f} "
        f"({b['percent_used'] * 100:.1f}%) — restante ${b['remaining_usd']:.2f}"
    )
    hf = costs["higgsfield_credits"]
    lines.append(f"- Créditos Higgsfield: {hf['status']} — {hf['note']}")
    lines.append("")

    audit = result["audit"]
    lines.append("## 5. Auditoría (`scripts/validate.py`)")
    lines.append("")
    lines.append(f"- Estado: **{audit['status']}**")
    if audit["status"] == "PASS":
        for key in ("agents", "skills", "notes"):
            if key in audit:
                lines.append(f"  - {key}: {audit[key]}")
    else:
        if audit.get("stderr"):
            lines.append(f"  - stderr: `{audit['stderr'][-500:]}`")
    lines.append("")

    mem = result["memory_candidates"]
    lines.append("## 6. Memoria — candidatos pendientes (K11/K15)")
    lines.append("")
    if mem["status"] != "ok":
        lines.append(f"- **error**: {mem.get('detail')}")
    else:
        lines.append(f"- Pendientes de revisión humana: **{mem['pending_count']}**")
        if mem["pending_count"]:
            lines.append("- Resolver vía `POST /api/memory/candidates/{id}/resolve` "
                         '(`{"decision": "approved"|"rejected", "actor": "..."}`):')
            for c in mem["pending"]:
                lines.append(f"  - `{c['id']}` ({c['namespace']}, creado {c['created_at']})")
        else:
            lines.append("- Nada pendiente.")
    lines.append("")

    return "\n".join(lines) + "\n"


def write_baserow_metrics(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort: one metricas_diarias row per key metric. Never raises --
    a Baserow outage must not fail the whole cycle (see
    monitoring.write_metric_row's own contract)."""
    today = result["date"]
    conn_totals = result.get("connections", {}).get("totals", {})
    conn_total_checks = sum(conn_totals.values()) if conn_totals else 0
    conn_ok_pct = (
        (conn_totals.get("✓", 0) / conn_total_checks * 100.0) if conn_total_checks else 0.0
    )
    budget = result["costs"]["budget"]

    # C5 -- validadores en vivo (~30 proveedores) y registry de llaves (C0).
    validators_totals = result.get("connections", {}).get("validators_totals") or {}
    validators_total_checks = sum(
        validators_totals.get(k, 0) for k in ("✓", "✗", "—", "policy-skip")
    )
    validators_ok_pct = (
        (validators_totals.get("✓", 0) / validators_total_checks * 100.0)
        if validators_total_checks else 0.0
    )
    key_registry = result.get("key_registry", {})

    rows_to_write = [
        ("sistema", "connection_matrix_ok_pct", round(conn_ok_pct, 2), "F2, % de variables ✓ sobre el total revisado"),
        ("sistema", "starhome_api_health", 1.0 if result["health"]["starhome_api"]["status"] == "ok" else 0.0, ""),
        ("sistema", "audit_status_pass", 1.0 if result["audit"]["status"] == "PASS" else 0.0, ""),
        ("sistema", "budget_percent_used", round(budget["percent_used"] * 100, 2), f"día {today}"),
        ("sistema", "budget_remaining_usd", round(budget["remaining_usd"], 4), ""),
        ("costos", "usage_files_total_cost_usd", result["costs"]["usage_files"]["total_cost_usd"], ""),
        ("ugc", "performance_classification", 0.0, result["ugc_performance"]["note"]),
        ("sistema", "validators_ok_pct", round(validators_ok_pct, 2),
         "C5/C1, % de proveedores ✓ sobre los validadores en vivo corridos"),
        ("sistema", "validators_policy_skip_count", float(validators_totals.get("policy-skip", 0)),
         "C5/C1, proveedores en policy-skip (sin red por política, no es fallo)"),
        ("sistema", "unclaimed_keys_count", float(key_registry.get("unclaimed_count", 0)),
         "C5/C0, llaves del vault sin consumidor detectado en código"),
        ("sistema", "rotation_pending_count", float(key_registry.get("rotation_pending_count", 0)),
         "C5/C0, llaves marcadas rotacion_pendiente en config/key_registry.yaml"),
    ]

    written = []
    for oficina, metrica, valor, nota in rows_to_write:
        outcome = monitoring.write_metric_row(today, oficina, metrica, valor, nota)
        written.append({"oficina": oficina, "metrica": metrica, "valor": valor, "result": outcome})
    return written


def write_finance_and_orders_snapshot(store: SQLiteStore, budget_service: BudgetService) -> dict[str, Any]:
    """K14 -- extra ciclo diario step (`GET /api/dashboard/{finance,
    orders}`'s own aggregation, reused rather than recomputed): writes
    throughput/cola/tasa-de-fallo a `metricas_diarias` (filas que no
    existían antes de K14) y un espejo agregado de costo por motor/oficina
    a `gastos`. Deliberately one row per (día, motor-u-oficina) bucket with
    a non-zero cost, not one row per execution -- `gastos`' schema has no
    concept of "individual run", and a per-run mirror would eventually
    dwarf the table with mostly-$0 rows (most of this environment's runs
    are tier-0/free). Every write goes through `monitoring.write_metric_
    row`/`write_expense_row`, both already "never raise" -- a Baserow
    outage degrades this step's return dict to `status: "error"`/
    `"sin_token"` entries, same as every other Baserow write in this
    script, never an exception that kills the rest of the cycle."""
    today = BudgetService.today()
    finance = dashboards.finance_dashboard(store, budget_service)
    orders = dashboards.orders_dashboard(store)

    # `metricas_diarias.valor` (Baserow) rejects more than 2 decimal places
    # (confirmed live: a first version of this function that passed
    # `failure_rate["rate"]` through unrounded -- 4 decimal places -- got a
    # real 400 `ERROR_REQUEST_BODY_VALIDATION`/`max_decimal_places` back).
    # Every value below is rounded to 2dp before it reaches `write_metric_
    # row`, matching the convention `write_baserow_metrics` above already
    # uses for its own percent fields (`round(conn_ok_pct, 2)` etc.) --
    # percentages are stored 0-100, not as a 0-1 fraction, for the same
    # reason.
    metric_rows = [
        ("sistema", "orders_active_count", float(orders["active_orders_count"]), ""),
        ("sistema", "orders_total_count", float(orders["orders_total_count"]), ""),
        ("sistema", "orders_failure_rate_pct", round((orders["failure_rate"]["rate"] or 0.0) * 100, 2),
         f"{orders['failure_rate']['done_count']} done / {orders['failure_rate']['failed_or_blocked_count']} failed+blocked"),
        ("sistema", "orders_queue_pending_plus_running",
         float(orders["queue"]["pending_executions"] + orders["queue"]["running_executions"]),
         "proxy sqlite, no QueueService en memoria (ver dashboards.orders_dashboard)"),
        ("sistema", "orders_avg_hours_to_done", round(orders["throughput"]["avg_hours_to_done"] or 0.0, 2),
         f"muestra={orders['throughput']['sample_size']}"),
        ("costos", "finance_projected_spend_usd", round(finance["today"]["projected_spend_usd"], 2), ""),
    ]
    metric_writes = []
    for oficina, metrica, valor, nota in metric_rows:
        outcome = monitoring.write_metric_row(today, oficina, metrica, valor, nota)
        metric_writes.append({"oficina": oficina, "metrica": metrica, "valor": valor, "result": outcome})

    # `gastos.monto_usd` (Baserow) is also a 2-decimal-place field
    # (confirmed via `GET /api/database/fields/table/136/`) -- same
    # rounding discipline as `metric_rows` above.
    expense_writes = []
    for row in finance["cost_by_executor"]:
        monto = round(row["cost_usd"], 2)
        if monto <= 0:
            continue
        outcome = monitoring.write_expense_row(
            today, row["executor"], "gasto agregado del día (motor/executor)", monto,
            aprobado_por="daily_cycle", solicitud_id="",
        )
        expense_writes.append({"oficina": row["executor"], "monto_usd": monto, "result": outcome})
    for row in finance["cost_by_office"]:
        monto = round(row["cost_usd"], 2)
        if monto <= 0:
            continue
        outcome = monitoring.write_expense_row(
            today, f"office-{row['office']}", "gasto agregado del día (oficina K9)", monto,
            aprobado_por="daily_cycle", solicitud_id="",
        )
        expense_writes.append({"oficina": f"office-{row['office']}", "monto_usd": monto, "result": outcome})

    return {"metric_writes": metric_writes, "expense_writes": expense_writes}


def main() -> int:
    result = run_cycle()

    baserow_writes = write_baserow_metrics(result)
    result["baserow_writes"] = baserow_writes

    store = SQLiteStore(settings.database_url)
    budget_service = BudgetService(store)
    finance_orders_snapshot = write_finance_and_orders_snapshot(store, budget_service)
    result["finance_orders_snapshot"] = finance_orders_snapshot

    report_dir = ROOT / "reports" / "daily"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{result['date']}.md"
    report_path.write_text(render_markdown(result), encoding="utf-8")

    baserow_ok = sum(1 for w in baserow_writes if w["result"].get("status") == "ok")
    snapshot_metric_ok = sum(1 for w in finance_orders_snapshot["metric_writes"] if w["result"].get("status") == "ok")
    snapshot_expense_ok = sum(1 for w in finance_orders_snapshot["expense_writes"] if w["result"].get("status") == "ok")
    print(f"reporte diario: {report_path}")
    print(f"alertas: {len(result['alerts'])}")
    print(f"baserow: {baserow_ok}/{len(baserow_writes)} filas escritas en metricas_diarias")
    print(
        f"baserow (K14 snapshot órdenes/finanzas): "
        f"{snapshot_metric_ok}/{len(finance_orders_snapshot['metric_writes'])} metricas_diarias, "
        f"{snapshot_expense_ok}/{len(finance_orders_snapshot['expense_writes'])} gastos"
    )
    if result["alerts"]:
        for alert in result["alerts"]:
            print(f"  ⚠️ {alert}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
