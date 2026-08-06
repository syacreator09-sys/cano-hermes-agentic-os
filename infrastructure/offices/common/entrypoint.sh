#!/usr/bin/env bash
# Shared supervisor for every Prometeo office container (F11).
#
# Pattern (same for all 4 offices, only /office/task.sh differs):
#   1. Run the office's own deterministic, read-only pipeline step
#      (/office/task.sh, baked into each office's own Dockerfile layer)
#      against repos mounted read-only from the host.
#   2. Hand that output to `hermes --oneshot` (the only supervisor — the
#      interactive hermes CLI refuses subprocesses, this is the sole
#      programmatic path) to narrate/summarize the cycle.
#
# hermes itself is never installed in this image; it is bind-mounted
# read-only from the host at the exact absolute path it lives at there
# (/home/cano/repos/hermes-agent), because its venv is a PEP 660 editable
# install whose finder hardcodes that source path — see F11 report for why.
set -euo pipefail

: "${OFFICE_NAME:?OFFICE_NAME is required}"
: "${HERMES_MODEL:=kimi-k2.6}"
: "${HERMES_PROVIDER:=kimi}"
: "${HERMES_TOOLSETS:=}"

HERMES_REPO="/home/cano/repos/hermes-agent"
HERMES_PY="${HERMES_REPO}/venv/bin/python3"

mkdir -p /office/output
TS="$(date +%s)"
TASK_OUT="/office/output/task-${OFFICE_NAME}-${TS}.txt"

echo "[office-${OFFICE_NAME}] $(date -u +%FT%TZ) -- starting cycle"

# --- Step 1: deterministic pipeline step (no LLM, no credentials beyond what
# the office's own allowlist injected) -------------------------------------
if [ -x /office/task.sh ]; then
    /office/task.sh > "$TASK_OUT" 2>&1 || echo "(task.sh exited non-zero, see output above)" >> "$TASK_OUT"
else
    echo "(office-${OFFICE_NAME} has no task.sh -- design-only office, skipping step 1)" > "$TASK_OUT"
fi
echo "--- step 1 output (${TASK_OUT}) ---"
cat "$TASK_OUT"

# --- Step 2: hermes --oneshot supervises / narrates the cycle -------------
if [ ! -x "$HERMES_PY" ]; then
    echo "[office-${OFFICE_NAME}] hermes venv not found at ${HERMES_PY} -- is the bind mount missing? Skipping step 2." >&2
    exit 0
fi

OBJECTIVE="${HERMES_OBJECTIVE:-Eres el supervisor de office-${OFFICE_NAME} de StarHome OS (Plan Prometeo). Resume en <= 6 lineas, en espanol, el resultado del paso 1 de este ciclo (abajo). Si ves un error real, dilo. No inventes cifras que no esten en el output.}"
CONTEXT="$(tail -c 4000 "$TASK_OUT")"
USAGE_FILE="/office/output/usage-${OFFICE_NAME}-${TS}.json"
REPORT_FILE="/office/output/hermes-report-${OFFICE_NAME}-${TS}.md"

echo "--- step 2: hermes --oneshot (model=${HERMES_MODEL} provider=${HERMES_PROVIDER}) ---"
set +e
"$HERMES_PY" -m hermes_cli.main \
    --oneshot "${OBJECTIVE}

--- salida real del paso 1 (task.sh) ---
${CONTEXT}" \
    --model "$HERMES_MODEL" \
    --provider "$HERMES_PROVIDER" \
    --toolsets "$HERMES_TOOLSETS" \
    --usage-file "$USAGE_FILE" \
    | tee "$REPORT_FILE"
HERMES_EXIT=$?
set -e

echo "[office-${OFFICE_NAME}] cycle done (hermes exit=${HERMES_EXIT}). Artifacts in /office/output/"
exit "$HERMES_EXIT"
