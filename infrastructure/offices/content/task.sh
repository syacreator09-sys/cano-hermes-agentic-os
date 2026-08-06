#!/usr/bin/env bash
# office-content step 1 (K9) -- real read-only/plan invocation of Factory V5
# by contract (skills/factory-v5-contract/SKILL.md), replacing the F11
# DESIGN-ONLY STUB.
#
# Kanban profile this container serves: hermes-produccion (see
# offices/hermes-produccion/office.yaml, reclassified isolation: folder ->
# docker in K9 -- rendering/ffmpeg/Remotion work is heavy enough to want
# container sandboxing even though the office.yaml contract originally
# assumed a folder-isolated native worker; see K9 report for the full
# reconciliation of office.yaml <-> Docker office). hermes-guiones (pure
# LLM scriptwriting) stays a native folder-isolated worker, not this
# container -- it doesn't need factory-v5's mount or a sandbox.
#
# Runs ONLY commands in factory.py's SAFE_DRY_RUN_ACTIONS family
# (provider-health, validate-yaml -- both confirmed live in the
# factory-v5-contract skill's own smoke test). Nothing that renders or
# uploads (SENSITIVE_ACTIONS) is ever invoked from here -- that always
# needs a real ApprovalRequest resolved by a human outside this container
# (ApprovalService.resolve, F3), never triggered automatically.
#
# Still can't drive a real stage-pipeline command: runtime/stage-handlers.yaml
# is still missing from this factory-ia-channel-v5 checkout (pending manual
# copy from OMEN, see skills/factory-v5-contract/SKILL.md "Gap conocido").
# That gap does NOT block provider-health/validate-yaml, which don't touch
# the stage/handler pipeline -- so this office now does real, useful,
# zero-cost work instead of a stub, while the stage-pipeline gap stays
# honestly documented rather than faked.
# factory-ia-channel-v5's own .venv/bin/python(3) is a symlink chain ending
# in an ABSOLUTE host path (/usr/bin/python3), same issue office-ugc's
# task.sh already hit and solved for ugc-commerce-studio's venv: this
# image's python:3.12-slim base keeps its interpreter at
# /usr/local/bin/python3, so the venv's own symlink doesn't resolve inside
# the container (verified live: `test -x .venv/bin/python` is false here).
# Same fix as office-ugc -- reuse office-base's own python3.12 (matching
# minor version, so factory-v5's compiled deps stay ABI-compatible) and
# point PYTHONPATH at its venv's site-packages directly instead of
# invoking the venv's own (broken-in-this-image) interpreter.
set -uo pipefail

FACTORY_REPO="/home/cano/repos/factory-ia-channel-v5"
FACTORY_SITE_PACKAGES="${FACTORY_REPO}/.venv/lib/python3.12/site-packages"
FACTORY_PY="python3"

echo "== office-content: factory-v5-contract (read-only/plan commands only) =="

if [ ! -d "$FACTORY_REPO" ]; then
    echo "factory-ia-channel-v5 not mounted in this run -- nothing to do."
    exit 0
fi
echo "factory-ia-channel-v5 mounted read-only at $FACTORY_REPO: OK"

if [ ! -d "$FACTORY_SITE_PACKAGES" ]; then
    echo "factory-ia-channel-v5's own venv site-packages not found at $FACTORY_SITE_PACKAGES -- cannot invoke factory.py (it depends on its own venv's deps, per factory-v5-contract skill)."
    exit 0
fi
export PYTHONPATH="${FACTORY_SITE_PACKAGES}"

if [ -f "${FACTORY_REPO}/runtime/stage-handlers.yaml" ]; then
    echo "runtime/stage-handlers.yaml present -- stage pipeline commands would be available (still not invoked here, this office only runs read-only/plan)."
else
    echo "runtime/stage-handlers.yaml still missing (known gap, pending manual copy from OMEN) -- stage-pipeline commands are unavailable; provider-health/validate-yaml below don't need it."
fi

echo
echo "-- factory.py provider-health --"
cd "$FACTORY_REPO"
"$FACTORY_PY" scripts/factory.py provider-health 2>&1
PH_STATUS=$?

echo
echo "-- factory.py validate-yaml --"
"$FACTORY_PY" scripts/factory.py validate-yaml 2>&1
VY_STATUS=$?

echo
if [ "$PH_STATUS" -eq 0 ] && [ "$VY_STATUS" -eq 0 ]; then
    echo "office-content: both read-only commands succeeded (exit 0)."
else
    echo "office-content: provider-health exit=${PH_STATUS} validate-yaml exit=${VY_STATUS} -- see output above."
fi
exit 0
