from __future__ import annotations

import argparse
import json

from cano_hermes.config import settings
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore
from cano_hermes.domain.models import TaskCreate


def build_engine() -> TaskEngine:
    registry = AgentRegistry(settings.agent_path)
    registry.load()
    return TaskEngine(SQLiteStore(settings.database_url), Conductor(registry, ModelRouter()))


def main() -> None:
    parser = argparse.ArgumentParser(prog="hermes-cano")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("task")
    create.add_argument("objective")
    create.add_argument("--title", default="CLI task")
    create.add_argument("--domain", default="general")
    sub.add_parser("status")
    args = parser.parse_args()
    engine = build_engine()
    if args.command == "task":
        task = engine.create(TaskCreate(title=args.title, objective=args.objective, domain=args.domain))
        print(engine.plan(task.id).model_dump_json(indent=2))
    else:
        store = engine.store
        print(json.dumps({"tasks": len(store.list_tasks()), "mode": settings.execution_mode}, indent=2))


if __name__ == "__main__":
    main()
