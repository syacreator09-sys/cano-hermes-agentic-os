from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cano_hermes.domain.models import TaskCreate
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore

with tempfile.TemporaryDirectory() as directory:
    engine = TaskEngine(
        SQLiteStore(f"sqlite:///{directory}/demo.db"),
        Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()),
    )
    task = engine.create(
        TaskCreate(
            title="Create content agent",
            objective="Design and test an agent that audits channel metrics",
            domain="forge",
        )
    )
    print(engine.plan(task.id).model_dump_json(indent=2))
