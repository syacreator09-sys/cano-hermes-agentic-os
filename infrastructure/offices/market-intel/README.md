# office-market-intel — built for real (K9)

Design was frozen at `docs/MARKET_INTEL_OFFICE_DESIGN.md` (Prometeo F14,
design-only pass). K9 (plan HERMES-KICKOFF) builds the container for real,
following the same pattern as the other 4 offices.

## What actually runs (K9 scope)

`task.sh` reads three read-only sources and writes one local synthesis file
to `/office/output/market-intel-daily-<ts>.md`:

1. **amazon-fba-product-hunter** (`:ro`) — reads the latest real
   `reports/*.md` already on disk (produced by `scorer_agent.py` on its own
   host-side run; this office does not re-score, it reads results).
2. **cano-investment-intelligence** (`:ro`) — reads the latest
   `docs/reports/*.md`. The live `/v1/council/offline` API is **not**
   started from this container — F14 found that repo's own
   `docker-compose.yml` has no `mem_limit`/`cpus`/`profiles` yet, so
   standing it up stays deferred (see design doc sec. 6).
3. office-ugc's trend signal is intentionally **not** duplicated here — it
   already lives in `office-ugc` (`RAPIDAPI_KEY`/`APIFY_API_KEY`).

## What does NOT run yet (documented gate, not faked)

Design doc sec. 2 rule 1 (FBA score ≥70 + active trend → new row in
Baserow's `productos_ugc`) needs a `BASEROW_API_TOKEN` this office is not
allowlisted for. `task.sh` prints that this step is skipped rather than
inventing a Baserow write.

## Hard rule (inherited, never relaxed)

CERO trading real, CERO compra real, CERO credencial de broker
(`ALPACA_*`/`IBKR_*`/`BINANCE_*` or equivalent) anywhere in this container.
Verify with `docker compose config` — only `KIMI_API_KEY`/`KIMI_BASE_URL`
(tier-0, for the `hermes --oneshot` supervisor) ever appear for this
service.

## Kanban profile

Serves `hermes-market-intel` (new `office.yaml`, isolation: docker) on
board `starhome`, same worker-loop pattern as the other 4 offices (K9
`entrypoint.sh`, `WORKER_MODE=kanban`).

## Volumes

- `~/repos/amazon-fba-product-hunter` → same path, `:ro`
- `~/repos/cano-investment-intelligence` → same path, `:ro`
- `~/repos/hermes-agent` + uv python (`:ro`) — the hermes `--oneshot`
  supervisor, and the scoped kanban board mount (see
  `infrastructure/offices/common/entrypoint.sh`).

## Resource limits

`mem_limit: 1g`, `cpus: 0.2` — same ceiling as `office-analytics`, the
lightest of the original 4 (see K9 report for the full budget table).
