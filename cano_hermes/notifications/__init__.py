"""K4 (plan HERMES-KICKOFF, gap 6) — Telegram delivery for task transitions.

`telegram.py` is a thin, dependency-free (beyond httpx, already a project
dependency) Bot API client. `service.py` wires it to `TaskEngine.transition`
and `ApprovalService.request` via optional observer callbacks, so DONE,
FAILED and pending-APPROVAL each produce one Telegram message without any
call site having to remember to send one.
"""
