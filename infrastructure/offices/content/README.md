# office-content — design only (F11)

Not run end-to-end in F11. Built (`docker compose --profile content build`
works) and startable, but the pipeline step is a stub — see `task.sh`.

## Intended job

Producción factory-v5 (reels, carruseles, largos), invocada por contrato vía
`skills/factory-v5-contract/SKILL.md`:

```bash
cd ~/repos/factory-ia-channel-v5
source .venv/bin/activate
python scripts/factory.py <comando>
```

Read-only/plan commands (`provider-health`, `validate-yaml`, `route`,
`compute-route`, `asset-recommend`, `list-*`, `*-status`, `*-doctor`,
`secure-config-audit`) would run directly from this container. Anything in
`SENSITIVE_ACTIONS` (real `remotion` render, `kie`, `upload-post-dry-run`
without the dry-run flag, `campaign-command` execution,
`editorial-explainer-render`) requires a real `ApprovalRequest` resolved by
a human outside this container — this office is never allowed to approve
its own request (`ApprovalService.resolve`, F3).

## Why not run end-to-end

`skills/factory-v5-contract/SKILL.md` documents a known, standing gap:
`runtime/stage-handlers.yaml` does not exist in the `factory-ia-channel-v5`
checkout on this machine (confirmed by `find` over the repo) — it's a
pending manual copy from the OMEN machine. Any `factory.py` command that
depends on the stage/handler pipeline fails or is incomplete until that
file is copied over. Fabricating a synthetic `stage-handlers.yaml` here
would mean inventing behavior of an external, by-contract-only system,
which both this skill and the root `CLAUDE.md` ("Nunca absorber
factory-ia-channel-v5") explicitly forbid.

## Volumes (when run)

- `~/repos/factory-ia-channel-v5` → `/home/cano/repos/factory-ia-channel-v5`
  (`:ro`) — read-only, by contract.
- `~/repos/hermes-agent` + `~/.local/share/uv/python` (`:ro`) — the hermes
  `--oneshot` supervisor (see `infrastructure/offices/common/`).

## Credentials

Tier 0 only (`KIMI_API_KEY`, `KIMI_BASE_URL`, `NVIDIA_NIM_API_KEY`) for the
hermes supervisor. Nothing from factory-v5's own `.env` is injected into
this container — factory.py, when it does run for real, reads its own
`.env` on its own host-side invocation path (per `factory-v5-contract`),
not through this office's environment.

## Resource limits

`mem_limit: 1g`, `cpus: 0.2` (see `infrastructure/offices/docker-compose.yml`).
