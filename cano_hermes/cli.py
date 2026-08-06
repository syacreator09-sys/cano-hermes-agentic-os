from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

from cano_hermes.config import settings
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore
from cano_hermes.domain.models import TaskCreate

# K8 (plan HERMES-KICKOFF) -- base URL the `order` subcommand group talks
# to. HTTP, not direct SQLiteStore/service calls: `order submit`/`status`
# have no simpler path than the endpoints K5/K6 already expose
# (`POST /api/orders`, `GET /api/orders/{id}`), and `order list` gets the
# same treatment via the small `GET /api/orders` endpoint added alongside
# this CLI -- so all three verbs go through one code path (easy to test by
# mocking `httpx`, and it exercises the exact same API surface the
# `starhome-orders` Telegram skill uses, instead of a second, divergent way
# to create an order). Unprefixed env var (`STARHOME_API_BASE`, no
# `HERMES_` prefix) matching the `TELEGRAM_BOT_TOKEN`/
# `STARHOME_BRIDGE_HMAC_SECRET` convention in `config.py` for values that
# are about *where a sibling process lives* rather than this process's own
# settings.
_DEFAULT_STARHOME_BASE_URL = "http://127.0.0.1:8787"


def _starhome_base_url() -> str:
    return os.environ.get("STARHOME_API_BASE", _DEFAULT_STARHOME_BASE_URL)


def order_submit(objective: str, source: str = "cli", budget_usd: float | None = None) -> dict:
    """`POST /api/orders`. `budget_usd`, when given, is sent as
    `budget.max_cost_usd`; omitted entirely otherwise so the server's own
    `Budget()` default applies (matches `OrderCreate.budget`'s
    `default_factory`)."""
    payload: dict = {"objective": objective, "source": source}
    if budget_usd is not None:
        payload["budget"] = {"max_cost_usd": budget_usd}
    response = httpx.post(f"{_starhome_base_url()}/api/orders", json=payload, timeout=30.0)
    response.raise_for_status()
    return response.json()


def order_status(order_id: str) -> dict:
    response = httpx.get(f"{_starhome_base_url()}/api/orders/{order_id}", timeout=30.0)
    response.raise_for_status()
    return response.json()


def order_list() -> list:
    response = httpx.get(f"{_starhome_base_url()}/api/orders", timeout=30.0)
    response.raise_for_status()
    return response.json()


def _run_order(args: argparse.Namespace) -> None:
    if args.order_command == "submit":
        result = order_submit(args.objective, source=args.source, budget_usd=args.budget)
    elif args.order_command == "status":
        result = order_status(args.order_id)
    elif args.order_command == "list":
        result = order_list()
    else:  # pragma: no cover -- argparse `required=True` already guards this
        raise ValueError(f"unknown order subcommand: {args.order_command}")
    print(json.dumps(result, indent=2, default=str))


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

    order = sub.add_parser("order", help="K8 -- submit/track orders via the running StarHome API (POST /api/orders et al)")
    order_sub = order.add_subparsers(dest="order_command", required=True)

    order_submit_p = order_sub.add_parser("submit", help="POST /api/orders")
    order_submit_p.add_argument("objective")
    order_submit_p.add_argument("--source", default="cli", choices=["telegram", "cli", "api"])
    order_submit_p.add_argument("--budget", type=float, default=None, help="max_cost_usd; omit for the server default")

    order_status_p = order_sub.add_parser("status", help="GET /api/orders/{id}")
    order_status_p.add_argument("order_id")

    order_sub.add_parser("list", help="GET /api/orders")

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

    if args.command == "order":
        _run_order(args)
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
