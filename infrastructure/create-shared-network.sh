#!/usr/bin/env bash
# K9 (plan HERMES-KICKOFF): create the `starhome-net` bridge network shared
# by Baserow and the offices, once, before either compose project's first
# `up`. Idempotent -- safe to re-run.
#
# Why external (not owned by either compose file): Baserow
# (infrastructure/baserow/docker-compose.yml) and the offices
# (infrastructure/offices/docker-compose.yml) are two separate Compose
# *projects* (separate directories, no shared top-level `name:`), each of
# which would otherwise get its own private default network. Declaring
# `starhome-net` as `external: true` in both compose files lets them join
# the same physical network without making one project responsible for
# creating it (and erroring if brought up in the "wrong" order).
#
# This does not add any new capability that didn't already exist within
# each project -- see the network-isolation note at the top of
# infrastructure/offices/docker-compose.yml for why: F11 never actually
# restricted network access per-service (no network_mode/networks block
# existed before K9), so this only bridges two projects that could already
# each reach the internet and talk to their own siblings.
set -euo pipefail

NETWORK_NAME="starhome-net"

if docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    echo "network '$NETWORK_NAME' already exists."
else
    docker network create "$NETWORK_NAME"
    echo "created network '$NETWORK_NAME'."
fi
