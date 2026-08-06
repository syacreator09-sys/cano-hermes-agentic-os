"""K6 (plan HERMES-KICKOFF, gap 2) — bridge between StarHome's governance
plane and hermes-agent's Kanban execution plane.

`kanban_bridge.py` is the outbound half: it turns an approved `OrderRecord`
into a triage-column task on the dedicated `starhome` Kanban board via the
`hermes kanban` CLI subprocess and lets hermes-agent's own auto-decompose
planner fan it out. It never touches the Kanban CLI's decompose command
itself — see that module's docstring for why.

K7 will add `inbound.py`, the other half: hooks from a `~/.hermes/plugins/
starhome-bridge/` plugin POST task lifecycle events back here, resolved via
`SQLiteStore.get_bridge_link_by_kanban_task_id`.
"""
