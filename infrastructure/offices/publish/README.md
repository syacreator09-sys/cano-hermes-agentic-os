# office-publish — design only (F11)

Not run end-to-end in F11. Built and startable, but the pipeline step is a
stub — see `task.sh`. This is the office with the hardest constraint in the
whole plan: **it must never be able to publish for real.**

## Intended job

Chain: `dedup → release guard → draft → dry-run → gate humano → dispatch → ledger`.

- **dedup**: consult the real mechanism F9 found (`upload_log_ugc.db`
  SQLite in command-center's `ugc-affiliate` office, key
  `canal+slug+fecha`) — read-only.
- **release guard / draft / dry-run**: produce a draft artifact, never a
  live post.
- **gate humano**: any transition from draft to real dispatch is a
  `SENSITIVE_ACTION` (`cano_hermes/governance/policy.py`:
  `publish`/`send_external_message`) and requires a resolved
  `ApprovalRequest` (F3) from an actor different from whoever requested it
  — `ApprovalService.resolve` enforces this in code, not just by convention.
- **dispatch**: happens *outside* this container, driven by StarHome's own
  execution service after approval — never triggered by office-publish
  itself.
- **ledger**: record of what was actually dispatched, for the dedup step's
  next run.

## Why not run end-to-end

The real chain depends on command-center's `ugc-affiliate` uploader
(`scripts/uploaders/uploader.py`, read-only per `command-center-contract`)
and on F3's `ApprovalService` being reachable from inside a container cycle
— wiring that reach-through safely (container → StarHome API →
ApprovalService, without giving the container the API's own credentials)
is real design work that F11's time budget didn't leave room for after
getting office-analytics and office-ugc genuinely running. Scaffolding a
fake approval path here would be worse than not building it.

## Credentials — the allowlist that matters most in this plan

Tier 0 only (`KIMI_API_KEY`, `KIMI_BASE_URL`, `NVIDIA_NIM_API_KEY`) for the
hermes `--oneshot` supervisor that drafts/narrates. **Nothing else.**
Specifically **never** present in this container's environment: any
Upload-post JWT/token, TikTok/Meta/YouTube API credentials, or any other
`*_TOKEN`/`*_API_KEY` tied to a real publish action. Verified by inspecting
`docker compose config` for the `office-publish` service (see F11 report,
allowlist confirmation section) — variable *names* only, no values printed.

## Resource limits

`mem_limit: 1g`, `cpus: 0.2` (see `infrastructure/offices/docker-compose.yml`).
