from __future__ import annotations

import argparse
import json
from pathlib import Path

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


def build_forge_pipeline():
    from cano_hermes.forge.pipeline import ForgePipeline
    from cano_hermes.governance.approvals import ApprovalService
    from cano_hermes.governance.budget import BudgetService

    store = SQLiteStore(settings.database_url)
    return ForgePipeline(
        agents_root=settings.agent_path,
        skills_root=settings.skill_path,
        candidates_root=settings.forge_candidates_path,
        sandbox_workspace_root=settings.forge_sandbox_path,
        approvals=ApprovalService(store),
        budget=BudgetService(store),
    )


def _load_definition(path: str) -> dict:
    import yaml

    text = Path(path).read_text(encoding="utf-8")
    if path.endswith((".yaml", ".yml")):
        return yaml.safe_load(text)
    return json.loads(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hermes-cano")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("task")
    create.add_argument("objective")
    create.add_argument("--title", default="CLI task")
    create.add_argument("--domain", default="general")

    sub.add_parser("status")

    forge = sub.add_parser("forge", help="Plan Prometeo F4 — candidate/sandbox/review/approval/promotion pipeline")
    forge_sub = forge.add_subparsers(dest="forge_command", required=True)

    propose = forge_sub.add_parser("propose", help="propose a candidate and run it through sandbox + cross-review + approval request")
    propose.add_argument("kind", choices=["agent", "skill"])
    propose.add_argument("definition_file", help="path to a YAML/JSON candidate definition")
    propose.add_argument("--requested-by", default="cli")
    propose.add_argument("--canal", default="engineering")
    propose.add_argument("--motivo", default=None)
    propose.add_argument("--costo-estimado-usd", type=float, default=0.0)

    status = forge_sub.add_parser("status", help="show a candidate's current pipeline stage and results")
    status.add_argument("candidate_id")

    promote = forge_sub.add_parser("promote", help="materialize an already-approved candidate into production")
    promote.add_argument("candidate_id")

    forge_sub.add_parser("list", help="list all known forge candidates")

    return parser


def _run_forge(args: argparse.Namespace) -> None:
    pipeline = build_forge_pipeline()
    if args.forge_command == "propose":
        definition = _load_definition(args.definition_file)
        candidate = pipeline.submit(
            args.kind,
            definition,
            requested_by=args.requested_by,
            canal=args.canal,
            motivo=args.motivo,
            costo_estimado_usd=args.costo_estimado_usd,
        )
        print(candidate.model_dump_json(indent=2))
    elif args.forge_command == "status":
        print(pipeline.status(args.candidate_id).model_dump_json(indent=2))
    elif args.forge_command == "promote":
        print(pipeline.promote(args.candidate_id).model_dump_json(indent=2))
    elif args.forge_command == "list":
        candidates = [c.model_dump(mode="json") for c in pipeline.list_candidates()]
        print(json.dumps(candidates, indent=2, default=str))


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "forge":
        _run_forge(args)
        return

    engine = build_engine()
    if args.command == "task":
        task = engine.create(TaskCreate(title=args.title, objective=args.objective, domain=args.domain))
        print(engine.plan(task.id).model_dump_json(indent=2))
    else:
        store = engine.store
        print(json.dumps({"tasks": len(store.list_tasks()), "mode": settings.execution_mode}, indent=2))


if __name__ == "__main__":
    main()
