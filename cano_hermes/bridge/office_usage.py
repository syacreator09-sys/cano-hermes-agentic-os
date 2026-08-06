"""K9 (plan HERMES-KICKOFF, gap in "usage de oficinas -> presupuesto real").

Docker offices write `usage-*.json` files (hermes-agent's own
`--usage-file` schema, `estimated_cost_usd` field -- identical shape to
what `HermesAgentExecutor` already produces for native tasks, see K1)
under `infrastructure/offices/data/<office>/output/` on the host (that
directory is each office's `/office/output:rw` bind mount, per
`infrastructure/offices/docker-compose.yml`).

`BudgetService.ingest_workspace(workspace_root)` (governance/budget.py, K1)
already walks any directory tree for `**/usage-*.json` and records their
cost -- its logic is untouched here, on purpose (the K9 mandate is
explicit: map the *path*, not the ingestion code). This module's only job
is to make office usage files visible under the SAME root
`ingest_workspace`'s default already scans (`storage/workspaces/`), via a
cheap hardlink-or-copy sync rather than a second `ingest_workspace(...)`
call per office (which would also work, but this keeps the "one budget
sweep, one root" operational habit K0's admin sweep already assumes).

Sync direction is one-way and idempotent: office output files are never
mutated or deleted by this module, only mirrored. Uses hardlinks when the
office data dir and `storage/workspaces/` are on the same filesystem (the
common case -- both live under this repo checkout) to avoid doubling disk
usage; falls back to a copy across filesystems.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from cano_hermes.config import settings

logger = logging.getLogger(__name__)

# K9 office.yaml <-> Docker office names (kept in sync with
# cano_hermes/bridge/office_launcher.py's PROFILE_TO_OFFICE values).
OFFICE_NAMES = ("analytics", "ugc", "content", "publish", "market-intel")


def _offices_data_root() -> Path:
    return Path(settings.repository_root) / "infrastructure" / "offices" / "data"


def _workspaces_root() -> Path:
    # Matches BudgetService.ingest_workspace's own default literal
    # ("storage/workspaces") -- no dedicated Settings field exists for
    # this path (checked: cano_hermes/config.py has no `workspace*`
    # field), so this mirrors that hardcoded default rather than
    # inventing a new setting for a single call site.
    return Path(settings.repository_root) / "storage" / "workspaces"


def sync_office_usage_to_workspaces(
    offices_data_root: Path | None = None,
    workspaces_root: Path | None = None,
) -> int:
    """Mirror every `infrastructure/offices/data/<office>/output/usage-*.json`
    into `storage/workspaces/office-<office>/`, so a plain
    `BudgetService().ingest_workspace()` (default root) picks them up
    without any change to `ingest_workspace` itself.

    Returns the number of files newly mirrored (0 if nothing new -- safe
    to call on every admin sweep / daily cycle tick, same cadence as K0's
    reaper). Never raises on a missing office directory (offices that were
    never started yet have no `data/<office>/output/`); only real
    filesystem errors on the destination propagate.
    """
    offices_data_root = offices_data_root or _offices_data_root()
    workspaces_root = workspaces_root or _workspaces_root()
    mirrored = 0

    for office in OFFICE_NAMES:
        src_dir = offices_data_root / office / "output"
        if not src_dir.is_dir():
            continue
        dst_dir = workspaces_root / f"office-{office}"
        dst_dir.mkdir(parents=True, exist_ok=True)

        for usage_file in sorted(src_dir.glob("usage-*.json")):
            dst_file = dst_dir / usage_file.name
            if dst_file.exists():
                continue
            try:
                os.link(usage_file, dst_file)
            except OSError:
                # Cross-filesystem, or hardlinks unsupported -- copy instead.
                shutil.copy2(usage_file, dst_file)
            mirrored += 1
            logger.debug("mirrored office usage file %s -> %s", usage_file, dst_file)

    return mirrored
