import asyncio,tempfile,unittest
from pathlib import Path
from cano_hermes.domain.enums import RiskLevel,TaskStatus
from cano_hermes.domain.models import TaskCreate,AgentManifest
from cano_hermes.governance.budget import BudgetLedger
from cano_hermes.governance.policy import PermissionEngine
from cano_hermes.intelligence.router import ModelRouter,RouteRequest
from cano_hermes.nexus.context import ContextBuilder
from cano_hermes.nexus.graph import KnowledgeGraph
from cano_hermes.nexus.markdown import MarkdownVault
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.execution_service import ExecutionService
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.registry.skills import SkillRegistry
from cano_hermes.storage.sqlite import SQLiteStore

ROOT=Path(__file__).resolve().parents[1]
class FoundationTests(unittest.TestCase):
    def make_engine(self,d): return TaskEngine(SQLiteStore(f'sqlite:///{d}/db.sqlite'),Conductor(AgentRegistry(ROOT/'agents'),ModelRouter()))
    def test_agent_registry(self):
        agents=AgentRegistry(ROOT/'agents').all(); self.assertGreaterEqual(len(agents),35); self.assertTrue(any(a.id=='conductor' for a in agents))
    def test_skill_registry(self): self.assertGreaterEqual(len(SkillRegistry(ROOT/'skills').load()),35)
    def test_router_engineering_prefers_subscription(self): self.assertIn(ModelRouter().route(RouteRequest(domain='engineering',complexity=5,tools_required=True)).profile.id,{'claude-subscription','codex-subscription'})
    def test_router_research(self): self.assertEqual(ModelRouter().route(RouteRequest(domain='research',complexity=4,context_need=5)).profile.id,'kimi-research')
    def test_policy_dry_run(self):
        p=PermissionEngine('dry_run'); self.assertTrue(p.evaluate('simulate').allowed); self.assertFalse(p.evaluate('deploy').allowed)
    def test_budget(self):
        b=BudgetLedger(1); b.record(.4); self.assertAlmostEqual(b.spent_usd,.4); self.assertFalse(b.can_spend(.7))
    def test_task_lifecycle(self):
        with tempfile.TemporaryDirectory() as d:
            e=self.make_engine(d); t=e.create(TaskCreate(title='Build feature',objective='Implement a safe feature',domain='engineering')); p=e.plan(t.id); self.assertEqual(p.status,TaskStatus.PLANNED); self.assertIsNotNone(p.assigned_agent); self.assertEqual(len(e.store.list_events(t.id)),2)
    def test_execution_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            e=self.make_engine(d); t=e.create(TaskCreate(title='Review repo',objective='Review architecture',domain='engineering')); e.plan(t.id); r=asyncio.run(ExecutionService(e,'dry_run',Path(d)/'ws').run(t.id,'claude-code')); self.assertEqual(r.status,'simulated'); self.assertEqual(e.require(t.id).status,TaskStatus.REVIEW)
    def test_nexus_context(self):
        v=MarkdownVault(ROOT/'vault'); c=ContextBuilder(v,KnowledgeGraph(v)).build('architecture autonomy'); self.assertGreaterEqual(len(c.notes),1)
    def test_path_policy(self):
        with tempfile.TemporaryDirectory() as d: self.assertTrue(PermissionEngine.validate_path(Path(d)/'x',[Path(d)]))
    def test_manifest_schema(self): AgentManifest.model_validate({'id':'demo','name':'Demo','team':'research','objective':'test'})
