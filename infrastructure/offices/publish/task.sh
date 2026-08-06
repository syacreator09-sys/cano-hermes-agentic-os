#!/usr/bin/env bash
# office-publish step 1 (F11) -- DESIGN-ONLY STUB.
#
# Intended chain (never fully automated): dedup -> release guard -> draft ->
# dry-run -> gate humano (ApprovalService, F3) -> dispatch -> ledger. This
# container is never given real publish credentials (no Upload-post token,
# no TikTok/Meta/etc keys) -- see README.md. It can only ever produce a
# draft; a real dispatch happens outside this container, after a human
# resolves an ApprovalRequest that a *different* actor requested
# (self-approval is rejected by ApprovalService.resolve, F3).
set -uo pipefail

echo "== office-publish: design-only stub =="
echo "This office never holds real publish credentials (verify via 'docker compose config' -- no UPLOAD_POST_*, TIKTOK_*, META_* etc. vars appear for this service)."
echo "Real dispatch requires: dedup -> release guard -> draft -> dry-run -> human ApprovalRequest (F3) -> dispatch -> ledger."
echo "No draft produced in this stub run (F11 scope: design/scaffold only)."
