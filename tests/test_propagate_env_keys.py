"""C2 (plan de conexiones) -- tests de `scripts/propagate_env_keys.py`.

Todo corre sobre un vault, un registro y unos repos de prueba (tempdirs),
nunca sobre el vault real ni sobre `~/repos`. Cubre lo que pide el plan:
nunca sobrescribe un valor existente, sí agrega llaves faltantes, respeta
`CONSUMER_REPO_NAMES`, nunca toca `cano-ai-command-center`, verifica
permisos 0600 y `git check-ignore`.
"""

from __future__ import annotations

import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts import propagate_env_keys as pek


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_git_repo(repo_root: Path, gitignore_has_env: bool = True) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo_root, check=True)
    if gitignore_has_env:
        _write(repo_root / ".gitignore", ".env\n")
    else:
        _write(repo_root / ".gitignore", "node_modules/\n")
    _write(repo_root / "README.md", "placeholder\n")
    subprocess.run(["git", "add", "-A"], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_root, check=True)


def _registry_entry(nombre: str, consumidores: list[str]) -> dict:
    return {
        "nombre": nombre,
        "proveedor": "Test",
        "dominio": "starhome",
        "uso": "prueba",
        "consumidores": consumidores,
        "validacion": "presence-only",
        "riesgo": "medio",
        "rotacion_pendiente": False,
        "rotacion_motivo": "",
    }


def _write_registry(registry_path: Path, entries: list[dict]) -> None:
    _write(
        registry_path,
        yaml.safe_dump({"llaves": entries}, sort_keys=False, allow_unicode=True),
    )


class PropagateTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.vault_path = self.root / "vault" / ".env"
        self.repos_root = self.root / "repos"
        self.registry_path = self.root / "config" / "key_registry.yaml"

    def write_vault(self, pairs: dict[str, str]) -> None:
        body = "\n".join(f"{k}={v}" for k, v in pairs.items())
        _write(self.vault_path, body + "\n")

    def init_repo(self, name: str, gitignore_has_env: bool = True) -> Path:
        repo_root = self.repos_root / name
        _init_git_repo(repo_root, gitignore_has_env=gitignore_has_env)
        return repo_root


class NeededKeysByRepoTests(PropagateTestBase):
    def test_respects_consumer_repo_names_allowlist(self):
        entries = [
            _registry_entry("FOO_KEY", ["cano-hermes-agentic-os/x.py:1"]),
            _registry_entry("BAR_KEY", ["cano-ai-command-center/y.py:1"]),
        ]
        needed = pek.needed_keys_by_repo(entries)
        self.assertIn("cano-hermes-agentic-os", needed)
        self.assertNotIn("cano-ai-command-center", needed)
        self.assertNotIn("BAR_KEY", needed.get("cano-hermes-agentic-os", set()))

    def test_never_surfaces_command_center_even_indirectly(self):
        # Aunque una entrada tuviera command-center MEZCLADO con un repo real,
        # command-center nunca debe aparecer como clave de `needed`.
        entries = [
            _registry_entry(
                "MIXED_KEY",
                [
                    "cano-ai-command-center/a.py:1",
                    "hermes-agent/b.py:2",
                ],
            ),
        ]
        needed = pek.needed_keys_by_repo(entries)
        self.assertEqual(set(needed.keys()), {"hermes-agent"})
        self.assertNotIn("cano-ai-command-center", needed)

    def test_entries_without_consumers_are_ignored(self):
        entries = [_registry_entry("ORPHAN_KEY", [])]
        needed = pek.needed_keys_by_repo(entries)
        self.assertEqual(needed, {})


class PlanRepoTests(PropagateTestBase):
    def test_adds_missing_key_from_vault(self):
        self.write_vault({"FOO_KEY": "real-value-123"})
        repo_root = self.init_repo("cano-hermes-agentic-os")
        _write(repo_root / ".env", "OTHER_KEY=already-here\n")

        plan = pek.plan_repo(
            "cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"},
            pek.read_vault_entries(self.vault_path),
        )
        self.assertEqual(plan.to_add, ["FOO_KEY"])
        self.assertEqual(plan.to_sanitize, [])
        self.assertTrue(plan.has_writes)

    def test_never_overwrites_existing_value_even_if_different_from_vault(self):
        self.write_vault({"FOO_KEY": "vault-value"})
        repo_root = self.init_repo("cano-hermes-agentic-os")
        _write(repo_root / ".env", "FOO_KEY=repo-already-has-this-value\n")

        plan = pek.plan_repo(
            "cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"},
            pek.read_vault_entries(self.vault_path),
        )
        self.assertEqual(plan.to_add, [])
        self.assertEqual(plan.to_sanitize, [])
        self.assertFalse(plan.has_writes)

        # Confirmar también tras un apply real: el archivo no cambia.
        before = (repo_root / ".env").read_text(encoding="utf-8")
        result = pek.apply_plan(plan, self.repos_root, pek.read_vault_entries(self.vault_path))
        after = (repo_root / ".env").read_text(encoding="utf-8")
        self.assertEqual(before, after)
        self.assertEqual(result.added, 0)
        self.assertEqual(result.critical_error, "")

    def test_missing_from_vault_is_reported_never_invented(self):
        self.write_vault({})  # vault vacío
        repo_root = self.init_repo("cano-hermes-agentic-os")
        _write(repo_root / ".env", "OTHER=1\n")

        plan = pek.plan_repo(
            "cano-hermes-agentic-os", self.repos_root, {"GHOST_KEY"},
            pek.read_vault_entries(self.vault_path),
        )
        self.assertEqual(plan.to_add, [])
        self.assertEqual(plan.missing_from_vault, ["GHOST_KEY"])
        self.assertFalse(plan.has_writes)


class PlaceholderSanitizationTests(PropagateTestBase):
    def test_sanitizes_placeholder_when_vault_has_real_value(self):
        self.write_vault({"FOO_KEY": "sk-real-usable-value"})
        repo_root = self.init_repo("cano-hermes-agentic-os")
        _write(repo_root / ".env", "FOO_KEY=changeme\n")

        vault_entries = pek.read_vault_entries(self.vault_path)
        plan = pek.plan_repo("cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"}, vault_entries)
        self.assertEqual(plan.to_sanitize, ["FOO_KEY"])
        self.assertEqual(plan.placeholder_unfixable, [])

        result = pek.apply_plan(plan, self.repos_root, vault_entries)
        self.assertEqual(result.sanitized, 1)
        content = (repo_root / ".env").read_text(encoding="utf-8")
        self.assertIn("FOO_KEY=sk-real-usable-value", content)
        self.assertNotIn("changeme", content)

    def test_leaves_placeholder_alone_when_vault_also_placeholder(self):
        self.write_vault({"FOO_KEY": "xxxx"})
        repo_root = self.init_repo("cano-hermes-agentic-os")
        _write(repo_root / ".env", "FOO_KEY=changeme\n")

        vault_entries = pek.read_vault_entries(self.vault_path)
        plan = pek.plan_repo("cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"}, vault_entries)
        self.assertEqual(plan.to_sanitize, [])
        self.assertEqual(plan.placeholder_unfixable, ["FOO_KEY"])

        before = (repo_root / ".env").read_text(encoding="utf-8")
        pek.apply_plan(plan, self.repos_root, vault_entries)
        after = (repo_root / ".env").read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_leaves_placeholder_alone_when_vault_missing_key(self):
        self.write_vault({})
        repo_root = self.init_repo("cano-hermes-agentic-os")
        _write(repo_root / ".env", "FOO_KEY=todo\n")

        vault_entries = pek.read_vault_entries(self.vault_path)
        plan = pek.plan_repo("cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"}, vault_entries)
        self.assertEqual(plan.to_sanitize, [])
        self.assertEqual(plan.placeholder_unfixable, ["FOO_KEY"])


class EnvCreationTests(PropagateTestBase):
    def test_creates_env_only_when_something_to_propagate(self):
        self.write_vault({"FOO_KEY": "value-1"})
        repo_root = self.init_repo("ugc-commerce-studio")
        env_path = repo_root / ".env"
        self.assertFalse(env_path.exists())

        vault_entries = pek.read_vault_entries(self.vault_path)
        plan = pek.plan_repo("ugc-commerce-studio", self.repos_root, {"FOO_KEY"}, vault_entries)
        result = pek.apply_plan(plan, self.repos_root, vault_entries)

        self.assertTrue(env_path.exists())
        self.assertTrue(result.created_env)
        self.assertIn("FOO_KEY=value-1", env_path.read_text(encoding="utf-8"))

    def test_does_not_create_env_when_nothing_needed(self):
        repo_root = self.init_repo("ugc-commerce-studio")
        env_path = repo_root / ".env"

        plan = pek.plan_repo("ugc-commerce-studio", self.repos_root, set(), {})
        self.assertFalse(plan.has_writes)
        pek.apply_plan(plan, self.repos_root, {})
        self.assertFalse(env_path.exists())


class PermissionsTests(PropagateTestBase):
    def test_created_env_has_0600_permissions(self):
        self.write_vault({"FOO_KEY": "value-1"})
        repo_root = self.init_repo("cano-hermes-agentic-os")
        vault_entries = pek.read_vault_entries(self.vault_path)
        plan = pek.plan_repo("cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"}, vault_entries)
        pek.apply_plan(plan, self.repos_root, vault_entries)

        mode = stat.S_IMODE((repo_root / ".env").stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_existing_env_gets_permissions_fixed_to_0600(self):
        self.write_vault({"FOO_KEY": "value-1"})
        repo_root = self.init_repo("cano-hermes-agentic-os")
        env_path = repo_root / ".env"
        _write(env_path, "OTHER=1\n")
        env_path.chmod(0o644)

        vault_entries = pek.read_vault_entries(self.vault_path)
        plan = pek.plan_repo("cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"}, vault_entries)
        pek.apply_plan(plan, self.repos_root, vault_entries)

        mode = stat.S_IMODE(env_path.stat().st_mode)
        self.assertEqual(mode, 0o600)


class GitCheckIgnoreTests(PropagateTestBase):
    def test_aborts_write_when_env_not_gitignored(self):
        self.write_vault({"FOO_KEY": "value-1"})
        repo_root = self.init_repo("cano-hermes-agentic-os", gitignore_has_env=False)
        env_path = repo_root / ".env"

        vault_entries = pek.read_vault_entries(self.vault_path)
        plan = pek.plan_repo("cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"}, vault_entries)
        self.assertTrue(plan.has_writes)

        result = pek.apply_plan(plan, self.repos_root, vault_entries)
        self.assertNotEqual(result.critical_error, "")
        self.assertFalse(env_path.exists())  # nunca se creó/escribió

    def test_writes_when_env_is_gitignored(self):
        self.write_vault({"FOO_KEY": "value-1"})
        repo_root = self.init_repo("cano-hermes-agentic-os", gitignore_has_env=True)

        vault_entries = pek.read_vault_entries(self.vault_path)
        plan = pek.plan_repo("cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"}, vault_entries)
        result = pek.apply_plan(plan, self.repos_root, vault_entries)

        self.assertEqual(result.critical_error, "")
        self.assertTrue((repo_root / ".env").exists())


class DryRunSafetyTests(PropagateTestBase):
    def test_plan_all_never_writes_anything(self):
        self.write_vault({"FOO_KEY": "value-1"})
        repo_root = self.init_repo("cano-hermes-agentic-os")
        env_path = repo_root / ".env"
        _write_registry(
            self.registry_path,
            [_registry_entry("FOO_KEY", ["cano-hermes-agentic-os/x.py:1"])],
        )

        plans = pek.plan_all(self.registry_path, self.vault_path, self.repos_root)
        self.assertFalse(env_path.exists())  # dry-run: nada se escribió ni se creó
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].to_add, ["FOO_KEY"])

    def test_repo_missing_on_disk_is_reported_not_crashed(self):
        _write_registry(
            self.registry_path,
            [_registry_entry("FOO_KEY", ["amazon-fba-product-hunter/x.py:1"])],
        )
        self.write_vault({"FOO_KEY": "value-1"})
        plans = pek.plan_all(self.registry_path, self.vault_path, self.repos_root)
        self.assertEqual(len(plans), 1)
        self.assertTrue(plans[0].repo_missing_on_disk)

        result = pek.apply_plan(plans[0], self.repos_root, {"FOO_KEY": "value-1"})
        self.assertNotEqual(result.critical_error, "")


class OutputSafetyTests(PropagateTestBase):
    def test_report_and_summary_never_contain_values(self):
        self.write_vault({"FOO_KEY": "super-secret-value-should-never-leak"})
        repo_root = self.init_repo("cano-hermes-agentic-os")
        vault_entries = pek.read_vault_entries(self.vault_path)
        plan = pek.plan_repo("cano-hermes-agentic-os", self.repos_root, {"FOO_KEY"}, vault_entries)
        result = pek.apply_plan(plan, self.repos_root, vault_entries)

        report = pek.render_report([plan], "apply")
        summary = pek.render_summary([result])
        self.assertNotIn("super-secret-value-should-never-leak", report)
        self.assertNotIn("super-secret-value-should-never-leak", summary)


if __name__ == "__main__":
    unittest.main()
