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
  6. Escribe cada métrica a la tabla `metricas_diarias` de Baserow (F11,
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
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cano_hermes import monitoring  # noqa: E402
from cano_hermes.config import settings  # noqa: E402
from cano_hermes.governance.budget import BudgetService  # noqa: E402
from cano_hermes.storage.sqlite import SQLiteStore  # noqa: E402

BUDGET_ALERT_THRESHOLD = 0.8


def run_cycle() -> dict[str, Any]:
    today = datetime.date.today().isoformat()
    result: dict[str, Any] = {"date": today}

    # 1. Connection matrix (F2) -- actually runs it (not the cached
    # summary the dashboard reads) so today's report is fresh.
    try:
        result["connections"] = monitoring.run_connection_matrix()
    except Exception as exc:  # noqa: BLE001 -- one failing step must not kill the cycle
        result["connections"] = {"status": "error", "detail": str(exc)}

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
    if percent_used > BUDGET_ALERT_THRESHOLD:
        alerts.append(
            f"Presupuesto del día al {percent_used * 100:.0f}% "
            f"(${ledger.spent_usd:.2f} de ${ledger.daily_limit_usd:.2f})."
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

    rows_to_write = [
        ("sistema", "connection_matrix_ok_pct", round(conn_ok_pct, 2), "F2, % de variables ✓ sobre el total revisado"),
        ("sistema", "starhome_api_health", 1.0 if result["health"]["starhome_api"]["status"] == "ok" else 0.0, ""),
        ("sistema", "audit_status_pass", 1.0 if result["audit"]["status"] == "PASS" else 0.0, ""),
        ("sistema", "budget_percent_used", round(budget["percent_used"] * 100, 2), f"día {today}"),
        ("sistema", "budget_remaining_usd", round(budget["remaining_usd"], 4), ""),
        ("costos", "usage_files_total_cost_usd", result["costs"]["usage_files"]["total_cost_usd"], ""),
        ("ugc", "performance_classification", 0.0, result["ugc_performance"]["note"]),
    ]

    written = []
    for oficina, metrica, valor, nota in rows_to_write:
        outcome = monitoring.write_metric_row(today, oficina, metrica, valor, nota)
        written.append({"oficina": oficina, "metrica": metrica, "valor": valor, "result": outcome})
    return written


def main() -> int:
    result = run_cycle()

    baserow_writes = write_baserow_metrics(result)
    result["baserow_writes"] = baserow_writes

    report_dir = ROOT / "reports" / "daily"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{result['date']}.md"
    report_path.write_text(render_markdown(result), encoding="utf-8")

    baserow_ok = sum(1 for w in baserow_writes if w["result"].get("status") == "ok")
    print(f"reporte diario: {report_path}")
    print(f"alertas: {len(result['alerts'])}")
    print(f"baserow: {baserow_ok}/{len(baserow_writes)} filas escritas en metricas_diarias")
    if result["alerts"]:
        for alert in result["alerts"]:
            print(f"  ⚠️ {alert}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
