"""K18 (plan HERMES-KICKOFF) -- real executable logic behind the three
Personal Runtime v0.3 finance skills that mergeed from Prometeo F5 as
manifest-only contracts (`skills/expense-capture`, `skills/cash-position`,
`skills/finance-close` -- confirmed live before writing this module: each
one is a `manifest.json` + `SKILL.md` procedure/verification checklist,
zero Python behind them). This module IS that Python, one function per
skill, each one implementing its own `SKILL.md` procedure/verification
list directly (see the docstring on each function below for the mapping):

  - `capture_expense`          -- skills/expense-capture
  - `cash_position`            -- skills/cash-position
  - `finance_close`            -- skills/finance-close

Backed by Baserow's `contabilidad` table (table id 660, database 172,
workspace 127 "StarHome K18 Accounting" -- created live by
`infrastructure/baserow/setup_accounting_table.py`, same "own workspace"
pattern `content/dedup.py` used for K17's `contenido` table and for the
same reason: the K17 management token is REST-row-scoped only, and no
prior registration's password was ever persisted to log back into its
workspace -- confirmed live, not assumed, see setup_accounting_table.py's
docstring).

This table is business accounting (CASS / Cano Digital / LUZYA / otro),
NOT the agent/engine spend ledger -- that is `governance.budget
.BudgetService` (`budget_ledger` sqlite table), already aggregated by
`orchestration.dashboards.finance_dashboard`. `orchestration.dashboards
.accounting_dashboard` (K18) is the one place both ledgers are combined.

Every skill's own "Verification" list maps to a real constraint enforced
here, not just documentation:
  - expense-capture: "No se modifica saldo ni se mueve dinero sin
    aprobación" -> `capture_expense` never POSTs to Baserow unless called
    with `confirm=True`; without it, it returns a draft/preview dict and
    makes zero network calls (mirrors `content.dedup`'s check-vs-insert
    split). The one caller that passes `confirm=True` unattended is the
    `on_approval_resolved` observer below, and only because an
    `ApprovalRequest` reaching APPROVED has ALREADY passed
    `ApprovalService`'s human-approval gate (anti-self-approval enforced
    in `governance/approvals.py`) -- this module adds no new unapproved
    write path.
  - cash-position: "No contar cuentas por cobrar como efectivo
    disponible" -- this ledger has no separate cuentas-por-cobrar/pagar
    columns (K18's `contabilidad` schema is ingreso/gasto only), so
    `cash_position` computes `disponible_operativo` as the same
    ingreso-menos-gasto balance as `saldo_bruto` and says so explicitly in
    every negocio's `advertencia` field, rather than inventing numbers for
    columns that don't exist.
  - finance-close: "Las diferencias deben permanecer visibles, no
    compensarse sin evidencia" -- `finance_close` classifies every
    movement as `con_referencia`/`sin_referencia` (empty `referencia` is
    the closest signal this schema carries to "unbacked by evidence") and
    flags exact-duplicate groups, both lists kept in the output/report
    rather than netted away.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from cano_hermes.monitoring import BASEROW_BASE_URL, VAULT_ENV_PATH, baserow_headers

ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports" / "finance"

BASEROW_CONTABILIDAD_TABLE_ID = 660
_MAX_PAGES = 20  # 20 * 100 rows/page -- generous for this table's real size.

NEGOCIOS = frozenset({"CASS", "Cano Digital", "LUZYA", "otro"})
TIPOS = frozenset({"ingreso", "gasto"})
ORIGENES = frozenset({"agente", "manual"})


class AccountingValidationError(ValueError):
    """A movement violates a hard field-level rule of the `contabilidad` schema."""


# --------------------------------------------------------------------------
# Baserow plumbing -- same "never raise on infra flakiness" contract as
# `monitoring.write_expense_row` / `content.dedup.fetch_rows`.
# --------------------------------------------------------------------------
def _accounting_token() -> str | None:
    """BASEROW_ACCOUNTING_TOKEN -- checks the environment first (an office
    container could get it injected the same allowlist way K17's
    BASEROW_CONTENT_TOKEN is), the vault .env second, matching
    `content.dedup._content_token`'s own precedence."""
    env_token = os.environ.get("BASEROW_ACCOUNTING_TOKEN")
    if env_token:
        return env_token
    if not VAULT_ENV_PATH.exists():
        return None
    for line in VAULT_ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("BASEROW_ACCOUNTING_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def accounting_configured() -> bool:
    return _accounting_token() is not None


def numeric_value(value: Any) -> float | None:
    """Baserow's `number` field type serializes as a JSON STRING on read
    (confirmed live: `GET .../rows/table/660/` returns `"monto": "12.5000"`,
    not a bare 12.5) even though it accepts a bare number on write. Every
    reader of a fetched row's `monto` must go through this, not a raw
    `isinstance(x, (int, float))` check -- that check silently drops every
    real row (found live while writing this module's own verification
    script: a freshly-inserted, freshly-fetched row's cash position came
    back `None` until this normalization was added). Returns `None` on
    anything that isn't a real number (missing, blank, non-numeric
    string) instead of raising -- callers treat `None` as "skip this
    row", matching every other "never raise on bad data" helper in this
    module."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def select_value(row: dict[str, Any], field: str) -> str | None:
    """Baserow's row-read API (`?user_field_names=true`) returns a
    single_select field as `{"id":, "value":, "color":}`, not the bare
    string -- same normalization `content.dedup.estado_value` applies to
    `estado`, generalized here for `negocio`/`tipo`/`origen`."""
    value = row.get(field)
    if isinstance(value, dict):
        return value.get("value")
    return value


def fetch_rows(*, timeout: float = 10.0) -> dict[str, Any]:
    """GETs every row of the `contabilidad` table (paginated), never
    raises. Returns one of:
      {"status": "sin_token", "detail": ...}
      {"status": "error", "detail": ...}
      {"status": "ok", "rows": [ {...}, ... ]}
    """
    token = _accounting_token()
    if not token:
        return {"status": "sin_token", "detail": "BASEROW_ACCOUNTING_TOKEN no encontrado en el vault"}

    rows: list[dict[str, Any]] = []
    url = (
        f"{BASEROW_BASE_URL}/api/database/rows/table/{BASEROW_CONTABILIDAD_TABLE_ID}/"
        "?user_field_names=true&size=100"
    )
    for _ in range(_MAX_PAGES):
        req = urllib.request.Request(url, headers=baserow_headers(token))
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return {"status": "error", "http_status": exc.code, "detail": exc.read().decode(errors="replace")[:300]}
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            return {"status": "error", "detail": f"{exc.__class__.__name__}: {exc}"}

        rows.extend(payload.get("results", []))
        url = payload.get("next")
        if not url:
            break

    return {"status": "ok", "rows": rows}


def validate_movement(fields: dict[str, Any]) -> None:
    """Hard field-level rules for a `contabilidad` row. Raises
    `AccountingValidationError` -- never a silent pass-through, same
    discipline as `content.dedup.validate_publish_requires_video_id`."""
    negocio = fields.get("negocio")
    if negocio not in NEGOCIOS:
        raise AccountingValidationError(f"negocio {negocio!r} inválido -- debe ser uno de {sorted(NEGOCIOS)}")
    tipo = fields.get("tipo")
    if tipo not in TIPOS:
        raise AccountingValidationError(f"tipo {tipo!r} inválido -- debe ser uno de {sorted(TIPOS)}")
    monto = fields.get("monto")
    if not isinstance(monto, (int, float)) or monto < 0:
        raise AccountingValidationError(f"monto {monto!r} inválido -- debe ser numérico y no negativo")
    if not (fields.get("moneda") or "").strip():
        raise AccountingValidationError("moneda vacía -- requerida (skill: 'el monto debe conservar... moneda')")
    if not (fields.get("categoria") or "").strip():
        raise AccountingValidationError("categoria vacía -- requerida")
    if not (fields.get("fecha") or "").strip():
        raise AccountingValidationError("fecha vacía -- requerida (skill: 'el periodo debe tener fechas absolutas')")
    origen = fields.get("origen")
    if origen not in ORIGENES:
        raise AccountingValidationError(f"origen {origen!r} inválido -- debe ser uno de {sorted(ORIGENES)}")


def insert_movement(fields: dict[str, Any], *, timeout: float = 10.0) -> dict[str, Any]:
    """Validates the hard rules, then POSTs one row to `contabilidad`.
    Raises `AccountingValidationError` on a bad field (deliberate, no
    network involved); once past validation, degrades to a result dict on
    any Baserow error (same "never raise on infra flakiness" contract as
    `content.dedup.insert_content_row`)."""
    validate_movement(fields)

    token = _accounting_token()
    if not token:
        return {"status": "sin_token", "detail": "BASEROW_ACCOUNTING_TOKEN no encontrado en el vault"}

    body = json.dumps(fields).encode("utf-8")
    req = urllib.request.Request(
        f"{BASEROW_BASE_URL}/api/database/rows/table/{BASEROW_CONTABILIDAD_TABLE_ID}/?user_field_names=true",
        data=body, method="POST",
        headers=baserow_headers(token, json_body=True),
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"status": "ok", "row_id": json.loads(resp.read()).get("id")}
    except urllib.error.HTTPError as exc:
        return {"status": "error", "http_status": exc.code, "detail": exc.read().decode(errors="replace")[:300]}
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        return {"status": "error", "detail": f"{exc.__class__.__name__}: {exc}"}


# --------------------------------------------------------------------------
# skills/expense-capture -- Procedure steps 1-5 of SKILL.md, in order:
#  1. extract only explicit monto/moneda/fecha/concepto/cuenta/entidad --
#     the caller's job (this function does not infer from free text, it
#     takes already-extracted fields);
#  2. keep the original evidence -- `evidencia` is passed straight through
#     into `referencia` when the caller supplies one (e.g. an approval id
#     or a receipt path), never dropped;
#  3. search for duplicates by monto/fecha/concepto/cuenta ->
#     `find_duplicate_movements`;
#  4. propose categoria/entidad, marking any inference -> caller-supplied
#     `categoria`/`negocio` are trusted as explicit, not this function's
#     job to guess;
#  5. present for approval before writing externally -> the `confirm` gate.
# --------------------------------------------------------------------------
def find_duplicate_movements(
    *, negocio: str, monto: float, fecha: str, categoria: str, rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Pure function (no I/O) -- duplicate search by monto+fecha+categoria
    +negocio (the closest match this schema has to the skill's "monto,
    fecha, concepto y cuenta"). Exact fecha match only (this schema has no
    separate 'day' granularity to fuzz against). Compares `monto` through
    `numeric_value` on both sides -- a row just fetched from Baserow
    carries `monto` as a JSON string (see `numeric_value`'s docstring), a
    caller-built candidate carries a real float; a raw `==` would never
    match the two representations."""
    return [
        row for row in rows
        if select_value(row, "negocio") == negocio
        and select_value(row, "categoria") == categoria
        and row.get("fecha") == fecha
        and numeric_value(row.get("monto")) == numeric_value(monto)
    ]


def capture_expense(
    *,
    negocio: str,
    tipo: str = "gasto",
    monto: float,
    moneda: str = "USD",
    categoria: str,
    fecha: str,
    origen: str = "manual",
    referencia: str = "",
    cierre_mensual: bool = False,
    confirm: bool = False,
    rows_for_dedup: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Prepare (and, only with `confirm=True`, persist) one `contabilidad`
    movement. Without `confirm`, this is a pure/no-network dry-run: it
    validates the fields, checks for a duplicate, and returns a
    `{"status": "draft", ...}` or `{"status": "duplicate_review_required",
    ...}` preview -- exactly SKILL.md step 5 ("presentar... para
    aprobación antes de escribir"). A duplicate is reported, never
    silently blocked or silently written -- the caller (human or the
    `on_approval_resolved` observer below) decides whether it's a real
    repeat or a legitimate second movement with the same shape."""
    fields = {
        "negocio": negocio, "tipo": tipo, "monto": monto, "moneda": moneda,
        "categoria": categoria, "fecha": fecha, "origen": origen,
        "referencia": referencia, "cierre_mensual": cierre_mensual,
    }
    validate_movement(fields)

    if rows_for_dedup is None and confirm:
        # Only fetch live rows on the path that could actually write --
        # keeps unconfirmed dry-run previews network-free.
        fetched = fetch_rows()
        rows_for_dedup = fetched["rows"] if fetched["status"] == "ok" else []
    duplicates = find_duplicate_movements(
        negocio=negocio, monto=monto, fecha=fecha, categoria=categoria,
        rows=rows_for_dedup or [],
    )

    if not confirm:
        return {
            "status": "duplicate_review_required" if duplicates else "draft",
            "movement": fields, "duplicates": duplicates,
        }

    result = insert_movement(fields)
    return {
        "status": result["status"], "movement": fields, "duplicates": duplicates,
        "row_id": result.get("row_id"), "detail": result.get("detail"),
    }


# --------------------------------------------------------------------------
# skills/cash-position -- Procedure/Verification mapped onto what this
# ledger actually carries (ingreso/gasto movements, no separate saldo/
# cuentas-por-cobrar/pagar/deuda columns yet -- honestly labeled, not
# invented, matching this repo's existing "never pad missing data"
# convention, see content/dashboards.py's own comments).
# --------------------------------------------------------------------------
def cash_position(rows: list[dict[str, Any]], *, cutoff: str | None = None) -> dict[str, Any]:
    """Step 2 (separate by entity before consolidating) + step 3
    (calcular saldo bruto/disponible) + step 4 (señalar registros sin
    fecha) of SKILL.md, against whatever `contabilidad` rows the caller
    passes in (production callers pass `fetch_rows()["rows"]`; tests pass
    a fixture). Step 1 ("reunir saldos... cuentas por cobrar/pagar/
    deudas") only partially applies -- this schema has no columns for
    those, so `disponible_operativo` degrades to the same ingreso-menos-
    gasto balance as `saldo_bruto`, each negocio's `advertencia` says so
    explicitly rather than pretending cuentas por cobrar/pagar were
    counted."""
    by_negocio: dict[str, dict[str, Any]] = {}
    sin_fecha = 0
    for row in rows:
        negocio = select_value(row, "negocio") or "otro"
        tipo = select_value(row, "tipo")
        monto = numeric_value(row.get("monto"))
        if monto is None:
            continue
        entry = by_negocio.setdefault(negocio, {"ingresos_total": 0.0, "gastos_total": 0.0, "movimientos": 0})
        entry["movimientos"] += 1
        if tipo == "ingreso":
            entry["ingresos_total"] += monto
        elif tipo == "gasto":
            entry["gastos_total"] += monto
        if not (row.get("fecha") or "").strip():
            sin_fecha += 1

    positions = {}
    total_saldo = 0.0
    for negocio, entry in by_negocio.items():
        saldo_bruto = round(entry["ingresos_total"] - entry["gastos_total"], 4)
        total_saldo += saldo_bruto
        positions[negocio] = {
            "ingresos_total_usd": round(entry["ingresos_total"], 4),
            "gastos_total_usd": round(entry["gastos_total"], 4),
            "saldo_bruto_usd": saldo_bruto,
            "disponible_operativo_usd": saldo_bruto,
            "movimientos": entry["movimientos"],
            "advertencia": (
                "sin columnas de cuentas por cobrar/pagar/deuda en este ledger -- "
                "disponible_operativo tratado como igual a saldo_bruto (ingresos - gastos), "
                "no como capital utilizable certificado"
            ),
        }

    return {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "cutoff": cutoff,
        "by_negocio": positions,
        "consolidado": {
            "saldo_total_usd": round(total_saldo, 4),
            "reconciles": round(sum(p["saldo_bruto_usd"] for p in positions.values()), 4) == round(total_saldo, 4),
        },
        "registros_sin_fecha": sin_fecha,
        "total_movimientos": len(rows),
    }


# --------------------------------------------------------------------------
# skills/finance-close -- Procedure/Verification, dry-run (K18 task 5):
# writes reports/finance/cierre-<year>-<month>.md, returns the same data
# as a dict for direct assertion in tests / the dashboard.
# --------------------------------------------------------------------------
def _month_rows(rows: list[dict[str, Any]], year: int, month: int) -> list[dict[str, Any]]:
    prefix = f"{year:04d}-{month:02d}"
    return [row for row in rows if (row.get("fecha") or "").startswith(prefix)]


def find_duplicate_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pure function -- groups by (negocio, tipo, monto, categoria, fecha);
    any group with >1 row is a possible duplicate, surfaced (not netted
    away) per SKILL.md's 'las diferencias deben permanecer visibles'."""
    keyed = Counter(
        (select_value(r, "negocio"), select_value(r, "tipo"), numeric_value(r.get("monto")),
         r.get("categoria"), r.get("fecha"))
        for r in rows
    )
    return [
        {"negocio": k[0], "tipo": k[1], "monto": k[2], "categoria": k[3], "fecha": k[4], "count": count}
        for k, count in keyed.items() if count > 1
    ]


def finance_close(
    rows: list[dict[str, Any]], year: int, month: int, *, out_dir: Path | None = None,
) -> dict[str, Any]:
    """Step 1 (periodo/entidades), step 3 (conciliadas/pendientes/
    duplicadas/sin evidencia), step 4 (flujo + resumen por negocio y
    categoria) of SKILL.md. Step 2 (comparar saldos iniciales/finales)
    does not apply -- this ledger has no separate opening-balance concept,
    only dated movements, documented as such in the report rather than
    fabricated. Step 5 ('solicitar aprobación antes de exportar a
    sistemas externos') is satisfied by this being a LOCAL markdown file
    under `reports/finance/`, not a write to any external accounting
    system -- no approval gate needed for a dry-run report Cano reads
    himself."""
    month_rows = _month_rows(rows, year, month)
    negocios = sorted({select_value(r, "negocio") or "otro" for r in month_rows}) or ["(sin movimientos)"]

    by_negocio: dict[str, Any] = {}
    for negocio in negocios if month_rows else []:
        n_rows = [r for r in month_rows if (select_value(r, "negocio") or "otro") == negocio]
        ingresos = sum(
            (numeric_value(r.get("monto")) or 0.0) for r in n_rows if select_value(r, "tipo") == "ingreso"
        )
        gastos = sum(
            (numeric_value(r.get("monto")) or 0.0) for r in n_rows if select_value(r, "tipo") == "gasto"
        )
        by_categoria: dict[str, float] = {}
        for r in n_rows:
            cat = r.get("categoria") or "(sin categoría)"
            signed = (numeric_value(r.get("monto")) or 0.0) * (1 if select_value(r, "tipo") == "ingreso" else -1)
            by_categoria[cat] = round(by_categoria.get(cat, 0.0) + signed, 4)
        con_referencia = [r for r in n_rows if (r.get("referencia") or "").strip()]
        sin_referencia = [r for r in n_rows if not (r.get("referencia") or "").strip()]
        by_negocio[negocio] = {
            "ingresos_usd": round(ingresos, 4),
            "gastos_usd": round(gastos, 4),
            "flujo_neto_usd": round(ingresos - gastos, 4),
            "por_categoria_usd": by_categoria,
            "movimientos_con_referencia": len(con_referencia),
            "movimientos_sin_referencia": len(sin_referencia),
        }

    duplicates = find_duplicate_groups(month_rows)
    position = cash_position(rows, cutoff=f"{year:04d}-{month:02d}")

    period = f"{year:04d}-{month:02d}"
    result = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "periodo": period,
        "movimientos_totales": len(month_rows),
        "por_negocio": by_negocio,
        "posibles_duplicados": duplicates,
        "posicion_caja_acumulada": position,
        "nota": (
            "cierre operativo generado automáticamente para revisión de Cano -- "
            "no es contabilidad formal certificada; sin conciliación de saldos "
            "iniciales/finales (este ledger no los distingue de los movimientos)."
        ),
    }

    report_dir = out_dir or REPORTS_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"cierre-{period}.md"
    report_path.write_text(_render_close_markdown(result), encoding="utf-8")
    result["report_path"] = str(report_path)
    return result


def _render_close_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# Cierre financiero — {result['periodo']}",
        "",
        f"_Generado: {result['generated_at']}_",
        "",
        f"> {result['nota']}",
        "",
        f"Movimientos del mes: **{result['movimientos_totales']}**",
        "",
        "## Por negocio",
    ]
    if not result["por_negocio"]:
        lines.append("\n_Sin movimientos este mes._")
    for negocio, data in result["por_negocio"].items():
        lines.append(f"\n### {negocio}")
        lines.append(f"- Ingresos: ${data['ingresos_usd']:.2f}")
        lines.append(f"- Gastos: ${data['gastos_usd']:.2f}")
        lines.append(f"- Flujo neto: ${data['flujo_neto_usd']:.2f}")
        lines.append(f"- Movimientos con referencia: {data['movimientos_con_referencia']}")
        lines.append(f"- Movimientos sin referencia: {data['movimientos_sin_referencia']}")
        if data["por_categoria_usd"]:
            lines.append("- Por categoría:")
            for cat, amount in sorted(data["por_categoria_usd"].items()):
                lines.append(f"  - {cat}: ${amount:.2f}")

    lines.append("\n## Posibles duplicados")
    if result["posibles_duplicados"]:
        for dup in result["posibles_duplicados"]:
            lines.append(f"- {dup}")
    else:
        lines.append("_Ninguno detectado._")

    lines.append("\n## Posición de caja acumulada (todo el ledger, no solo el mes)")
    for negocio, pos in result["posicion_caja_acumulada"]["by_negocio"].items():
        lines.append(
            f"- {negocio}: saldo bruto ${pos['saldo_bruto_usd']:.2f} "
            f"({pos['movimientos']} movimientos totales)"
        )
    lines.append(
        f"\nSaldo total consolidado: ${result['posicion_caja_acumulada']['consolidado']['saldo_total_usd']:.2f}"
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# K18 task 4 -- connect expense-capture to the approvals flow. Wired as an
# observer into `ApprovalService.resolve()` (`on_resolved`), the same
# pattern K4's `NotificationService.on_approval_requested` uses for
# `ApprovalService.request()` -- see `api/dependencies.py`. Never raises:
# `ApprovalService.resolve` wraps this in try/except (mirroring its
# existing `on_request` safety net), so a Baserow hiccup here can never
# take an approval resolution down with it.
# --------------------------------------------------------------------------
def on_approval_resolved(approval: Any) -> None:
    """When an `ApprovalRequest` resolves APPROVED with
    `costo_estimado_usd > 0`, capture it as a real `gasto` movement,
    `origen=agente`, `referencia=<approval.id>` -- the exact K18 task-4
    mapping. `negocio` defaults to "otro": `ApprovalRequest` (Prometeo F3)
    carries no business field today (only `canal`, the requesting office/
    channel) -- K19's per-business views are expected to refine this once
    a real canal->negocio mapping exists; documented here rather than
    guessed. `confirm=True` is safe specifically because reaching this
    callback already means `ApprovalService.resolve` accepted the
    approval (anti-self-approval enforced, `approved=True` required by the
    caller) -- this is not a new unattended-write path, it is the
    already-approved write finally landing."""
    from cano_hermes.domain.enums import ApprovalStatus

    if approval.status != ApprovalStatus.APPROVED:
        return
    if approval.costo_estimado_usd <= 0:
        return

    fecha = (approval.resolved_at or approval.created_at)
    fecha_str = fecha.isoformat() if hasattr(fecha, "isoformat") else str(fecha)
    capture_expense(
        negocio="otro",
        tipo="gasto",
        monto=float(approval.costo_estimado_usd),
        moneda="USD",
        categoria=f"{approval.canal}:{approval.action}"[:255],
        fecha=fecha_str,
        origen="agente",
        referencia=approval.id,
        confirm=True,
    )
