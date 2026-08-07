from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HERMES_", extra="ignore")

    env: str = "development"
    # K12 (plan HERMES-KICKOFF): default changed dry_run -> supervised to
    # match the real systemd `starhome-os` unit, which has run with
    # `HERMES_EXECUTION_MODE=supervised` in its own `.env` since before K7
    # (see `tests/test_k7_kanban_events.py`'s
    # `test_synthesis_needing_approval_blocks_order_not_fails_it`, a
    # regression documented from a live 2026-08-06 demo run under that
    # exact mode) -- the code default was simply stale, not a deliberate
    # dry_run-by-default posture that changed here. `supervised` routes
    # every task through `PermissionEngine` as a `SENSITIVE_ACTIONS`
    # member (`ExecutionService.run` always evaluates the coarse label
    # `"production_write"`), so *everything* would need Cano's manual
    # approval without K12's other half: `governance/auto_approval.py`,
    # which lets only LOW-risk/$0/non-sensitive/office-allowed requests
    # resolve themselves. Tests that need `dry_run` specifically already
    # set `HERMES_EXECUTION_MODE=dry_run` (or pass the literal string to
    # `ExecutionService(...)` directly) rather than relying on this
    # default, so this change does not require touching them.
    execution_mode: str = "supervised"
    database_url: str = "sqlite:///storage/hermes.db"
    vault_path: Path = Path("vault")
    # K11 (plan HERMES-KICKOFF) -- default location of a graphify graph.json
    # export (`graphify update cano_hermes`, no LLM/API key needed for a
    # code-only corpus). Relative to cwd, matching `vault_path`'s own
    # convention. `ContextBuilder`/`nexus_context()` treat a missing file
    # here as "graphify was never run" and degrade to vault-only context --
    # this setting does not need to point at something that exists.
    graphify_graph_path: Path = Path("graphify-out/graph.json")
    agent_path: Path = Path("agents")
    skill_path: Path = Path("skills")
    artifact_path: Path = Path("storage/artifacts")
    worktree_path: Path = Path("storage/worktrees")
    # Git repository engineering-domain tasks get an isolated worktree
    # inside. Defaults to cwd (this repo, when the process runs from its
    # root) -- ExecutionService only activates worktree isolation when a
    # `repository` is actually configured, so this only takes effect for
    # the wiring in api/dependencies.py, not for tests that construct their
    # own ExecutionService without it.
    repository_root: Path = Path(".")
    forge_candidates_path: Path = Path("storage/forge/candidates")
    forge_sandbox_path: Path = Path("storage/forge/sandbox")
    max_concurrent_workers: int = Field(default=3, ge=1, le=12)
    default_daily_budget_usd: float = Field(default=5.0, ge=0)
    require_approval_for_paid_api: bool = True
    require_approval_for_writes: bool = True
    claude_command: str = "claude"
    codex_command: str = "codex"
    agent_command: str = "hermes"
    openclaw_command: str = "openclaw"
    # K4 (plan HERMES-KICKOFF, gap 6) -- Telegram Bot API credentials for
    # cano_hermes.notifications. Unprefixed (no HERMES_ prefix, unlike every
    # other field above): the token/chat id live in credential files owned
    # by other systems -- hermes-agent's own `.env` and the shared vault
    # (`~/.secrets/credenciales/credenciales/.env`) -- never in this repo's
    # source, only (optionally) in this repo's own untracked `.env`, which
    # already stores them unprefixed today and is loaded verbatim into the
    # `starhome-os` systemd unit via `EnvironmentFile=`. `validation_alias`
    # reads the bare name instead of the auto-derived `HERMES_TELEGRAM_*`,
    # so no second, StarHome-specific env var is needed anywhere upstream.
    # `TELEGRAM_CHAT_ID` (not hermes-agent's `TELEGRAM_HOME_CHANNEL`) was
    # picked because it's the name this repo's own `.env` already uses --
    # both names hold the identical chat id in practice.
    telegram_bot_token: str = Field(default="", validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", validation_alias="TELEGRAM_CHAT_ID")
    # K7 (plan HERMES-KICKOFF, gap 2 continuation) -- shared secret between
    # this repo and the `starhome-bridge` user plugin living in
    # `~/.hermes/plugins/starhome-bridge/` (outside this repo, CERO changes
    # to hermes-agent itself). The plugin signs every `POST
    # /api/bridge/kanban-events` body with HMAC-SHA256 using the exact same
    # value, read from `~/.hermes/.env`. Unprefixed (no `HERMES_` prefix),
    # matching the `telegram_bot_token`/`telegram_chat_id` pattern above --
    # both processes run on the same machine, so both read the identical
    # value from their own untracked `.env` rather than sharing a filesystem
    # path. Empty by default: `inbound.verify_signature` treats an unset
    # secret as "reject everything" (fail closed), never "skip verification".
    starhome_bridge_hmac_secret: str = Field(
        default="", validation_alias="STARHOME_BRIDGE_HMAC_SECRET"
    )
    # K9 (plan HERMES-KICKOFF, gaps 12/13) -- hard cap on simultaneously
    # active Docker offices (cano_hermes/bridge/office_launcher.py). The
    # whole Docker infra budget (16GB/3CPU) assumes at most 2 offices up at
    # once alongside Baserow + the F3 sandbox.
    offices_max_active: int = Field(default=2, ge=1, le=5)

    def ensure_directories(self) -> None:
        for path in (
            self.vault_path,
            self.agent_path,
            self.skill_path,
            self.artifact_path,
            self.worktree_path,
            self.forge_candidates_path,
            self.forge_sandbox_path,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
