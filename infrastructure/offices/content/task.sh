#!/usr/bin/env bash
# office-content step 1 (F11) -- DESIGN-ONLY STUB, not wired to a real render.
#
# Intended real job (see README.md): invoke factory-ia-channel-v5's
# scripts/factory.py by contract (skills/factory-v5-contract/SKILL.md),
# read-only/plan commands only (provider-health, validate-yaml, route,
# asset-recommend) directly; anything that renders/uploads is a
# SENSITIVE_ACTION and needs a real ApprovalRequest from outside this
# container before it runs -- never triggered automatically here.
#
# Left as a stub in this pass because factory-v5-contract's own known gap
# (runtime/stage-handlers.yaml, missing from the factory-v5 checkout,
# expected to come from the OMEN machine) blocks any real stage-pipeline
# command from completing -- see skills/factory-v5-contract/SKILL.md
# "Gap conocido". This stub only proves the mount/credential wiring, it
# does not fabricate output.
set -uo pipefail

FACTORY_REPO="/home/cano/repos/factory-ia-channel-v5"

echo "== office-content: design-only stub =="
if [ -d "$FACTORY_REPO" ]; then
    echo "factory-ia-channel-v5 mounted read-only at $FACTORY_REPO: OK"
    echo "NOT invoking scripts/factory.py -- runtime/stage-handlers.yaml gap (see factory-v5-contract skill)."
else
    echo "factory-ia-channel-v5 not mounted in this run."
fi
echo "office-content has no real pipeline execution wired yet (F11 scope: design/scaffold only)."
