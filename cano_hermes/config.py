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
