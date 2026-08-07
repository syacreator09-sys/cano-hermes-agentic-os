"""C0 (plan de conexiones) -- tests de `scripts/build_key_registry.py`.

Todo corre sobre un vault y unos repos de prueba (tempdirs), nunca sobre el
vault real ni sobre `~/repos`. Cubre lo que pide el plan: detecta consumidor
real, no detecta substring-falso-positivo, preserva campos curados en una
segunda corrida, y `--check` detecta drift.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import build_key_registry as bkr


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class KeyRegistryTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.vault_path = self.root / "vault" / ".env"
        self.repos_root = self.root / "repos"
        self.registry_path = self.root / "config" / "key_registry.yaml"
        self.docs_path = self.root / "docs" / "KEY_REGISTRY.md"

    def write_vault(self, names: list[str]) -> None:
        body = "\n".join(f"{n}=whatever-value-not-read" for n in names)
        _write(self.vault_path, body + "\n")

    def build(self):
        return bkr.build_registry(self.vault_path, self.repos_root, self.registry_path)


class VaultNameParsingTests(KeyRegistryTestBase):
    def test_reads_names_only_ignores_comments_and_blanks(self):
        _write(
            self.vault_path,
            "\n".join(
                [
                    "FOO_API_KEY=super-secret-value",
                    "# BAR_TOKEN=also-secret  (comentada, no cuenta)",
                    "",
                    "  ",
                    "BAZ_URL=https://example.invalid",
                ]
            ),
        )
        unique, raw = bkr.read_vault_key_names(self.vault_path)
        self.assertEqual(unique, ["BAZ_URL", "FOO_API_KEY"])
        self.assertEqual(raw, ["FOO_API_KEY", "BAZ_URL"])

    def test_dedupes_repeated_names_but_reports_raw_count(self):
        _write(
            self.vault_path,
            "FOO_KEY=one\nFOO_KEY=two\nBAR_KEY=three\n",
        )
        unique, raw = bkr.read_vault_key_names(self.vault_path)
        self.assertEqual(unique, ["BAR_KEY", "FOO_KEY"])
        self.assertEqual(len(raw), 3)

    def test_never_returns_anything_resembling_a_value(self):
        # Si el parser tocara valores, "super-secret-value" aparecería aquí.
        _write(self.vault_path, "FOO_API_KEY=super-secret-value\n")
        unique, raw = bkr.read_vault_key_names(self.vault_path)
        joined = " ".join(unique + raw)
        self.assertNotIn("super-secret-value", joined)


class ConsumerDetectionTests(KeyRegistryTestBase):
    def test_detects_real_python_consumer(self):
        # Nombre de fantasía deliberado (no una llave real del vault): si
        # este test usara un nombre real (p.ej. NVIDIA_NIM_API_KEY), la
        # línea de fixture de abajo -- que vive en el código fuente de este
        # mismo repo -- se colaría como "consumidor real" al correr el
        # script contra el vault de verdad. Ver test_output_safety /
        # RealRepoSmokeTest, que sí corren contra el vault real.
        self.write_vault(["ACME_WIDGET_API_KEY"])
        _write(
            self.repos_root / "cano-hermes-agentic-os" / "cano_hermes" / "runtimes" / "foo.py",
            "import os\n"
            "\n"
            "def get_key():\n"
            "    return os.getenv('ACME_WIDGET_API_KEY')\n",
        )
        result = self.build()
        entry = next(e for e in result["entries"] if e["nombre"] == "ACME_WIDGET_API_KEY")
        self.assertEqual(len(entry["consumidores"]), 1)
        self.assertIn("cano-hermes-agentic-os/cano_hermes/runtimes/foo.py:4", entry["consumidores"][0])
        self.assertEqual(entry["dominio"], "starhome")

    def test_detects_real_js_consumer(self):
        self.write_vault(["ELEVENLABS_API_KEY"])
        _write(
            self.repos_root / "hermes-agent" / "lib" / "tts.mjs",
            "const key = process.env.ELEVENLABS_API_KEY;\n",
        )
        result = self.build()
        entry = next(e for e in result["entries"] if e["nombre"] == "ELEVENLABS_API_KEY")
        self.assertEqual(len(entry["consumidores"]), 1)
        self.assertIn("hermes-agent/lib/tts.mjs:1", entry["consumidores"][0])
        self.assertEqual(entry["dominio"], "starhome")

    def test_detects_environ_bracket_and_environ_get_variants(self):
        self.write_vault(["FOO_TOKEN", "BAR_TOKEN"])
        _write(
            self.repos_root / "factory-ia-channel-v5" / "app.py",
            "import os\n"
            "a = os.environ['FOO_TOKEN']\n"
            "b = os.environ.get('BAR_TOKEN')\n",
        )
        result = self.build()
        foo = next(e for e in result["entries"] if e["nombre"] == "FOO_TOKEN")
        bar = next(e for e in result["entries"] if e["nombre"] == "BAR_TOKEN")
        self.assertEqual(len(foo["consumidores"]), 1)
        self.assertEqual(len(bar["consumidores"]), 1)
        self.assertEqual(foo["dominio"], "factory-v5")

    def test_no_false_positive_from_substring_name(self):
        # El vault solo tiene MYKEY; el archivo referencia MYKEY_EXTRA (superstring)
        # y también usa "MYKEY" como texto libre fuera de una llamada os.getenv --
        # ninguno de los dos debe contar como consumidor de MYKEY.
        self.write_vault(["MYKEY"])
        _write(
            self.repos_root / "cano-hermes-agentic-os" / "noise.py",
            "import os\n"
            "x = os.getenv('MYKEY_EXTRA')\n"
            "# esto es solo un comentario sobre MYKEY, no una llamada real\n"
            "MYKEY = 'no es os.getenv, es una asignación cualquiera'\n",
        )
        result = self.build()
        entry = next(e for e in result["entries"] if e["nombre"] == "MYKEY")
        self.assertEqual(entry["consumidores"], [])
        self.assertEqual(entry["dominio"], "otro-proyecto")

    def test_excludes_vendor_and_build_dirs(self):
        self.write_vault(["VENDORED_KEY"])
        _write(
            self.repos_root / "hermes-agent" / "node_modules" / "somepkg" / "index.js",
            "process.env.VENDORED_KEY\n",
        )
        _write(
            self.repos_root / "hermes-agent" / ".venv" / "lib" / "x.py",
            "import os\nos.getenv('VENDORED_KEY')\n",
        )
        result = self.build()
        entry = next(e for e in result["entries"] if e["nombre"] == "VENDORED_KEY")
        self.assertEqual(entry["consumidores"], [])


class DomainClassificationTests(KeyRegistryTestBase):
    def test_vps_infra_prefix_without_consumer(self):
        self.write_vault(["MINIO_ACCESS_KEY", "CHATWOOT_TOKEN"])
        result = self.build()
        by_name = {e["nombre"]: e for e in result["entries"]}
        self.assertEqual(by_name["MINIO_ACCESS_KEY"]["dominio"], "vps-infra")
        self.assertEqual(by_name["CHATWOOT_TOKEN"]["dominio"], "vps-infra")

    def test_business_saas_without_consumer_is_otro_proyecto(self):
        self.write_vault(["RETELL_API_KEY", "STRIPE_SECRET_KEY"])
        result = self.build()
        by_name = {e["nombre"]: e for e in result["entries"]}
        self.assertEqual(by_name["RETELL_API_KEY"]["dominio"], "otro-proyecto")
        self.assertEqual(by_name["STRIPE_SECRET_KEY"]["dominio"], "otro-proyecto")

    def test_unclassified_key_flagged_for_review(self):
        self.write_vault(["SOME_RANDOM_THING"])
        result = self.build()
        entry = result["entries"][0]
        self.assertEqual(entry["dominio"], "otro-proyecto")
        self.assertIn("sin clasificar", entry["uso"])

    def test_starhome_takes_priority_over_factory(self):
        self.write_vault(["SHARED_KEY"])
        _write(
            self.repos_root / "cano-hermes-agentic-os" / "a.py",
            "import os\nos.getenv('SHARED_KEY')\n",
        )
        _write(
            self.repos_root / "factory-ia-channel-v5" / "b.py",
            "import os\nos.getenv('SHARED_KEY')\n",
        )
        result = self.build()
        entry = result["entries"][0]
        self.assertEqual(entry["dominio"], "starhome")


class RiskAndRotationTests(KeyRegistryTestBase):
    def test_risk_heuristic(self):
        self.write_vault(["FOO_SECRET", "FOO_PASSWORD", "FOO_TOKEN", "FOO_URL"])
        result = self.build()
        by_name = {e["nombre"]: e for e in result["entries"]}
        self.assertEqual(by_name["FOO_SECRET"]["riesgo"], "alto")
        self.assertEqual(by_name["FOO_PASSWORD"]["riesgo"], "alto")
        self.assertEqual(by_name["FOO_TOKEN"]["riesgo"], "medio")
        self.assertEqual(by_name["FOO_URL"]["riesgo"], "bajo")

    def test_kimi_and_nvidia_flagged_for_rotation(self):
        self.write_vault(["KIMI_API_KEY", "NVIDIA_NIM_API_KEY", "OTHER_KEY"])
        result = self.build()
        by_name = {e["nombre"]: e for e in result["entries"]}
        self.assertTrue(by_name["KIMI_API_KEY"]["rotacion_pendiente"])
        self.assertTrue(by_name["NVIDIA_NIM_API_KEY"]["rotacion_pendiente"])
        self.assertFalse(by_name["OTHER_KEY"]["rotacion_pendiente"])
        self.assertIn("transcript", by_name["KIMI_API_KEY"]["rotacion_motivo"])


class RerunPreservationTests(KeyRegistryTestBase):
    def test_curated_fields_survive_a_rerun_only_consumers_refresh(self):
        self.write_vault(["FOO_API_KEY"])
        result = self.build()
        bkr.write_yaml(result["entries"], self.registry_path)

        # Un humano cura el registro a mano.
        curated = bkr.load_existing_registry(self.registry_path)
        curated["FOO_API_KEY"]["dominio"] = "vps-infra"
        curated["FOO_API_KEY"]["uso"] = "curado a mano por Cano"
        curated["FOO_API_KEY"]["riesgo"] = "bajo"
        curated["FOO_API_KEY"]["rotacion_pendiente"] = True
        curated["FOO_API_KEY"]["rotacion_motivo"] = "motivo curado a mano"
        bkr.write_yaml(list(curated.values()), self.registry_path)

        # Ahora aparece un consumidor real en el repo -- una segunda corrida
        # debe refrescar SOLO `consumidores`, preservando lo curado.
        _write(
            self.repos_root / "cano-hermes-agentic-os" / "new_consumer.py",
            "import os\nos.getenv('FOO_API_KEY')\n",
        )
        second = self.build()
        entry = next(e for e in second["entries"] if e["nombre"] == "FOO_API_KEY")
        self.assertEqual(entry["dominio"], "vps-infra")
        self.assertEqual(entry["uso"], "curado a mano por Cano")
        self.assertEqual(entry["riesgo"], "bajo")
        self.assertTrue(entry["rotacion_pendiente"])
        self.assertEqual(entry["rotacion_motivo"], "motivo curado a mano")
        self.assertEqual(len(entry["consumidores"]), 1)

    def test_new_vault_key_gets_full_heuristic_on_second_run(self):
        self.write_vault(["FOO_API_KEY"])
        result = self.build()
        bkr.write_yaml(result["entries"], self.registry_path)

        self.write_vault(["FOO_API_KEY", "BRAND_NEW_SECRET"])
        second = self.build()
        names = {e["nombre"] for e in second["entries"]}
        self.assertEqual(names, {"FOO_API_KEY", "BRAND_NEW_SECRET"})
        new_entry = next(e for e in second["entries"] if e["nombre"] == "BRAND_NEW_SECRET")
        self.assertEqual(new_entry["riesgo"], "alto")

    def test_stale_entry_dropped_when_key_removed_from_vault(self):
        self.write_vault(["FOO_API_KEY", "SOON_GONE_KEY"])
        result = self.build()
        bkr.write_yaml(result["entries"], self.registry_path)

        self.write_vault(["FOO_API_KEY"])
        second = self.build()
        names = {e["nombre"] for e in second["entries"]}
        self.assertEqual(names, {"FOO_API_KEY"})
        self.assertEqual(second["stale_entries"], ["SOON_GONE_KEY"])


class CheckFlagTests(KeyRegistryTestBase):
    def test_check_reports_drift_and_nonzero_exit_when_registry_missing(self):
        self.write_vault(["FOO_API_KEY", "BAR_TOKEN"])
        code = bkr.main(
            [
                "--check",
                "--vault",
                str(self.vault_path),
                "--repos-root",
                str(self.repos_root),
                "--registry",
                str(self.registry_path),
            ]
        )
        self.assertEqual(code, 1)

    def test_check_exits_zero_when_synced(self):
        self.write_vault(["FOO_API_KEY", "BAR_TOKEN"])
        code = bkr.main(
            [
                "--vault",
                str(self.vault_path),
                "--repos-root",
                str(self.repos_root),
                "--registry",
                str(self.registry_path),
                "--docs",
                str(self.docs_path),
            ]
        )
        self.assertEqual(code, 0)
        self.assertTrue(self.registry_path.exists())
        self.assertTrue(self.docs_path.exists())

        code = bkr.main(
            [
                "--check",
                "--vault",
                str(self.vault_path),
                "--repos-root",
                str(self.repos_root),
                "--registry",
                str(self.registry_path),
            ]
        )
        self.assertEqual(code, 0)

    def test_check_detects_drift_after_vault_changes(self):
        self.write_vault(["FOO_API_KEY"])
        bkr.main(
            [
                "--vault",
                str(self.vault_path),
                "--repos-root",
                str(self.repos_root),
                "--registry",
                str(self.registry_path),
                "--no-docs",
            ]
        )
        self.write_vault(["FOO_API_KEY", "NEW_KEY_NOT_YET_REGISTERED"])
        code = bkr.main(
            [
                "--check",
                "--vault",
                str(self.vault_path),
                "--repos-root",
                str(self.repos_root),
                "--registry",
                str(self.registry_path),
            ]
        )
        self.assertEqual(code, 1)


class OutputSafetyTests(KeyRegistryTestBase):
    def test_no_value_ever_written_to_yaml_or_docs(self):
        self.write_vault(["TOP_SECRET_KEY"])
        secret_marker = "sk-this-must-never-appear-anywhere"
        _write(self.vault_path, f"TOP_SECRET_KEY={secret_marker}\n")
        bkr.main(
            [
                "--vault",
                str(self.vault_path),
                "--repos-root",
                str(self.repos_root),
                "--registry",
                str(self.registry_path),
                "--docs",
                str(self.docs_path),
            ]
        )
        yaml_text = self.registry_path.read_text(encoding="utf-8")
        docs_text = self.docs_path.read_text(encoding="utf-8")
        self.assertNotIn(secret_marker, yaml_text)
        self.assertNotIn(secret_marker, docs_text)


class RealRepoSmokeTest(unittest.TestCase):
    """Corre contra el vault real de solo lectura (nombres) y confirma que
    el registro escrito en el repo coincide con lo que produce el script
    hoy. No escribe nada -- solo recalcula y compara."""

    def test_registry_in_repo_matches_fresh_build(self):
        registry_path = bkr.DEFAULT_REGISTRY_PATH
        if not registry_path.exists() or not bkr.DEFAULT_VAULT_PATH.exists():
            self.skipTest("vault real o registro no disponibles en este entorno")
        result = bkr.build_registry(bkr.DEFAULT_VAULT_PATH, Path.home() / "repos", registry_path)
        self.assertEqual(result["vault_unique_count"], len(result["entries"]))
        self.assertEqual(result["new_entries"], [])
        self.assertEqual(result["stale_entries"], [])
