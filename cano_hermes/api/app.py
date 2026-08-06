from __future__ import annotations

from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from cano_hermes import __version__
from cano_hermes.config import settings
from cano_hermes.domain.models import TaskCreate
from cano_hermes.nexus.context import ContextBuilder
from cano_hermes.nexus.graph import KnowledgeGraph
from cano_hermes.nexus.markdown import MarkdownVault
from .dependencies import approvals, engine, execution_service, registry, store


class ApprovalResolution(BaseModel):
    approved: bool
    actor: str


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


@app.get("/api/nexus/search")
def nexus_search(q: str):
    return MarkdownVault(settings.vault_path).search(q)


@app.get("/api/nexus/context")
def nexus_context(q: str):
    vault = MarkdownVault(settings.vault_path)
    return ContextBuilder(vault, KnowledgeGraph(vault)).build(q)
