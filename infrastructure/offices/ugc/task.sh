#!/usr/bin/env bash
# office-ugc step 1 (F11): the free tier of F9's UGC-Affiliate pipeline,
# containerized. Runs ugc-commerce-studio's own `plan` CLI against the
# repo's own example fixtures (examples/product.json, examples/profile.json)
# -- exactly the command F9's dry-run report already validated on the host
# (reports/ugc-affiliate-dry-run-2026-08-06.md sec. 4) as the proposed
# engine for this office. Zero network, zero Higgsfield credits
# (paid_generation stays false), zero writes into the mounted repo -- the
# repo is mounted read-only and the plan is written to /office/output.
#
# ugc-commerce-studio's own venv assumes /usr/bin/python3 (Ubuntu host
# layout); python:3.12-slim (this image's base) keeps Python at
# /usr/local/bin instead, so its venv/bin/python3 symlink doesn't resolve
# here. Rather than fight that, this office reuses office-base's own
# python3.12 interpreter (same minor version as the repo's venv, so its
# compiled deps are ABI-compatible) and points PYTHONPATH at the repo's
# src/ and its venv's site-packages directly.
set -uo pipefail

UGC_REPO="/home/cano/repos/ugc-commerce-studio"
export PYTHONPATH="${UGC_REPO}/src:${UGC_REPO}/.venv/lib/python3.12/site-packages"

echo "== office-ugc: ugc-commerce-studio plan (dry-run, \$0) =="
cd "$UGC_REPO"
python3 -m ugc_commerce.cli plan \
    --product examples/product.json \
    --profile examples/profile.json \
    --output /office/output/plan.json
STATUS=$?

echo
echo "== office-ugc: opportunity summary =="
if [ -f /office/output/plan.json ]; then
    python3 -c "
import json
plan = json.load(open('/office/output/plan.json'))
print('scope_id:', plan['scope_id'])
print('opportunity.score:', plan['opportunity']['score'])
print('recommendation:', plan['opportunity']['recommendation'])
print('scenes:', len(plan['scenes']))
print('auto_publish:', plan.get('auto_publish'))
print('human_review_required:', plan.get('human_review_required'))
"
fi
exit $STATUS
