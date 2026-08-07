"""P0 (plan POTENCIA, 2026-08-07) -- "cablear lo muerto": routing real.

Covers: (a) the 6 previously-orphan teams are reachable through
`DOMAIN_TEAMS` under their agreed domain names (+ the `trading` and
`personal` aliases); (b) every `TEAM_TO_KANBAN_PROFILE` value is a real
office (an `offices/<profile>/office.yaml` exists -- no `team-*`
placeholders survive) and Docker-backed profiles resolve through
`office_launcher.PROFILE_TO_OFFICE`; (c) `Conductor.assign` end-to-end:
each newly-routable domain lands on an assignable (approved/active) agent
of the right team and carries the right kanban profile; (d) teams
deliberately left without a kanban profile (engineering, governance
fallback, the native personal teams) yield `kanban_profile=None` without
breaking assignment.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from cano_hermes.bridge.office_launcher import PROFILE_TO_OFFICE
from cano_hermes.domain.models import TaskRecord
from cano_hermes.intelligence.router import ModelRouter
from cano_hermes.orchestration.conductor import (
    DOMAIN_TEAMS,
    TEAM_TO_KANBAN_PROFILE,
    Conductor,
    kanban_profile_for_domain,
)
from cano_hermes.registry.agents import AgentRegistry

ROOT = Path(__file__).resolve().parents[1]
OFFICES_ROOT = ROOT / "offices"

# Profiles that are real offices but run natively (no Docker container) --
# mirrors office_launcher's own docstring: these must NOT be in
# PROFILE_TO_OFFICE.
NATIVE_PROFILES = {"hermes-research", "hermes-guiones", "hermes-ads"}  # hermes-ads: P2, folder-isolated


class DomainTeamsTests(unittest.TestCase):
    def test_new_domains_reach_their_teams(self):
        cases = {
            "investments": "investments",
            "trading": "investments",
            "revenue": "revenue",
            "documents": "documents",
            "learning": "learning",
            "personal-operations": "personal-operations",
            "personal": "personal-operations",
            "projects": "projects",
        }
        for domain, team in cases.items():
            with self.subTest(domain=domain):
                self.assertEqual(DOMAIN_TEAMS[domain], team)

    def test_pre_p0_domains_unchanged(self):
        for domain, team in {
            "engineering": "engineering",
            "research": "research",
            "content": "content",
            "operations": "operations",
            "forge": "forge",
            "security": "governance",
            "finance": "finance",
        }.items():
            with self.subTest(domain=domain):
                self.assertEqual(DOMAIN_TEAMS[domain], team)


class KanbanProfileMapTests(unittest.TestCase):
    def test_no_placeholder_profiles_remain(self):
        for team, profile in TEAM_TO_KANBAN_PROFILE.items():
            with self.subTest(team=team):
                self.assertFalse(profile.startswith("team-"))

    def test_every_profile_is_a_real_office(self):
        """Each mapped profile must have a real office.yaml -- this is what
        lets `auto_approval.load_office_never` enforce the office's
        `never:` list on tasks routed there."""
        for team, profile in TEAM_TO_KANBAN_PROFILE.items():
            with self.subTest(team=team, profile=profile):
                self.assertTrue((OFFICES_ROOT / profile / "office.yaml").is_file())

    def test_docker_profiles_resolve_to_containers(self):
        """Every mapped profile is either Docker-backed (launchable via
        PROFILE_TO_OFFICE) or one of the known native profiles."""
        for team, profile in TEAM_TO_KANBAN_PROFILE.items():
            with self.subTest(team=team, profile=profile):
                self.assertTrue(profile in PROFILE_TO_OFFICE or profile in NATIVE_PROFILES)

    def test_team_to_profile_decisions(self):
        self.assertEqual(TEAM_TO_KANBAN_PROFILE["content"], "hermes-produccion")
        self.assertEqual(TEAM_TO_KANBAN_PROFILE["forge"], "hermes-ugc")
        self.assertEqual(TEAM_TO_KANBAN_PROFILE["finance"], "hermes-monitor")
        self.assertEqual(TEAM_TO_KANBAN_PROFILE["investments"], "hermes-market-intel")
        self.assertEqual(TEAM_TO_KANBAN_PROFILE["research"], "hermes-research")
        self.assertEqual(TEAM_TO_KANBAN_PROFILE["operations"], "hermes-monitor")

    def test_teams_without_profile_on_purpose(self):
        for team in ("engineering", "governance", "revenue", "documents",
                     "learning", "personal-operations", "projects"):
            with self.subTest(team=team):
                self.assertNotIn(team, TEAM_TO_KANBAN_PROFILE)

    def test_kanban_profile_for_domain_standalone(self):
        self.assertEqual(kanban_profile_for_domain("content"), "hermes-produccion")
        self.assertEqual(kanban_profile_for_domain("trading"), "hermes-market-intel")
        self.assertIsNone(kanban_profile_for_domain("engineering"))
        self.assertIsNone(kanban_profile_for_domain("projects"))
        self.assertIsNone(kanban_profile_for_domain("totally-unknown"))


class ConductorEndToEndTests(unittest.TestCase):
    """Dry-run of the actual assignment decision -- no execution."""

    def setUp(self):
        self.conductor = Conductor(AgentRegistry(ROOT / "agents"), ModelRouter())

    def _assign(self, domain: str):
        task = TaskRecord(title="P0 probe", objective="routing dry-run", domain=domain)
        return self.conductor.assign(task)

    def test_new_domains_land_on_their_team_agents(self):
        """Each newly-routable team has at least one approved/active agent
        after the P0 triage, so assignment must NOT fall back to
        task-governor."""
        cases = {
            "investments": ("investment-intelligence", "hermes-market-intel"),
            "trading": ("investment-intelligence", "hermes-market-intel"),
            "revenue": ("revenue-operator", None),
            "documents": ("document-auditor", None),
            "learning": ("learning-coach", None),
            "personal": ("chief-of-staff", None),
            "projects": ("project-operator", None),
        }
        for domain, (agent_id, profile) in cases.items():
            with self.subTest(domain=domain):
                assignment = self._assign(domain)
                self.assertEqual(assignment.agent_id, agent_id)
                self.assertEqual(assignment.kanban_profile, profile)

    def test_docker_office_domains(self):
        for domain, profile in {
            "content": "hermes-produccion",
            "forge": "hermes-ugc",
            "finance": "hermes-monitor",
            "operations": "hermes-monitor",
        }.items():
            with self.subTest(domain=domain):
                self.assertEqual(self._assign(domain).kanban_profile, profile)

    def test_engineering_and_unknown_have_no_office(self):
        self.assertIsNone(self._assign("engineering").kanban_profile)
        self.assertIsNone(self._assign("no-such-domain").kanban_profile)


if __name__ == "__main__":
    unittest.main()
