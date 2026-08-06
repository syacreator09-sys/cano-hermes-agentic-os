from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cano_hermes.storage.sqlite import SQLiteStore

logger = logging.getLogger(__name__)


@dataclass
class BudgetLedger:
    daily_limit_usd: float
    spent_usd: float = 0.0

    def can_spend(self, amount: float) -> bool:
        return amount >= 0 and self.spent_usd + amount <= self.daily_limit_usd

    def record(self, amount: float, force: bool = False) -> None:
        """Record spend. `force=True` reconciles cost already incurred (e.g.
        a usage-file report) — it must never raise, because the money is
        already spent whether or not it fit the plan; it can only push the
        ledger over budget so the *next* request gets gated."""
        if not force and not self.can_spend(amount):
            raise ValueError("Budget limit exceeded")
        self.spent_usd += amount

    @property
    def remaining_usd(self) -> float:
        return self.daily_limit_usd - self.spent_usd


class BudgetService:
    """Persists one `BudgetLedger` per UTC day in sqlite and reconciles it
    against the `--usage-file` JSON reports hermes-agent one-shot runs write.

    Plan Prometeo F3, task 2: `default_daily_budget_usd` (cano_hermes.config
    .Settings) was declared but never read anywhere; this is the reader.
    Sits in `governance/` (not `orchestration/`) so PermissionEngine-adjacent
    code can depend on it without ExecutionService pulling in storage
    directly — ExecutionService composes BudgetService + ApprovalService,
    it doesn't reimplement either.

    Usage-file location: `HermesAgentExecutor.build_args` (runtimes/
    hermes_agent.py) writes each run's report to
    `storage/workspaces/<task_id>/<executor_id>/usage-<task_id>.json`, using
    the exact schema hermes-agent's own `_write_usage_file` produces
    (hermes-agent/hermes_cli/oneshot.py) — the cost field is
    `estimated_cost_usd`. `ingest_workspace` walks that tree; other
    executors that aren't hermes-agent simply never produce a usage file, so
    they cost nothing against the ledger until they do.
    """

    USAGE_COST_FIELDS = ("estimated_cost_usd", "cost_usd", "total_cost_usd")

    def __init__(
        self,
        store: "SQLiteStore",
        daily_limit_usd: float | None = None,
    ) -> None:
        self.store = store
        if daily_limit_usd is None:
            from cano_hermes.config import settings

            daily_limit_usd = settings.default_daily_budget_usd
        self.daily_limit_usd = daily_limit_usd

    @staticmethod
    def today() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def ledger_for(self, day: str | None = None) -> BudgetLedger:
        day = day or self.today()
        ledger = self.store.get_budget_state(day)
        if ledger is None:
            ledger = BudgetLedger(daily_limit_usd=self.daily_limit_usd)
            self.store.save_budget_state(day, ledger)
        return ledger

    def can_spend(self, amount: float, day: str | None = None) -> bool:
        return self.ledger_for(day).can_spend(amount)

    def record_spend(self, amount: float, day: str | None = None, force: bool = False) -> BudgetLedger:
        day = day or self.today()
        ledger = self.ledger_for(day)
        ledger.record(amount, force=force)
        self.store.save_budget_state(day, ledger)
        return ledger

    def ingest_usage_file(self, path: Path | str, day: str | None = None) -> float:
        """Read one hermes-agent usage-file and record its cost. Tolerant of
        a missing file, invalid JSON, or an absent cost field — those all
        record nothing rather than raise, because a broken usage report must
        never block the task it describes (mirrors hermes-agent's own
        "write even on failure" contract)."""
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read usage file %s: %s", path, exc)
            return 0.0
        amount = 0.0
        for field in self.USAGE_COST_FIELDS:
            value = data.get(field)
            if isinstance(value, (int, float)):
                amount = float(value)
                break
        if amount > 0:
            self.record_spend(amount, day, force=True)
        return amount

    def ingest_workspace(self, workspace_root: Path | str = "storage/workspaces", day: str | None = None) -> float:
        """Bulk-ingest every `usage-*.json` under `workspace_root`.

        Not idempotent: it has no memory of which files it already recorded,
        so calling it twice double-counts. It exists for one-off
        reconciliation (e.g. a startup/admin sweep after a restart), not for
        the per-run hot path — `ExecutionService.run` instead ingests only
        the single usage file its own execution just produced, by exact
        path, which is naturally exactly-once. Returns the total newly
        recorded (0.0 if the tree doesn't exist yet, e.g. in dry-run mode
        before any hermes-agent run has produced a report)."""
        root = Path(workspace_root)
        if not root.exists():
            return 0.0
        total = 0.0
        for usage_file in sorted(root.glob("**/usage-*.json")):
            total += self.ingest_usage_file(usage_file, day)
        return total
