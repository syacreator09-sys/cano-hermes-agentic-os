#!/usr/bin/env bash
# Shared supervisor for every Prometeo/HERMES-KICKOFF office container.
#
# Two modes, selected by $WORKER_MODE:
#
#   WORKER_MODE=kanban (K9 default) -- the office becomes a real kanban
#     worker: it polls board `starhome` for READY tasks assigned to its
#     own profile ($OFFICE_PROFILE), claims one at a time, runs the
#     office's deterministic step (/office/task.sh) against the task's
#     title/body, then narrates+executes via `hermes --oneshot`, and
#     closes the loop with `hermes kanban complete`/`block`. This is what
#     makes `docker compose --profile <office> up -d` a live worker
#     instead of a one-shot cron cycle.
#
#   WORKER_MODE=oneshot (F11 legacy behaviour, kept for manual debugging
#     and for any office run outside the kanban bus) -- run /office/task.sh
#     once, hand its output to one `hermes --oneshot` narration call, exit.
#
# In both modes hermes itself is never installed in this image; it is
# bind-mounted read-only from the host at the exact absolute path it lives
# at there (/home/cano/repos/hermes-agent), because its venv is a PEP 660
# editable install whose finder hardcodes that source path -- see F11
# report for why.
#
# Kanban access (K9): the container never sees the host's real
# ~/.hermes (config.yaml/.env/auth.json with live credentials). Instead
# compose bind-mounts ONLY ~/.hermes/kanban/boards/<board> read-write into
# a masked $HERMES_HOME (default /office/hermes-home) -- verified live
# that `HERMES_HOME=<empty dir with just kanban/boards/<board>> hermes
# kanban --board <board> list --json` works with nothing else present.
# Task titles/bodies/comments are not secrets; API keys stay out of the
# mount entirely, so the office's existing credential allowlist
# (docker-compose.yml `environment:` blocks) is still the only source of
# real secrets any office ever sees.
set -uo pipefail

: "${OFFICE_NAME:?OFFICE_NAME is required}"
: "${HERMES_MODEL:=kimi-k2.6}"
: "${HERMES_PROVIDER:=kimi}"
: "${HERMES_TOOLSETS:=}"
: "${WORKER_MODE:=kanban}"
: "${KANBAN_BOARD:=starhome}"
: "${OFFICE_PROFILE:=${OFFICE_NAME}}"
: "${POLL_INTERVAL_SECONDS:=20}"
: "${HERMES_HOME:=/office/hermes-home}"

HERMES_REPO="/home/cano/repos/hermes-agent"
HERMES_PY="${HERMES_REPO}/venv/bin/python3"
HERMES_CLI="${HERMES_REPO}/venv/bin/hermes"

mkdir -p /office/output

log() { echo "[office-${OFFICE_NAME}] $(date -u +%FT%TZ) -- $*"; }

# --- deterministic step 1 (task.sh) -----------------------------------------
run_task_step() {
    local out_file="$1"
    if [ -x /office/task.sh ]; then
        /office/task.sh > "$out_file" 2>&1 || echo "(task.sh exited non-zero, see output above)" >> "$out_file"
    else
        echo "(office-${OFFICE_NAME} has no task.sh -- design-only office, skipping step 1)" > "$out_file"
    fi
}

# --- hermes --oneshot narration/execution -----------------------------------
run_hermes_oneshot() {
    local objective="$1" usage_file="$2" report_file="$3"
    if [ ! -x "$HERMES_PY" ]; then
        log "hermes venv not found at ${HERMES_PY} -- is the bind mount missing? skipping oneshot."
        return 0
    fi
    "$HERMES_PY" -m hermes_cli.main \
        --oneshot "$objective" \
        --model "$HERMES_MODEL" \
        --provider "$HERMES_PROVIDER" \
        --toolsets "$HERMES_TOOLSETS" \
        --usage-file "$usage_file" \
        | tee "$report_file"
    return "${PIPESTATUS[0]}"
}

# ============================================================================
# WORKER_MODE=oneshot -- F11 legacy single-cycle behaviour
# ============================================================================
run_oneshot_mode() {
    TS="$(date +%s)"
    TASK_OUT="/office/output/task-${OFFICE_NAME}-${TS}.txt"
    log "starting one-shot cycle"
    run_task_step "$TASK_OUT"
    echo "--- step 1 output (${TASK_OUT}) ---"
    cat "$TASK_OUT"

    OBJECTIVE="${HERMES_OBJECTIVE:-Eres el supervisor de office-${OFFICE_NAME} de StarHome OS. Resume en <= 6 lineas, en espanol, el resultado del paso 1 de este ciclo (abajo). Si ves un error real, dilo. No inventes cifras que no esten en el output.}

--- salida real del paso 1 (task.sh) ---
$(tail -c 4000 "$TASK_OUT")"
    USAGE_FILE="/office/output/usage-${OFFICE_NAME}-${TS}.json"
    REPORT_FILE="/office/output/hermes-report-${OFFICE_NAME}-${TS}.md"
    echo "--- step 2: hermes --oneshot (model=${HERMES_MODEL} provider=${HERMES_PROVIDER}) ---"
    run_hermes_oneshot "$OBJECTIVE" "$USAGE_FILE" "$REPORT_FILE"
    HERMES_EXIT=$?
    log "cycle done (hermes exit=${HERMES_EXIT}). Artifacts in /office/output/"
    exit "$HERMES_EXIT"
}

# ============================================================================
# WORKER_MODE=kanban -- K9: real kanban worker for one profile on one board
# ============================================================================
STOP=0
_on_term() { STOP=1; log "SIGTERM/SIGINT received, finishing current cycle then exiting"; }
trap _on_term TERM INT

kanban() { "$HERMES_CLI" kanban --board "$KANBAN_BOARD" "$@"; }

run_kanban_mode() {
    if [ ! -x "$HERMES_CLI" ]; then
        log "hermes CLI not found at ${HERMES_CLI} -- cannot run kanban worker mode"
        exit 1
    fi
    export HERMES_HOME
    log "kanban worker starting -- board=${KANBAN_BOARD} profile=${OFFICE_PROFILE} home=${HERMES_HOME}"

    while [ "$STOP" -eq 0 ]; do
        LIST_JSON="$(kanban list --assignee "$OFFICE_PROFILE" --status ready --json 2>/tmp/kanban-list.err)"
        if [ -z "$LIST_JSON" ] || [ "$LIST_JSON" = "[]" ]; then
            [ -s /tmp/kanban-list.err ] && log "list warning: $(cat /tmp/kanban-list.err)"
            sleep "$POLL_INTERVAL_SECONDS" & wait $!
            continue
        fi

        TASK_ID="$(printf '%s' "$LIST_JSON" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["id"] if d else "")' 2>/dev/null)"
        if [ -z "$TASK_ID" ]; then
            log "could not parse a task id out of list output, sleeping"
            sleep "$POLL_INTERVAL_SECONDS" & wait $!
            continue
        fi

        log "ready task ${TASK_ID} -- claiming"
        if ! kanban claim "$TASK_ID" >/tmp/kanban-claim.out 2>&1; then
            log "claim failed for ${TASK_ID} (probably raced another worker): $(cat /tmp/kanban-claim.out)"
            continue
        fi

        SHOW_JSON="$(kanban show "$TASK_ID" --json 2>/dev/null)"
        TITLE="$(printf '%s' "$SHOW_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("title",""))' 2>/dev/null)"
        BODY="$(printf '%s' "$SHOW_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("body") or "")' 2>/dev/null)"

        TS="$(date +%s)"
        TASK_OUT="/office/output/task-${OFFICE_NAME}-${TASK_ID}-${TS}.txt"
        run_task_step "$TASK_OUT"

        OBJECTIVE="Eres el worker de office-${OFFICE_NAME} (perfil kanban ${OFFICE_PROFILE}) de StarHome OS.
Tarea kanban ${TASK_ID}: ${TITLE}
--- cuerpo de la tarea ---
${BODY}
--- salida real del paso 1 de esta oficina (task.sh) ---
$(tail -c 4000 "$TASK_OUT")
--- instrucciones ---
Resuelve la tarea con lo que tengas disponible en este contenedor (solo lectura salvo /office/output). Si algo requiere una credencial o accion que esta oficina no tiene permitida (ver 'never' de su office.yaml), dilo explicitamente en vez de inventar el resultado. Responde en espanol, <= 10 lineas."
        USAGE_FILE="/office/output/usage-${OFFICE_NAME}-${TASK_ID}-${TS}.json"
        REPORT_FILE="/office/output/hermes-report-${OFFICE_NAME}-${TASK_ID}-${TS}.md"

        run_hermes_oneshot "$OBJECTIVE" "$USAGE_FILE" "$REPORT_FILE"
        HERMES_EXIT=$?

        RESULT_SUMMARY="$(tail -c 800 "$REPORT_FILE" 2>/dev/null | tr '\n' ' ')"
        if [ "$HERMES_EXIT" -eq 0 ]; then
            kanban comment "$TASK_ID" "office-${OFFICE_NAME}: reporte en ${REPORT_FILE##*/} (dentro del contenedor)" >/dev/null 2>&1 || true
            kanban complete "$TASK_ID" --result "${RESULT_SUMMARY:0:500}" --summary "office-${OFFICE_NAME} completo la tarea, ver ${REPORT_FILE##*/}" >/tmp/kanban-complete.out 2>&1 \
                && log "task ${TASK_ID} -> complete" \
                || log "complete failed for ${TASK_ID}: $(cat /tmp/kanban-complete.out)"
        else
            kanban block "$TASK_ID" "office-${OFFICE_NAME}: hermes --oneshot salio con codigo ${HERMES_EXIT}, ver ${REPORT_FILE##*/}" --kind transient >/tmp/kanban-block.out 2>&1 \
                && log "task ${TASK_ID} -> blocked (transient)" \
                || log "block failed for ${TASK_ID}: $(cat /tmp/kanban-block.out)"
        fi
    done
    log "worker loop exited cleanly"
    exit 0
}

case "$WORKER_MODE" in
    oneshot) run_oneshot_mode ;;
    kanban) run_kanban_mode ;;
    *) log "unknown WORKER_MODE='${WORKER_MODE}' (expected kanban|oneshot)"; exit 2 ;;
esac
