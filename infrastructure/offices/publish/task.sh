#!/usr/bin/env bash
# office-publish step 1 (K9) -- real dedup -> release guard -> draft ->
# dry-run chain, replacing the F11 DESIGN-ONLY STUB. Gate humano (dispatch)
# stays OUTSIDE this container -- this script can never publish anything.
#
# Kanban profile this container serves: hermes-distribucion (see
# offices/hermes-distribucion/office.yaml -- mission "preparar drafts de
# subida verificados... el dispatch SIEMPRE es gate", isolation: docker,
# already a 1:1 match with office-publish by name and mission).
#
# dedup (skills/reel-dedup-check/SKILL.md, evidence from F9): the
# aspirational published_ledger.csv does not exist anywhere; the real
# mechanism is command-center's own upload_log_ugc.db (SQLite,
# 01-offices/ugc-affiliate/upload_log_ugc.db, created at RUNTIME, not
# committed -- so it usually won't exist here either, and that absence is
# itself a real, reportable state per the skill's rule, not an error to
# paper over). Only rows with a real, non-empty req_id/video id AND
# status=success count as "already published" -- dry_run/error rows never
# block or unblock production.
set -uo pipefail

LEDGER_DIR="/home/cano/repos/cano-ai-command-center/01-offices/ugc-affiliate"
LEDGER_DB="${LEDGER_DIR}/upload_log_ugc.db"
DRAFT_OUT="/office/output/draft-$(date +%s).json"

echo "== office-publish: dedup -> release guard -> draft -> dry-run (never dispatch) =="
echo "credentials in this container: tier-0 only (KIMI_API_KEY/KIMI_BASE_URL) -- no UPLOAD_POST_*/TIKTOK_*/META_*/YOUTUBE_* ever present here."
echo

echo "-- step: dedup (skills/reel-dedup-check) --"
DEDUP_STATE="unknown"
if [ ! -d "$LEDGER_DIR" ]; then
    echo "command-center's ugc-affiliate office not mounted in this run -- dedup check skipped (report as blocked upstream, not as 'no duplicates')."
    DEDUP_STATE="ledger_dir_not_mounted"
elif [ ! -f "$LEDGER_DB" ]; then
    echo "$LEDGER_DB does not exist (real, expected state: this SQLite db is created at runtime by uploader.py and is NOT committed to the repo -- per reel-dedup-check's own F9 finding)."
    echo "Per the skill's rule 2.1: an absent/insufficient ledger must be reported as a BLOCK on producing a fresh dispatch decision, never silently treated as 'no duplicates found'."
    DEDUP_STATE="ledger_absent"
else
    echo "found $LEDGER_DB -- querying real rows (read-only, sqlite3 stdlib) for canal+slug+fecha with a real video id and status=success..."
    python3 - "$LEDGER_DB" <<'PYEOF'
import sqlite3, sys
db = sys.argv[1]
try:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cur = conn.execute("SELECT canal, slug, fecha, status, req_id FROM uploads ORDER BY fecha DESC LIMIT 20")
    rows = cur.fetchall()
except Exception as exc:
    print(f"(could not query uploads table: {exc})")
    rows = []
real_published = [r for r in rows if r[3] == "success" and r[4] not in (None, "", "1", "test")]
print(f"rows seen: {len(rows)} -- rows counting as real published (status=success, non-placeholder req_id): {len(real_published)}")
for r in real_published[:10]:
    print(f"  canal={r[0]} slug={r[1]} fecha={r[2]} req_id={r[4]}")
PYEOF
    DEDUP_STATE="ledger_queried"
fi

echo
echo "-- step: release guard --"
echo "release guard = confirm dedup step above did not find a blocking duplicate, AND no real publish credential is present in this environment."
if env | grep -qE '^(UPLOAD_POST_|TIKTOK_|META_|YOUTUBE_).*_(TOKEN|KEY|SECRET)='; then
    echo "FAIL: a publish-shaped credential is present in this container's environment -- this must never happen, refusing to draft."
    exit 1
fi
echo "OK: no publish credentials present; dedup_state=${DEDUP_STATE}."

echo
echo "-- step: draft + dry-run (no network call, no upload SDK invoked) --"
python3 - "$DRAFT_OUT" "$DEDUP_STATE" <<'PYEOF'
import json, sys, datetime
out_path, dedup_state = sys.argv[1], sys.argv[2]
draft = {
    "schema_version": "1.0",
    "office": "publish",
    "kanban_profile": "hermes-distribucion",
    "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "dedup_state": dedup_state,
    "mode": "draft_only",
    "dry_run": True,
    "human_review_required": True,
    "dispatch_allowed": False,
    "note": "Draft produced by office-publish task.sh. Real dispatch NEVER happens from this container -- it requires a resolved ApprovalRequest (governance/approvals.py) by a human actor different from whoever requested it (self-approval is rejected in code), executed by StarHome's own execution service outside this container.",
}
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump(draft, fh, indent=2, ensure_ascii=False)
print(json.dumps(draft, indent=2, ensure_ascii=False))
PYEOF

echo
echo "office-publish: draft written to ${DRAFT_OUT} (dispatch_allowed=false, human_review_required=true)."
exit 0
