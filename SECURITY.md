# Security Summary

- Safe mode is the default.
- No secrets are committed.
- Paid calls, publication, deployment, external messaging and destructive operations require approval.
- Worker execution is path-scoped and timeout-bound.
- Imported agents, skills and MCP servers begin in quarantine.
- Docker workers run rootless and never receive `/var/run/docker.sock`.
- Claude Code and Codex use separate worktrees and write locks.
- Memory writes are proposed as candidates and reviewed before promotion.

Full policy: `docs/SECURITY.md`.
