from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HERMES_", extra="ignore")

    env: str = "development"
    execution_mode: str = "dry_run"
    database_url: str = "sqlite:///storage/hermes.db"
    vault_path: Path = Path("vault")
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
