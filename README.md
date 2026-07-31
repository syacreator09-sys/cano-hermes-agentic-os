# Cano Hermes Agentic OS

Autonomous, supervised personal agent operating system for Cano. It orchestrates Claude Code, Codex, economical API providers, specialist teams, Obsidian + Graphify Nexus, Agent Forge and external systems such as Factory V5. It is independent from Cano AI Command Center.

## Current foundation

- Persistent tasks and event timeline in SQLite.
- Lightweight Conductor and domain teams.
- Subscription-first multi-model router.
- Dry-run executors for Claude Code, Codex, Hermes Agent and OpenClaw.
- Agent and skill registries.
- Obsidian Markdown Nexus with graph and compact context builder.
- Agent/Skill Forge candidates.
- Governance: permissions, budgets and approvals.
- FastAPI dashboard and APIs.
- Docker, systemd, CI, validation and tests.

External providers and production side effects are disabled by default.

## Run

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
python scripts/validate.py
pytest
uvicorn cano_hermes.api.app:app --reload
```

Open `http://127.0.0.1:8000`.

## Demonstrate orchestration

```bash
python scripts/demo.py
hermes-cano task "Design an analytics agent" --domain forge
```

See `docs/ARCHITECTURE.md`, `CLAUDE.md`, `AGENTS.md`, `SECURITY.md`, and `ROADMAP.md`.
