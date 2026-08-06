from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cano_hermes import __version__, monitoring
from cano_hermes.config import settings
from cano_hermes.domain.enums import ApprovalStatus
from cano_hermes.domain.models import TaskCreate
from cano_hermes.forge.duplication import DuplicateCandidateError
from cano_hermes.governance.budget import BudgetService
from cano_hermes.nexus.context import ContextBuilder
from cano_hermes.nexus.graph import KnowledgeGraph
from cano_hermes.nexus.markdown import MarkdownVault
from .dependencies import approvals, budget, engine, execution_service, forge_pipeline, registry, store


class ApprovalResolution(BaseModel):
    approved: bool
    actor: str


class ForgeCandidateRequest(BaseModel):
    definition: dict[str, Any]
    requested_by: str = "system"
    canal: str = "engineering"
    motivo: str | None = None
    costo_estimado_usd: float = 0.0


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.ensure_directories()
    engine().reap_orphaned()
    yield


app = FastAPI(title="Cano Hermes OS", version=__version__, lifespan=lifespan)
STATIC = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def dashboard():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "version": __version__,
        "execution_mode": settings.execution_mode,
        "agents": len(registry().all()),
        "tasks": len(store().list_tasks()),
    }


@app.get("/api/tasks")
def list_tasks():
    return store().list_tasks()


@app.post("/api/tasks")
def create_task(request: TaskCreate):
    return engine().create(request)


@app.post("/api/tasks/{task_id}/plan")
def plan_task(task_id: str):
    try:
        return engine().plan(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@app.get("/api/tasks/{task_id}/events")
def task_events(task_id: str):
    return store().list_events(task_id)


@app.get("/api/agents")
def list_agents():
    return registry().all()


@app.get("/api/approvals")
def list_approvals():
    return store().list_approvals()


@app.post("/api/approvals/{approval_id}/resolve")
def resolve_approval(approval_id: str, request: ApprovalResolution):
    try:
        return approvals().resolve(approval_id, request.approved, request.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/execute")
async def execute_task(task_id: str, executor_id: str | None = None):
    try:
        return await execution_service().run(task_id, executor_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@app.post("/api/forge/agents")
def propose_forge_agent(request: ForgeCandidateRequest):
    return _submit_forge_candidate("agent", request)


@app.post("/api/forge/skills")
def propose_forge_skill(request: ForgeCandidateRequest):
    return _submit_forge_candidate("skill", request)


def _submit_forge_candidate(kind: str, request: ForgeCandidateRequest):
    try:
        return forge_pipeline().submit(
            kind,
            request.definition,
            requested_by=request.requested_by,
            canal=request.canal,
            motivo=request.motivo,
            costo_estimado_usd=request.costo_estimado_usd,
        )
    except DuplicateCandidateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/forge/candidates")
def list_forge_candidates():
    return forge_pipeline().list_candidates()


@app.get("/api/forge/candidates/{candidate_id}")
def forge_candidate_status(candidate_id: str):
    try:
        return forge_pipeline().status(candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Candidate not found") from exc


@app.post("/api/forge/candidates/{candidate_id}/promote")
def promote_forge_candidate(candidate_id: str):
    try:
        return forge_pipeline().promote(candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Candidate or approval not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/nexus/search")
def nexus_search(q: str):
    return MarkdownVault(settings.vault_path).search(q)


@app.get("/api/nexus/context")
def nexus_context(q: str):
    vault = MarkdownVault(settings.vault_path)
    return ContextBuilder(vault, KnowledgeGraph(vault)).build(q)


@app.get("/api/dashboard")
def dashboard_data() -> dict[str, Any]:
    """Plan Prometeo F13 — single aggregated JSON for the operator dashboard.

    Every piece here is either already-built (F3's ApprovalService/
    BudgetService) or a read of an on-disk artifact `daily_cycle.py` (F13)
    already wrote — this endpoint does no network I/O of its own and stays
    fast on every GET, unlike `daily_cycle.py`'s connection-matrix step
    which does two live checks.

    "Solicitudes" are never hand-built here: `store().list_approvals()`
    already round-trips every stored row through `ApprovalRequest.
    model_validate_json` (F3's schema, `motivo`/`costo_estimado_usd`/
    `presupuesto_restante`/`canal`/`evidencia` all mandatory) — an
    incomplete row fails at read time with Pydantic's own per-field
    message instead of reaching this endpoint as partial JSON.
    """
    all_approvals = store().list_approvals()
    pending = [a for a in all_approvals if a.status == ApprovalStatus.PENDING]

    today = BudgetService.today()
    ledger = budget().ledger_for(today)
    percent_used = (ledger.spent_usd / ledger.daily_limit_usd) if ledger.daily_limit_usd > 0 else 0.0

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "approvals_pending": [a.model_dump(mode="json") for a in pending],
        "approvals_pending_count": len(pending),
        "budget": {
            "day": today,
            "daily_limit_usd": ledger.daily_limit_usd,
            "spent_usd": ledger.spent_usd,
            "remaining_usd": ledger.remaining_usd,
            "percent_used": round(percent_used, 4),
        },
        "connections": monitoring.latest_connection_matrix_summary(),
        "ugc_performance": monitoring.ugc_performance_summary(),
        "offices": monitoring.office_container_status(),
        "baserow": {
            "base_url": monitoring.BASEROW_BASE_URL,
            "configured": monitoring.baserow_configured(),
            "tables": {
                "solicitudes": f"{monitoring.BASEROW_BASE_URL}/database/34/table/130/",
                "gastos": f"{monitoring.BASEROW_BASE_URL}/database/34/table/136/",
                "productos_ugc": f"{monitoring.BASEROW_BASE_URL}/database/34/table/140/",
                "metricas_diarias": f"{monitoring.BASEROW_BASE_URL}/database/34/table/{monitoring.BASEROW_METRICAS_TABLE_ID}/",
            },
        },
    }


def _dashboard_html(data: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    budget_row = data["budget"]
    approvals_html = "".join(
        f"<div class='card'><span class='pill'>{esc(a['canal'])}</span>"
        f"<span class='pill'>${esc(a['costo_estimado_usd'])}</span>"
        f"<h3>{esc(a['action'])}</h3><p class='muted'>{esc(a['motivo'])}</p>"
        f"<small>pedido por {esc(a['requested_by'])} · restante ${esc(a['presupuesto_restante'])} "
        f"· evidencia: {esc(a['evidencia'])}</small></div>"
        for a in data["approvals_pending"]
    ) or "<p class='muted'>Sin solicitudes pendientes.</p>"

    conn = data["connections"]
    conn_html = (
        f"<p>Totales: ✓{esc(conn['totals'].get('✓','?'))} ✗{esc(conn['totals'].get('✗','?'))} "
        f"—{esc(conn['totals'].get('—','?'))} <span class='muted'>({esc(conn['date'])})</span></p>"
        if conn else "<p class='muted'>Sin matriz de conexiones generada todavía — correr scripts/connection_matrix.py o scripts/daily_cycle.py.</p>"
    )

    offices_html = "".join(
        f"<span class='pill'>{esc(name)}: {esc(state)}</span>" for name, state in data["offices"].items()
    )

    baserow = data["baserow"]
    baserow_links = "".join(
        f"<li><a href='{esc(url)}' target='_blank' rel='noopener'>{esc(name)}</a></li>"
        for name, url in baserow["tables"].items()
    )

    ugc = data["ugc_performance"]

    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>StarHome OS — Dashboard</title><link rel="stylesheet" href="/static/style.css"></head>
<body style="display:block;padding:28px">
<header style="border-bottom:1px solid #1d273a;padding-bottom:18px;display:flex;justify-content:space-between;align-items:center">
<div><h2 style="margin:0">StarHome OS — Dashboard agregado</h2>
<small class="muted">Generado {esc(data['generated_at'])}</small></div>
</header>
<div class="grid">
<div class="card"><div class="muted">Presupuesto hoy</div>
<div class="metric">${esc(f"{budget_row['spent_usd']:.2f}")} / ${esc(f"{budget_row['daily_limit_usd']:.2f}")}</div>
<p class="muted">{esc(f"{budget_row['percent_used']*100:.1f}")}% usado · restante ${esc(f"{budget_row['remaining_usd']:.2f}")}</p></div>
<div class="card"><div class="muted">Aprobaciones pendientes</div>
<div class="metric">{esc(data['approvals_pending_count'])}</div></div>
<div class="card"><div class="muted">Oficinas F11</div><p>{offices_html}</p></div>
<div class="card"><div class="muted">UGC (F9)</div><p>{esc(ugc['classification'])}</p>
<small class="muted">{esc(ugc['note'])}</small></div>
</div>
<div class="card" style="margin-top:16px"><h3>Conexiones (F2)</h3>{conn_html}</div>
<div class="card" style="margin-top:16px"><h3>Solicitudes pendientes</h3>{approvals_html}</div>
<div class="card" style="margin-top:16px"><h3>Baserow</h3>
<p class="muted">{"configurado" if baserow["configured"] else "BASEROW_TOKEN no encontrado en el vault"}</p>
<ul>{baserow_links}</ul></div>
</body></html>"""


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_view():
    return _dashboard_html(dashboard_data())
