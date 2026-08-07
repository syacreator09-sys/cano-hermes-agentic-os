from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cano_hermes import __version__, monitoring
from cano_hermes.bridge import inbound as kanban_inbound
from cano_hermes.bridge import kanban_bridge
from cano_hermes.bridge.kanban_bridge import KanbanBridgeError
from cano_hermes.config import settings
from cano_hermes.domain.enums import ApprovalStatus, OrderStatus, TaskStatus
from cano_hermes.domain.models import OrderCreate, OrderRecord, TaskCreate, TaskEvent
from cano_hermes.forge.duplication import DuplicateCandidateError
from cano_hermes.governance.budget import BudgetService
from cano_hermes.nexus.context import ContextBuilder
from cano_hermes.nexus.graph import KnowledgeGraph
from cano_hermes.nexus.graphify_adapter import GraphifyAdapter
from cano_hermes.nexus.markdown import MarkdownVault

from .dependencies import (
    approvals,
    budget,
    engine,
    execution_service,
    forge_pipeline,
    memory_candidates,
    notification_service,
    queue_service,
    registry,
    store,
)

logger = logging.getLogger(__name__)


class ApprovalResolution(BaseModel):
    approved: bool
    actor: str


class TaskCompletion(BaseModel):
    actor: str = "cano"
    reason: str = "manual-completion"


class MemoryCandidateResolution(BaseModel):
    decision: str
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
    # K3: the worker loop that actually drains QueueService's queue lives for
    # the app's lifetime, started here alongside the K0 startup reaper (which
    # stays as the immediate once-at-boot pass; QueueService's own reaper
    # loop then repeats that same reap_orphaned() periodically while the app
    # keeps running).
    await queue_service().start()
    try:
        yield
    finally:
        await queue_service().stop()


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


@app.post("/api/orders", status_code=201)
def create_order(request: OrderCreate):
    """K5 -- CRUD-only creation: an order always starts at
    `OrderStatus.RECEIVED` with no subtasks, regardless of what the caller
    sends (`OrderCreate` has no `status`/`subtask_ids` fields to smuggle
    those in). Decomposing it into tasks and dispatching them to Kanban is
    K6's job, not this endpoint's.
    """
    order = OrderRecord(objective=request.objective, source=request.source, budget=request.budget)
    return store().save_order(order)


@app.get("/api/orders")
def list_orders():
    """K8 -- symmetric with `GET /api/tasks`; added alongside the CLI's
    `order list` (`cano_hermes/cli.py`) so the CLI can stay a pure HTTP
    client for all three `order` verbs instead of mixing HTTP for
    submit/status with direct `SQLiteStore` access for list. Newest first
    (`SQLiteStore.list_orders` already orders by `created_at DESC`)."""
    return store().list_orders()


@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    """K5 -- resolves child tasks via `list_children(order_id)` (matching
    on `TaskRecord.parent_task_id`) rather than trusting
    `OrderRecord.subtask_ids`, since nothing populates that field yet
    (K6/K7 own decomposition and aggregation) -- `list_children` is the
    live source of truth for "which tasks currently belong to this order."
    """
    order = store().get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    tasks = store().list_children(order_id)
    return {**order.model_dump(mode="json"), "tasks": [t.model_dump(mode="json") for t in tasks]}


@app.post("/api/orders/{order_id}/dispatch")
def dispatch_order(order_id: str):
    """K6 -- deliberately an explicit trigger, not automatic inside
    `POST /api/orders`. The architecture diagram in the plan
    (`~/.claude/plans/fluffy-twirling-lecun.md`) draws a governance step
    between order intake and the bridge -- "POST /api/orders -> riesgo/
    presupuesto/aprobación -> audit ... ▼ aprobada -> KanbanBridge" -- and
    K12 ("Autonomía gobernada") is explicitly the future phase that decides
    *when* an order clears that gate automatically. Making dispatch its own
    endpoint keeps that seam real today (a human, or a future policy
    engine, calls this once an order is actually approved to spend kanban/
    worker resources) instead of collapsing intake and dispatch into one
    step now and having to split them apart again later.

    Only a `RECEIVED` order can be dispatched (409 otherwise) -- this is a
    one-way, one-time transition; re-dispatching a `DISPATCHED`/`FAILED`
    order is refused rather than silently creating a second bridge link
    (the bridge's own `--idempotency-key` already makes the *kanban* side
    idempotent, but the *order* side still only gets one bridge_links row
    via `save_bridge_link`'s upsert-on-starhome_id, so a second dispatch
    attempt against an already-dispatched order would just overwrite that
    row with nothing new to show for it).

    On success: `bridge_links` row saved, order -> DISPATCHED.
    On any `KanbanBridgeError` (hermes CLI missing, non-zero exit, timeout,
    unparseable output): order -> FAILED with the captured error message on
    an `order.dispatch_failed` event -- never left in RECEIVED/DISPATCHED
    limbo. FAILED (not BLOCKED) because every failure mode here is a bridge/
    infrastructure problem the plan's `OrderStatus.FAILED` docstring already
    covers ("decompose error, all subtasks failed, aggregation error");
    BLOCKED is reserved for an order genuinely waiting on a human gate,
    which a subprocess failure is not.
    """
    order = store().get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.RECEIVED:
        raise HTTPException(
            status_code=409,
            detail=f"Order {order_id} is '{order.status.value}', expected 'received'",
        )

    try:
        submission = kanban_bridge.submit_order_to_kanban(order)
    except KanbanBridgeError as exc:
        order.status = OrderStatus.FAILED
        order.updated_at = datetime.now(UTC)
        store().save_order(order)
        store().add_event(
            TaskEvent(
                task_id=order.id,
                kind="order.dispatch_failed",
                actor="kanban-bridge",
                payload={"error": str(exc)},
            )
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    bridge_link = store().save_bridge_link(order.id, submission.kanban_task_id, submission.board)
    order.status = OrderStatus.DISPATCHED
    order.updated_at = datetime.now(UTC)
    store().save_order(order)
    store().add_event(
        TaskEvent(
            task_id=order.id,
            kind="order.dispatched",
            actor="kanban-bridge",
            payload={"kanban_task_id": submission.kanban_task_id, "board": submission.board},
        )
    )
    return {**order.model_dump(mode="json"), "bridge_link": bridge_link}


@app.post("/api/bridge/kanban-events")
async def kanban_events(request: Request, x_starhome_signature: str | None = Header(default=None)):
    """K7 -- inbound half of the Kanban<->StarHome bridge. Target of the
    `starhome-bridge` user plugin (`~/.hermes/plugins/starhome-bridge/`,
    outside this repo -- see `bridge/inbound.py`'s module docstring for the
    full wire contract and the reasoning behind what this endpoint does and
    does not resolve).

    Signature verified over the RAW request body (not a re-serialized
    version of the parsed JSON, which could byte-differ from what the
    plugin actually signed) -- `await request.body()` before any parsing.
    An invalid or missing `X-StarHome-Signature` is the one failure mode
    that gets a non-200: every other "nothing to do" outcome (unknown
    kanban_task_id, already-terminal order/task, malformed-but-signed
    payload) is a normal 200 with a `status: "ignored"` body, per
    `handle_kanban_event`'s own docstring -- a signed request from hermes
    describing real board state is never itself an error.
    """
    body = await request.body()
    if not kanban_inbound.verify_signature(settings.starhome_bridge_hmac_secret, body, x_starhome_signature):
        raise HTTPException(status_code=401, detail="invalid or missing X-StarHome-Signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a JSON object")

    return await kanban_inbound.handle_kanban_event(
        engine=engine(),
        store=store(),
        execution_service=execution_service(),
        notifier=notification_service(),
        budget=budget(),
        artifacts_root=settings.artifact_path,
        payload=payload,
    )


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


_RAW_TO_STATE = {
    "pending": "pending",
    "running": "running",
    "completed": "done",
    "simulated": "done",
    "failed": "failed",
    "approval_required": "approval_required",
}


@app.post("/api/tasks/{task_id}/execute", status_code=202)
async def execute_task(task_id: str, executor_id: str | None = None):
    """K3: no longer runs the executor inline and blocks the request until it
    finishes (up to the full 24h timeout) -- enqueues onto `QueueService` and
    returns immediately. The task-existence check stays synchronous (still a
    404 for an unknown id) since that's a cheap, meaningful pre-check;
    everything past it (governance, executor dispatch, the actual run) now
    happens on the worker loop. Poll `GET /api/executions/{execution_id}`
    for progress."""
    if store().get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    execution_id = await queue_service().enqueue(task_id, executor_id)
    return {"execution_id": execution_id, "task_id": task_id, "status": "pending"}


@app.get("/api/executions/{execution_id}")
def get_execution(execution_id: str):
    row = store().get_execution(execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {**row, "state": _RAW_TO_STATE.get(row["status"], row["status"])}


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: str, request: TaskCompletion = TaskCompletion()):
    """K2 — manual close for tasks `ExecutionService`/`completion.py` left in
    REVIEW (MEDIUM/HIGH/CRITICAL risk; LOW risk auto-closes to DONE on its
    own). This is a plain human-in-the-loop close, not an approval grant --
    no auto-approval logic lives here, that is K12's job. A task not
    currently in REVIEW is refused with 409 rather than silently
    re-transitioned, since "complete" only makes sense as the next step
    after a run actually finished.
    """
    task = store().get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status != TaskStatus.REVIEW:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task_id} is '{task.status.value}', expected 'review'",
        )
    return engine().transition(task_id, TaskStatus.DONE, request.actor, {"reason": request.reason})


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
    """K11 -- mixes the real Obsidian vault (`settings.vault_path`,
    `~/StarHomeVault` on this host) with a best-effort graphify lookup
    (`settings.graphify_graph_path`); see `ContextBuilder`'s docstring for
    how the two sources combine and where a future gbrain adapter plugs
    in."""
    vault = MarkdownVault(settings.vault_path)
    builder = ContextBuilder(vault, KnowledgeGraph(vault), GraphifyAdapter(), settings.graphify_graph_path)
    return builder.build(q)


@app.get("/api/memory/candidates")
def list_memory_candidates(status: str | None = None):
    """K11 -- reader for Prometeo F3's `add_memory_candidate` (write-only
    until now). `status` filters on `candidate` (pending) / `approved` /
    `rejected`; omitted, returns all of them newest first."""
    return memory_candidates().list(status)


@app.get("/api/memory/candidates/{candidate_id}")
def get_memory_candidate(candidate_id: str):
    try:
        return memory_candidates().get(candidate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory candidate not found") from exc


@app.post("/api/memory/candidates/{candidate_id}/resolve")
def resolve_memory_candidate(candidate_id: str, request: MemoryCandidateResolution):
    """K11 -- the only path that promotes a memory candidate to the vault
    (see `MemoryCandidateService`/root `CLAUDE.md` rule 9). `decision` must
    be `"approved"` or `"rejected"`; an actor cannot approve its own
    candidate when the payload carries a `proposed_by` field, mirroring
    `ApprovalService`'s anti-self-approval rule."""
    try:
        return memory_candidates().resolve(candidate_id, request.decision, request.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Memory candidate not found") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
