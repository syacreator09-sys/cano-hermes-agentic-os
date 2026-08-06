"""K9 (plan HERMES-KICKOFF, gaps 12/13) -- bridge/office_launcher.py.

Every test here mocks `cano_hermes.bridge.office_launcher.subprocess.run` --
none of them shell out to a real `docker` process (mirrors K6's
`test_k6_kanban_bridge.py` pattern for `hermes kanban`).
"""

from __future__ import annotations

import json
import subprocess
import unittest
from unittest.mock import patch

from cano_hermes.bridge.office_launcher import (
    KNOWN_OFFICES,
    PROFILE_TO_OFFICE,
    OfficeLauncher,
    OfficeLauncherError,
    ensure_office_for_profile,
)


def _completed(returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["docker", "compose"], returncode=returncode, stdout=stdout, stderr=stderr)


def _ps_json(*services: str) -> str:
    return "\n".join(json.dumps({"Service": f"office-{s}", "State": "running"}) for s in services)


class ActiveTests(unittest.TestCase):
    def test_empty_when_nothing_running(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.return_value = _completed(stdout="")
            self.assertEqual(OfficeLauncher().active(), frozenset())

    def test_parses_known_offices_from_ps_json(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.return_value = _completed(stdout=_ps_json("analytics", "ugc"))
            self.assertEqual(OfficeLauncher().active(), frozenset({"analytics", "ugc"}))

    def test_ignores_services_outside_known_offices(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.return_value = _completed(stdout=_ps_json("analytics") + "\n" + json.dumps({"Service": "some-other-thing"}))
            self.assertEqual(OfficeLauncher().active(), frozenset({"analytics"}))

    def test_nonzero_exit_raises(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.return_value = _completed(returncode=1, stderr="boom")
            with self.assertRaises(OfficeLauncherError):
                OfficeLauncher().active()


class StartTests(unittest.TestCase):
    def test_unknown_office_rejected(self):
        with self.assertRaises(OfficeLauncherError):
            OfficeLauncher().start("not-a-real-office")

    def test_already_running_is_a_noop(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.return_value = _completed(stdout=_ps_json("analytics"))
            result = OfficeLauncher().start("analytics")
        self.assertEqual(result.action, "already_running")
        fake_run.assert_called_once()  # only the `ps` probe, never `up`

    def test_starts_when_under_cap(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.side_effect = [
                _completed(stdout=""),  # active() before start
                _completed(returncode=0),  # up -d
                _completed(stdout=_ps_json("ugc")),  # active() after start
            ]
            result = OfficeLauncher().start("ugc")
        self.assertEqual(result.action, "started")
        self.assertEqual(result.active_offices, frozenset({"ugc"}))
        up_call = fake_run.call_args_list[1][0][0]
        self.assertIn("--profile", up_call)
        self.assertIn("ugc", up_call)
        self.assertIn("up", up_call)

    def test_third_office_rejected_at_cap_of_two(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.return_value = _completed(stdout=_ps_json("analytics", "ugc"))
            with self.assertRaises(OfficeLauncherError) as ctx:
                OfficeLauncher(max_active=2).start("content")
        self.assertIn("techo", str(ctx.exception))

    def test_custom_cap_of_one(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.return_value = _completed(stdout=_ps_json("analytics"))
            with self.assertRaises(OfficeLauncherError):
                OfficeLauncher(max_active=1).start("ugc")

    def test_compose_failure_raises(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.side_effect = [
                _completed(stdout=""),
                _completed(returncode=1, stderr="build failed"),
            ]
            with self.assertRaises(OfficeLauncherError) as ctx:
                OfficeLauncher().start("analytics")
        self.assertIn("build failed", str(ctx.exception))


class StopTests(unittest.TestCase):
    def test_not_running_is_a_noop(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.return_value = _completed(stdout="")
            result = OfficeLauncher().stop("analytics")
        self.assertEqual(result.action, "not_running")
        fake_run.assert_called_once()

    def test_stops_running_office(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.side_effect = [
                _completed(stdout=_ps_json("analytics")),
                _completed(returncode=0),
                _completed(stdout=""),
            ]
            result = OfficeLauncher().stop("analytics")
        self.assertEqual(result.action, "stopped")
        self.assertEqual(result.active_offices, frozenset())
        down_call = fake_run.call_args_list[1][0][0]
        self.assertIn("down", down_call)


class EnsureOfficeForProfileTests(unittest.TestCase):
    def test_returns_none_for_native_profile(self):
        # hermes-research/hermes-guiones have no Docker office (folder isolation)
        self.assertIsNone(ensure_office_for_profile("hermes-research"))
        self.assertIsNone(ensure_office_for_profile("hermes-guiones"))

    def test_returns_none_for_unknown_profile(self):
        self.assertIsNone(ensure_office_for_profile("some-made-up-profile"))

    def test_starts_the_mapped_office(self):
        with patch("cano_hermes.bridge.office_launcher.subprocess.run") as fake_run:
            fake_run.side_effect = [
                _completed(stdout=""),
                _completed(returncode=0),
                _completed(stdout=_ps_json("ugc")),
            ]
            result = ensure_office_for_profile("hermes-ugc")
        self.assertIsNotNone(result)
        self.assertEqual(result.office, "ugc")

    def test_mapping_covers_the_5_docker_offices(self):
        self.assertEqual(
            set(PROFILE_TO_OFFICE.values()),
            {"analytics", "ugc", "content", "publish", "market-intel"},
        )
        self.assertEqual(KNOWN_OFFICES, frozenset(PROFILE_TO_OFFICE.values()))


if __name__ == "__main__":
    unittest.main()
