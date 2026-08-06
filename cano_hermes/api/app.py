from __future__ import annotations

from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cano_hermes import __version__
from cano_hermes.config import settings
from cano_hermes.domain.models import TaskCreate
from cano_hermes.forge.duplication import DuplicateCandidateError
from cano_hermes.nexus.context import ContextBuilder
from cano_hermes.nexus.graph import KnowledgeGraph
from cano_hermes.nexus.markdown import MarkdownVault
from .dependencies import approvals, engine, execution_service, forge_pipeline, registry, store


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
