"""K6 (plan HERMES-KICKOFF, gap 2) — StarHome -> Kanban bridge (outbound half).

Turns an approved `OrderRecord` into one task on hermes-agent's Kanban bus,
on a board dedicated to StarHome (`starhome`) so it never mixes with Cano's
personal board (`default`) or any other board a human might be using
interactively.

Confirmed CLI syntax (run live on this machine, hermes-agent v0.20.0,
2026-08-06 — `hermes kanban --help` / `hermes kanban create --help` /
`hermes kanban boards --help`, per the K6 task instructions):

    hermes kanban boards create <slug> [--name ...]      # idempotent, see ensure_board()
    hermes kanban --board <slug> create <title>
        --body <text>
        --triage
        --idempotency-key <key>
        --priority <int>
        --created-by <name>
        --json

`--board` is a flag of the `kanban` subcommand itself, placed *before* the
action word (`create`), not after it — `hermes kanban --board starhome
create ...`, not `hermes kanban create --board starhome ...`. `create` is
the verb; there is no `add` subcommand (an earlier draft of this bridge
assumed one — `hermes kanban --help` lists `create` and does not accept
`add`).

Design decisions worth recording:

- **Always `--triage`, never a separate decompose call.** The plan's open
  question was whether auto-decompose needs an explicit second step. It
  does not: `kanban.auto_decompose` defaults to `True` (confirmed in
  hermes-agent's `hermes_cli/config_defaults.py`), so the dispatcher itself
  (gateway-embedded by default, `kanban.dispatch_in_gateway: True`) picks up
  every triage-column task on its own tick and either fans it out into
  child tasks or falls back to specify-style single-task promotion when the
  work doesn't benefit from fan-out (`hermes kanban decompose --help`).
  StarHome's job is only to land the task in triage with a good title/body;
  hermes-agent's own planner (`kanban_decompose.py`) owns everything past
  that point, per the plan's explicit call to not build a second planner in
  Conductor. A consequence: an order only actually starts moving once
  hermes-agent's dispatcher is alive (gateway running, or someone runs
  `hermes kanban dispatch`) — this bridge cannot make that happen and does
  not try to.

- **Idempotency key = `order.id`.** Verified live: creating a task with an
  `--idempotency-key` that already exists on a non-archived task returns
  the *existing* task's id instead of creating a duplicate — so a retried
  `submit_order_to_kanban()` call (crash-and-retry, duplicate webhook, etc.)
  is always safe.

- **Priority derives from `order.budget.max_cost_usd` only.** `OrderRecord`
  (K5) has no `risk` field — only `budget` — so "riesgo/budget" from the
  plan text collapses to budget alone here. Heuristic: the more Cano is
  willing to spend on an order, the more he wants it to jump the queue, so
  `priority = round(budget.max_cost_usd)`, clamped to `[0, 10]` so one
  high-budget order can't starve everything else forever (kanban's own
  dispatcher picks highest-priority-first, ties by oldest `created_at` —
  confirmed in `kanban_db.py`'s `ORDER BY priority DESC, created_at ASC`).
  The default `Budget.max_cost_usd == 0.0` maps to priority 0, kanban's own
  default — an order that sets no budget doesn't jump ahead of anything.

- **No `--skill`/`--model`/`--provider` on the parent task.** The task
  itself never runs a worker beyond whatever profile claims it (it sits in
  triage, or in ready-for-<profile>, until a human/decomposer/office
  worker acts on it) — those flags only make sense on the tasks a future
  decomposer creates, routed to specialist profiles "by description" on
  its own.

- **T10 (plan POTENCIA, 2026-08-07): `order.domain` -> `--assignee`.**
  `OrderRecord` still has no *team* the way `TaskRecord` does (it hasn't
  been through `Conductor.assign()`), but callers can now pass an explicit
  `domain` hint (`OrderCreate.domain`) resolved through the exact same
  `domain -> team -> kanban_profile` table `Conductor.assign()` uses
  (`conductor.kanban_profile_for_domain`, fixed in P0 so every value is a
  real `offices/<profile>/office.yaml`, not a `team-*` placeholder). When
  it resolves to a real K9 office profile, the task is created with
  `--assignee <profile>` and WITHOUT `--triage` -- `kanban_db.py`'s
  `create_task` puts a non-triage task straight into `status=ready`
  (confirmed reading its source), which is exactly what
  `infrastructure/offices/common/entrypoint.sh`'s worker loop polls for
  (`kanban list --assignee "$OFFICE_PROFILE" --status ready`). No domain,
  an unknown domain, or a domain that resolves to no office (engineering,
  governance, ...) all fall back to the original behavior: `--triage`, no
  assignee, a human/future-decomposer routes it.

Error handling: every failure mode below (hermes CLI missing, non-zero
exit, timeout, unparseable `--json` output, missing `id` in the response)
raises `KanbanBridgeError` with the captured stderr/output. The caller
(`api/app.py`'s dispatch endpoint) is expected to catch it and transition
the order to FAILED with `str(exc)` as the recorded reason — an order must
never be left in DISPATCHED-but-nothing-happened limbo.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass

from cano_hermes.config import settings
from cano_hermes.domain.models import OrderRecord
from cano_hermes.runtimes.subprocess_executor import SECRET_NAME_PATTERN

logger = logging.getLogger(__name__)

KANBAN_BOARD = "starhome"
TITLE_MAX_CHARS = 120
PRIORITY_MIN = 0
PRIORITY_MAX = 10
SUBPROCESS_TIMEOUT_SECONDS = 30.0


class KanbanBridgeError(RuntimeError):
    """The `hermes kanban` subprocess failed, timed out, or returned
    something this bridge couldn't parse. Always carries a human-readable
    message (subprocess stderr when available) suitable for storing
    verbatim as the reason on a FAILED `OrderRecord`."""


@dataclass(frozen=True)
class BridgeSubmission:
    """Result of a successful `submit_order_to_kanban()` call — enough for
    the caller to persist a `bridge_links` row and move the order forward."""

    kanban_task_id: str
    board: str
    command: list[str]


def _order_title(order: OrderRecord) -> str:
    """First line of the objective, truncated to `TITLE_MAX_CHARS`. Falls
    back to the order id for the pathological case of an all-whitespace
    objective (shouldn't happen — `OrderCreate.objective` has
    `min_length=3` — but a title is required by the CLI, so this never
    passes an empty string to it)."""
    stripped = order.objective.strip()
    first_line = stripped.splitlines()[0].strip() if stripped else ""
    if not first_line:
        return order.id
    if len(first_line) <= TITLE_MAX_CHARS:
        return first_line
    return first_line[: TITLE_MAX_CHARS - 1].rstrip() + "…"


def _order_priority(order: OrderRecord) -> int:
    """See module docstring — derived from `budget.max_cost_usd` alone,
    clamped to kanban's own tiebreak-friendly range."""
    raw = round(order.budget.max_cost_usd)
    return max(PRIORITY_MIN, min(PRIORITY_MAX, raw))


def _hermes_command() -> str:
    return settings.agent_command


def _kanban_subprocess_env() -> dict[str, str]:
    """K12 (plan HERMES-KICKOFF, Seguridad v2) -- "aislamiento por tier
    extendido a spawns kanban". Before this, `_run_hermes` called
    `subprocess.run(args, ...)` with no `env=` at all, so every `hermes
    kanban ...` CLI call StarHome shells out to (board create / task
    create -- see the two call sites below) silently inherited this
    process's *entire* environment, including every provider credential
    StarHome itself holds across every tier (`ANTHROPIC_API_KEY`,
    `OPENAI_API_KEY`, `KIMI_API_KEY`, Telegram/HMAC secrets, ...) --
    unlike `runtimes/subprocess_executor.py`'s executors, which strip
    every secret-shaped variable by default and restore only a per-
    executor allowlist (`EXECUTOR_SECRET_ALLOWLIST`).

    `hermes kanban boards create`/`hermes kanban --board ... create` are
    pure board-state writes (hermes-agent's sqlite kanban.db) -- they
    never call an LLM provider, so they need exactly zero of those
    credentials, the same "zero secrets, ever" tier
    `EXECUTOR_SECRET_ALLOWLIST` already gives `container-sandbox`/
    `openclaw`. Reusing `SECRET_NAME_PATTERN` here (not duplicating its
    regex) keeps this in sync with any future change to what counts as
    "secret-shaped" there."""
    return {k: v for k, v in os.environ.items() if not SECRET_NAME_PATTERN.search(k)}


def _run_hermes(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_kanban_subprocess_env(),
        )
    except FileNotFoundError as exc:
        raise KanbanBridgeError(
            f"comando '{args[0]}' no encontrado -- ¿hermes-agent está instalado en esta máquina?"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise KanbanBridgeError(
            f"'{' '.join(args)}' excedió el timeout de {timeout}s"
        ) from exc
    except OSError as exc:
        raise KanbanBridgeError(f"'{' '.join(args)}' falló al lanzarse: {exc}") from exc


def ensure_board(board: str = KANBAN_BOARD, *, command: str | None = None,
                  timeout: float = SUBPROCESS_TIMEOUT_SECONDS) -> None:
    """`hermes kanban boards create <slug>` is idempotent by design —
    verified live: re-running it against an already-existing board prints
    "Board '<slug>' already exists." and still exits 0. So this can be
    called unconditionally before every submission with no exists-check,
    at the cost of one cheap extra subprocess call per order."""
    hermes = command or _hermes_command()
    args = [hermes, "kanban", "boards", "create", board, "--name", board.capitalize()]
    result = _run_hermes(args, timeout=timeout)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "(sin stderr)"
        raise KanbanBridgeError(
            f"no se pudo asegurar el board de kanban '{board}' "
            f"(código {result.returncode}): {stderr}"
        )


def submit_order_to_kanban(
    order: OrderRecord,
    *,
    board: str = KANBAN_BOARD,
    command: str | None = None,
    timeout: float = SUBPROCESS_TIMEOUT_SECONDS,
) -> BridgeSubmission:
    """Create (or, via idempotency, resolve) the Kanban triage task for
    `order` on `board` and return its id.

    Raises `KanbanBridgeError` on any failure — never returns a partial or
    sentinel result. Callers must catch it and fail the order explicitly;
    see the module docstring's "Error handling" section.
    """
    hermes = command or _hermes_command()
    ensure_board(board, command=hermes, timeout=timeout)

    # T10: resolve a real K9 office profile from the order's optional
    # domain hint. `kanban_profile_for_domain` returns None for no domain,
    # an unknown domain, or a domain whose team deliberately has no office
    # (engineering, governance, ...) -- every one of those keeps the
    # original triage-only behavior.
    from cano_hermes.orchestration.conductor import kanban_profile_for_domain

    profile = kanban_profile_for_domain(order.domain) if order.domain else None

    args = [
        hermes,
        "kanban",
        "--board",
        board,
        "create",
        _order_title(order),
        "--body",
        order.objective,
        "--idempotency-key",
        order.id,
        "--priority",
        str(_order_priority(order)),
        "--created-by",
        "starhome-kanban-bridge",
        "--json",
    ]
    if profile:
        args += ["--assignee", profile]
    else:
        args += ["--triage"]
    result = _run_hermes(args, timeout=timeout)

    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "(sin stderr)"
        raise KanbanBridgeError(
            f"'{hermes} kanban create' salió con código {result.returncode} "
            f"para la orden {order.id}: {stderr}"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise KanbanBridgeError(
            f"'{hermes} kanban create --json' devolvió salida no-JSON para la "
            f"orden {order.id}: {result.stdout[:500]!r}"
        ) from exc

    kanban_task_id = payload.get("id") if isinstance(payload, dict) else None
    if not kanban_task_id:
        raise KanbanBridgeError(
            f"respuesta de 'hermes kanban create --json' sin campo 'id' para "
            f"la orden {order.id}: {payload}"
        )

    logger.info(
        "orden %s despachada a kanban board '%s' como tarea %s",
        order.id,
        board,
        kanban_task_id,
    )
    return BridgeSubmission(kanban_task_id=kanban_task_id, board=board, command=args)
