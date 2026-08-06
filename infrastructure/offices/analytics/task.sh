#!/usr/bin/env bash
# office-analytics step 1 (F11): re-run F2's connection-matrix audit from
# inside the container, read-only, against whatever repos this office was
# actually given (see docker-compose.yml volumes for office-analytics).
#
# Deliberately narrower than the host-level F2 run: this container is only
# handed StarHome's own repo and hermes-agent's (both needed anyway, the
# second one for the hermes supervisor in step 2). factory-v5 and the two
# command-center .env files are NOT mounted here — office-analytics doesn't
# need read access to those to do its job of watching StarHome's own health,
# and the credential-minimization principle from subprocess_executor.py
# (F3) says an office should only see what its function requires. The
# script itself already handles missing systems as "ausente" without
# erroring, so this is a real, honest (smaller) run, not a broken one.
set -uo pipefail

# connection_matrix.py resolves paths via Path.home() / "repos/...". The
# container's real $HOME is /office (see common/Dockerfile); temporarily
# point it at the host-shaped path so the bind-mounted repos resolve.
export HOME=/home/cano

echo "== office-analytics: connection matrix (F2 script, read-only) =="
python3 /home/cano/repos/cano-hermes-agentic-os/scripts/connection_matrix.py
echo
echo "== office-analytics: mounted-repo health check =="
for repo in /home/cano/repos/cano-hermes-agentic-os /home/cano/repos/hermes-agent; do
    if [ -d "$repo" ]; then
        echo "OK   $repo (read-only mount present)"
    else
        echo "MISS $repo (not mounted in this office)"
    fi
done
