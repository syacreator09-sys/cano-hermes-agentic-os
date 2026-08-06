# StarHome Personal Runtime v0.3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe, additive personal operating layer to StarHome OS with domain coordinators and reusable skills for daily operations, finance, revenue, projects, content, investments, documents and learning.

**Architecture:** Keep the existing Conductor as the only top-level orchestrator. Add domain coordinators as candidate manifests with minimum permissions and no production access. Add procedural skills as independent capability modules. Do not change existing runtime code, databases, integrations, active agents or production settings in this increment.

**Tech Stack:** Python 3.11, Pydantic, PyYAML, pytest, Ruff, GitHub Actions, Markdown Agent Skills.

## Global Constraints

- Work only on `feature/starhome-personal-runtime-v0.3`; never commit directly to `main`.
- All new domain agents start as `candidate`.
- No agent receives Docker socket, global secrets, unrestricted filesystem, production, publishing, payment or trading permissions.
- New skills are advisory or record-preparation capabilities; external writes require a later approved adapter.
- No existing source file is modified unless a failing validation proves it is necessary.
- No provider calls, deployment, publication, financial transaction or destructive operation is enabled.
- Every added manifest must pass `AgentManifest.model_validate`.
- Every referenced skill must contain a readable `SKILL.md`.

---

### Task 1: Add branch-only validation gate

**Files:**
- Create: `.github/workflows/starhome-quality.yml`
- Create: `tests/test_personal_runtime_pack.py`

**Interfaces:**
- Consumes: `cano_hermes.domain.models.AgentManifest`, repository YAML manifests and skill directories.
- Produces: automated proof that the personal runtime pack exists, validates and remains non-production.

- [ ] Add a GitHub Actions workflow using Python 3.11.
- [ ] Install the project with development dependencies.
- [ ] Run `python scripts/validate.py`, `pytest`, and `ruff check .`.
- [ ] Add failing tests for the eight planned domain coordinators and their required skills.
- [ ] Confirm the branch fails before manifests and skills exist.

### Task 2: Add personal operations and finance coordinators

**Files:**
- Create: `agents/personal-operations/chief-of-staff.yaml`
- Create: `agents/finance/finance-controller.yaml`
- Create: `skills/daily-brief/SKILL.md`
- Create: `skills/capture-anything/SKILL.md`
- Create: `skills/weekly-review/SKILL.md`
- Create: `skills/expense-capture/SKILL.md`
- Create: `skills/cash-position/SKILL.md`
- Create: `skills/finance-close/SKILL.md`

**Interfaces:**
- Consumes: compact Nexus context and task event recording.
- Produces: safe candidate coordinators for daily planning and financial record preparation.

- [ ] Add candidate manifests with workspace-only filesystem, allowlisted network and approval-required production.
- [ ] Keep costs, turns and timeout bounded.
- [ ] Add deterministic procedures with explicit verification and escalation rules.
- [ ] Run manifest and skill validation.

### Task 3: Add revenue and project coordinators

**Files:**
- Create: `agents/revenue/revenue-operator.yaml`
- Create: `agents/projects/project-operator.yaml`
- Create: `skills/lead-next-action/SKILL.md`
- Create: `skills/pipeline-review/SKILL.md`
- Create: `skills/project-status/SKILL.md`
- Create: `skills/blocker-review/SKILL.md`

**Interfaces:**
- Consumes: Nexus context and task events.
- Produces: recommended next actions without sending messages or changing external systems.

- [ ] Add candidate manifests.
- [ ] Require approval for communication, CRM writes and external side effects.
- [ ] Validate all files.

### Task 4: Add specialist coordinators

**Files:**
- Create: `agents/content/content-intelligence-director.yaml`
- Create: `agents/investments/investment-intelligence.yaml`
- Create: `agents/documents/document-auditor.yaml`
- Create: `agents/learning/learning-coach.yaml`
- Create: `skills/content-opportunity-brief/SKILL.md`
- Create: `skills/investment-thesis-review/SKILL.md`
- Create: `skills/document-consistency-audit/SKILL.md`
- Create: `skills/learning-session/SKILL.md`

**Interfaces:**
- Consumes: source-backed research or user-provided documents.
- Produces: briefs, simulations, audits and learning plans; never publication, trades or document mutation.

- [ ] Add candidate manifests with domain-specific safety restrictions.
- [ ] Make investment execution, publication and document mutation explicitly prohibited.
- [ ] Validate all files.

### Task 5: Document activation and rollback

**Files:**
- Create: `docs/PERSONAL-RUNTIME-V0.3.md`

**Interfaces:**
- Consumes: validated candidate manifests and skills.
- Produces: operator runbook for testing, approval, promotion and rollback.

- [ ] Document what is included and explicitly excluded.
- [ ] Document validation commands.
- [ ] Document lifecycle from candidate to active.
- [ ] Document rollback as branch deletion or file reversion before merge.
- [ ] Open a draft pull request; do not merge.

## Verification

Run in a clean checkout of the feature branch:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python scripts/validate.py
pytest -q
ruff check .
```

Expected result: all commands pass, all new agents remain `candidate`, and no production integration is enabled.
