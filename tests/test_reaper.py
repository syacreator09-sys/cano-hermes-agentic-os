import tempfile, unittest
from pathlib import Path

from cano_hermes.domain.enums import TaskStatus
from cano_hermes.domain.models import TaskCreate
from cano_hermes.orchestration.conductor import Conductor
from cano_hermes.orchestration.task_engine import TaskEngine
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.registry.agents import AgentRegistry
from cano_hermes.storage.sqlite import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]


class ReaperTests(unittest.TestCase):
    def make_engine(self, d):
        return TaskEngine(
            SQLiteStore(f"sqlite:///{d}/db.sqlite"),
            Conductor(AgentRegistry(ROOT / "agents"), ModelRouter()),
        )

    def test_reap_orphaned_running_task_direct(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.make_engine(d)
            t = e.create(
                TaskCreate(title="Orphan me", objective="Simulate a crash mid-run", domain="engineering")
            )
            # Seed the task straight into RUNNING, as if a process died mid-execution.
            e.transition(t.id, TaskStatus.RUNNING, "worker")
            self.assertEqual(e.require(t.id).status, TaskStatus.RUNNING)

            reaped = e.reap_orphaned()

            self.assertEqual(len(reaped), 1)
            self.assertEqual(reaped[0].id, t.id)
            refreshed = e.require(t.id)
            self.assertEqual(refreshed.status, TaskStatus.FAILED)
            events = e.store.list_events(t.id)
            last = events[-1]
            self.assertEqual(last.kind, "task.failed")
            self.assertEqual(last.payload.get("reason"), "orphaned-on-restart")

    def test_reap_orphaned_leaves_other_statuses_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.make_engine(d)
            done = e.create(
                TaskCreate(title="Already done", objective="Should be left alone", domain="engineering")
            )
            e.transition(done.id, TaskStatus.DONE, "worker")

            reaped = e.reap_orphaned()

            self.assertEqual(reaped, [])
            self.assertEqual(e.require(done.id).status, TaskStatus.DONE)

    def test_reap_orphaned_via_app_lifespan(self):
        # NOTE: cano_hermes.config.settings is a module-level singleton read from
        # the environment once at import time, so flipping HERMES_DATABASE_URL this
        # late would be a no-op if config was already imported by another test
        # module. Mutate the singleton's attribute directly instead — that's what
        # dependencies.store()/engine() actually read at call time.
        from cano_hermes.config import settings as global_settings
        from cano_hermes.api.dependencies import engine, store
        from cano_hermes.api.app import app
        from fastapi.testclient import TestClient

        with tempfile.TemporaryDirectory() as d:
            original_url = global_settings.database_url
            global_settings.database_url = f"sqlite:///{d}/lifespan.db"
            engine.cache_clear()
            store.cache_clear()
            try:
                eng = engine()
                t = eng.create(
                    TaskCreate(title="Orphan via lifespan", objective="Crash before restart", domain="engineering")
                )
                eng.transition(t.id, TaskStatus.RUNNING, "worker")

                with TestClient(app):
                    pass  # entering/exiting the context runs the lifespan startup hook

                self.assertEqual(eng.require(t.id).status, TaskStatus.FAILED)
            finally:
                global_settings.database_url = original_url
                engine.cache_clear()
                store.cache_clear()


if __name__ == "__main__":
    unittest.main()
