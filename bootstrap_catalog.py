from __future__ import annotations
import json
from pathlib import Path
import yaml

AGENTS = [
("governance","conductor","lead","Coordinate plans, teams, budgets, approvals and final delivery","hermes","balanced"),
("governance","task-governor","worker","Control task state, dependencies, retries and recovery","hermes","cheap_daily"),
("governance","context-curator","worker","Build small relevant context packs from Nexus","hermes","cheap_daily"),
("governance","budget-controller","worker","Track subscription and API budgets and escalation","hermes","cheap_daily"),
("governance","security-guardian","reviewer","Review permissions, secrets, containers and risky actions","hermes","critical_review"),
("governance","evaluation-manager","reviewer","Run acceptance gates and independent evaluations","hermes","critical_review"),
("engineering","engineering-lead","lead","Coordinate architecture, implementation, tests and reviews","claude-code","engineering_architecture"),
("engineering","claude-architect","architect","Design architecture, specifications and review complex diffs","claude-code","engineering_architecture"),
("engineering","codex-builder","builder","Implement code, tests, refactors and interfaces","codex","engineering_build"),
("engineering","test-engineer","reviewer","Design and run automated acceptance tests","codex","engineering_build"),
("engineering","code-reviewer","reviewer","Review correctness, maintainability and regression risk","claude-code","critical_review"),
("engineering","ui-reviewer","reviewer","Inspect usability, accessibility and responsive behavior","codex","engineering_build"),
("engineering","repository-cartographer","worker","Map repositories, dependencies and capability boundaries","claude-code","engineering_architecture"),
("research","research-lead","lead","Coordinate research questions, sources and synthesis","hermes","research_long"),
("research","kimi-researcher","worker","Process long context and synthesize large research sets","api","research_long"),
("research","deepseek-analyst","worker","Perform economical structured analysis and extraction","api","cheap_daily"),
("research","qwen-processor","worker","Process batches, normalize data and draft structured outputs","api","qwen_batch"),
("research","grok-trend-analyst","worker","Analyze current trends and alternative signals","api","trend_current"),
("research","evidence-verifier","reviewer","Verify claims, citations, contradictions and freshness","hermes","critical_review"),
("content","content-lead","lead","Coordinate content portfolio, calendar and approvals","hermes","balanced"),
("content","trend-radar","worker","Detect relevant opportunities and score them","api","trend_current"),
("content","editorial-analyst","worker","Convert verified opportunities into editorial decisions","hermes","cheap_daily"),
("content","creative-director","worker","Create concepts, formats and creative briefs","api","premium_general"),
("content","scriptwriter","worker","Write scripts matching channel, duration and audience","api","cheap_daily"),
("content","storyboard-designer","worker","Build deterministic scenes, shots and production instructions","api","cheap_daily"),
("content","factory-operator","worker","Invoke Factory V5 through an approved external contract","hermes","cheap_daily"),
("content","analytics-learner","reviewer","Connect performance metrics to reusable lessons","hermes","cheap_daily"),
("forge","forge-lead","lead","Coordinate capability audit, creation and promotion","hermes","balanced"),
("forge","capability-auditor","worker","Determine whether an agent, skill, MCP or reuse is needed","hermes","cheap_daily"),
("forge","agent-designer","architect","Design bounded agent contracts, tools and memory","claude-code","engineering_architecture"),
("forge","skill-engineer","builder","Create reusable progressive-disclosure skills","codex","engineering_build"),
("forge","mcp-engineer","builder","Create and test bounded MCP servers and adapters","codex","engineering_build"),
("forge","container-builder","builder","Build rootless sandbox images and policies","codex","engineering_build"),
("operations","infrastructure-operator","lead","Operate Ubuntu, services, logs and reversible infrastructure","hermes","balanced"),
("operations","browser-operator","worker","Perform bounded browser tasks in isolated sessions","hermes","cheap_daily"),
("operations","automation-engineer","worker","Build scheduled and event-driven workflows","codex","engineering_build"),
("operations","voice-operator","worker","Coordinate voice input, output and call adapters","hermes","cheap_daily"),
("operations","communication-operator","worker","Coordinate Telegram, WhatsApp and notifications safely","hermes","cheap_daily"),
]

SKILLS = [
"task-planning","task-governance","capability-routing","budget-routing","security-review",
"evaluation-gates","architecture-spec","repo-analysis","git-worktrees","tdd-build","testing",
"code-review","ui-review","integration-build","deep-research","research-plan","source-verification",
"batch-analysis","structured-processing","trend-analysis","trend-radar","editorial-scoring",
"creative-brief","scriptwriting","storyboard","content-pipeline","factory-v5","metrics-learning",
"agent-blueprint","capability-audit","skill-authoring","mcp-build","container-sandbox",
"forge-governance","nexus-context","graphify-map","infra-ops","browser-automation",
"communications","voice-flow",
]


def generate(root: Path) -> None:
    for team, agent_id, role, objective, runtime, profile in AGENTS:
        target=root/'agents'/team/f'{agent_id}.yaml'; target.parent.mkdir(parents=True,exist_ok=True)
        data={"id":agent_id,"name":agent_id.replace('-',' ').title(),"team":team,"role":role,
              "objective":objective,"status":"approved","runtime":runtime,"model_profile":profile,
              "permissions":{"production":"denied","secrets":"brokered"},
              "memory":{"write":"proposal_only"},"evaluation":{"required":True,"minimum_score":0.85}}
        target.write_text(yaml.safe_dump(data,sort_keys=False),encoding='utf-8')
    for skill_id in SKILLS:
        folder=root/'skills'/skill_id; folder.mkdir(parents=True,exist_ok=True)
        purpose=skill_id.replace('-',' ').capitalize()
        manifest={"id":skill_id,"version":"0.2.0","status":"approved","purpose":purpose,
                  "progressive_disclosure":True,"evaluation_required":True}
        (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        skill_text = (
            f"# {purpose}\n\n"
            "## Contract\n"
            f"Use this skill only when the task requires {purpose.lower()}.\n\n"
            "## Steps\n"
            "1. Inspect inputs.\n"
            "2. Apply bounded tools.\n"
            "3. Verify output.\n"
            "4. Record evidence and rollback.\n"
        )
        (folder/'SKILL.md').write_text(skill_text,encoding='utf-8')
