"""Plan POTENCIA T9 -- scripts/guion_to_videovox.py (conversor determinista
short-script.yaml -> scenes.json de video-vox). La escritura real del guion
(scripts/write_guion.py, que invoca hermes --oneshot) se verificó a mano en
vivo (ver storage/workspaces/guiones/2026-08-07/cano-digital-ia.scenes.json,
5 escenas reales generadas por Kimi, costo $0) -- este archivo cubre solo la
parte determinista y testeable: validación + conversión."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import guion_to_videovox as gv  # noqa: E402

VALID_GUION = {
    "title": "T",
    "music_prompt": "M",
    "hook": {"keyword": "K1", "narration": "N1", "image_prompt": "I1", "from": "left"},
    "beats": [
        {"keyword": "K2", "narration": "N2", "image_prompt": "I2"},
        {"keyword": "K3", "narration": "N3", "image_prompt": "I3", "from": "right"},
    ],
    "payoff": {"keyword": "K4", "narration": "N4", "image_prompt": "I4"},
}


class ParseGuionTests(unittest.TestCase):
    def test_valid_guion_parses(self):
        result = gv.parse_guion(VALID_GUION)
        self.assertEqual(result["title"], "T")

    def test_missing_title(self):
        bad = {**VALID_GUION, "title": ""}
        with self.assertRaises(gv.GuionValidationError):
            gv.parse_guion(bad)

    def test_missing_hook(self):
        bad = {k: v for k, v in VALID_GUION.items() if k != "hook"}
        with self.assertRaises(gv.GuionValidationError):
            gv.parse_guion(bad)

    def test_empty_beats(self):
        bad = {**VALID_GUION, "beats": []}
        with self.assertRaises(gv.GuionValidationError):
            gv.parse_guion(bad)

    def test_beat_missing_required_field(self):
        bad = {**VALID_GUION, "beats": [{"keyword": "K", "narration": "N"}]}  # sin image_prompt
        with self.assertRaises(gv.GuionValidationError):
            gv.parse_guion(bad)


class ToScenesJsonTests(unittest.TestCase):
    def test_flattens_hook_beats_payoff_in_order(self):
        guion = gv.parse_guion(VALID_GUION)
        scenes_json = gv.to_scenes_json(guion)
        self.assertEqual(scenes_json["title"], "T")
        self.assertEqual(scenes_json["musicPrompt"], "M")
        ids = [s["id"] for s in scenes_json["scenes"]]
        self.assertEqual(ids, ["01", "02", "03", "04"])
        keywords = [s["keyword"] for s in scenes_json["scenes"]]
        self.assertEqual(keywords, ["K1", "K2", "K3", "K4"])

    def test_explicit_from_is_preserved(self):
        guion = gv.parse_guion(VALID_GUION)
        scenes_json = gv.to_scenes_json(guion)
        self.assertEqual(scenes_json["scenes"][0]["from"], "left")
        self.assertEqual(scenes_json["scenes"][2]["from"], "right")

    def test_missing_from_cycles_default(self):
        guion = gv.parse_guion(VALID_GUION)
        scenes_json = gv.to_scenes_json(guion)
        # beats[0] (indice 1 global) sin 'from' -> cae al ciclo default (bottom)
        self.assertEqual(scenes_json["scenes"][1]["from"], "bottom")

    def test_output_matches_real_videovox_shape(self):
        """Confirma que las claves son EXACTAMENTE las que
        cano-video-vox/src/data/short.json usa de verdad (title,
        musicPrompt, scenes[].{id,keyword,narration,imagePrompt,from})."""
        guion = gv.parse_guion(VALID_GUION)
        scenes_json = gv.to_scenes_json(guion)
        self.assertEqual(set(scenes_json.keys()), {"title", "musicPrompt", "scenes"})
        for scene in scenes_json["scenes"]:
            self.assertEqual(set(scene.keys()), {"id", "keyword", "narration", "imagePrompt", "from"})


VALID_GUION_LARGO = {
    "title": "T largo",
    "music_prompt": "M largo",
    "hook": {"keyword": "K1", "narration": "N1", "image_prompt": "I1", "from": "left"},
    "context": {"keyword": "K2", "narration": "N2", "image_prompt": "I2"},
    "claims": {"keyword": "K3", "narration": "N3", "image_prompt": "I3"},
    "evidence": {"keyword": "K4", "narration": "N4", "image_prompt": "I4"},
    "counterpoint": {"keyword": "K5", "narration": "N5", "image_prompt": "I5"},
    "conclusion": {"keyword": "K6", "narration": "N6", "image_prompt": "I6"},
}


class ParseGuionLargoTests(unittest.TestCase):
    """A4 (plan AUTONOMÍA TOTAL, 2026-08-08) -- long-form validation."""

    def test_valid_guion_largo_parses(self):
        result = gv.parse_guion_largo(VALID_GUION_LARGO)
        self.assertEqual(result["title"], "T largo")

    def test_missing_beat_raises(self):
        bad = {k: v for k, v in VALID_GUION_LARGO.items() if k != "evidence"}
        with self.assertRaises(gv.GuionValidationError):
            gv.parse_guion_largo(bad)

    def test_beat_missing_required_field(self):
        bad = {**VALID_GUION_LARGO, "claims": {"keyword": "K", "narration": "N"}}  # sin image_prompt
        with self.assertRaises(gv.GuionValidationError):
            gv.parse_guion_largo(bad)

    def test_missing_title(self):
        bad = {**VALID_GUION_LARGO, "title": ""}
        with self.assertRaises(gv.GuionValidationError):
            gv.parse_guion_largo(bad)


class ToScenesJsonLargoTests(unittest.TestCase):
    def test_flattens_six_beats_in_order_with_beat_field(self):
        guion = gv.parse_guion_largo(VALID_GUION_LARGO)
        scenes_json = gv.to_scenes_json_largo(guion)
        ids = [s["id"] for s in scenes_json["scenes"]]
        self.assertEqual(ids, ["01", "02", "03", "04", "05", "06"])
        beats = [s["beat"] for s in scenes_json["scenes"]]
        self.assertEqual(beats, list(gv.BEATS_LARGO))
        keywords = [s["keyword"] for s in scenes_json["scenes"]]
        self.assertEqual(keywords, ["K1", "K2", "K3", "K4", "K5", "K6"])

    def test_output_matches_real_videovox_long_shape(self):
        """Confirma que las claves coinciden EXACTAMENTE con las que
        cano-video-vox/src/data/long.json usa de verdad para el campo
        "beat" por escena (id, beat, keyword, narration, imagePrompt,
        from -- audio/image/durationInFrames los añade
        gen-video-assets.mjs en la etapa siguiente, no este conversor)."""
        guion = gv.parse_guion_largo(VALID_GUION_LARGO)
        scenes_json = gv.to_scenes_json_largo(guion)
        self.assertEqual(set(scenes_json.keys()), {"title", "musicPrompt", "scenes"})
        for scene in scenes_json["scenes"]:
            self.assertEqual(set(scene.keys()), {"id", "beat", "keyword", "narration", "imagePrompt", "from"})


class ConvertFileLargoTests(unittest.TestCase):
    def test_convert_file_formato_largo_writes_valid_json_with_beats(self):
        import tempfile
        import yaml as _yaml
        with tempfile.TemporaryDirectory() as tmp:
            guion_path = Path(tmp) / "guion-largo.yaml"
            out_path = Path(tmp) / "out" / "scenes.json"
            guion_path.write_text(_yaml.safe_dump(VALID_GUION_LARGO), encoding="utf-8")
            result = gv.convert_file(guion_path, out_path, formato="largo")
            self.assertTrue(out_path.exists())
            on_disk = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk, result)
            self.assertEqual(len(on_disk["scenes"]), 6)

    def test_convert_file_default_formato_is_corto_unchanged(self):
        """formato="corto" (el default) debe seguir produciendo exactamente
        lo mismo que antes de A4 -- ninguna regresión en el camino short."""
        import tempfile
        import yaml as _yaml
        with tempfile.TemporaryDirectory() as tmp:
            guion_path = Path(tmp) / "guion.yaml"
            out_path = Path(tmp) / "out" / "scenes.json"
            guion_path.write_text(_yaml.safe_dump(VALID_GUION), encoding="utf-8")
            result = gv.convert_file(guion_path, out_path)
            self.assertEqual(len(result["scenes"]), 4)
            self.assertNotIn("beat", result["scenes"][0])


class ConvertFileTests(unittest.TestCase):
    def test_convert_file_writes_valid_json(self):
        import tempfile
        import yaml as _yaml
        with tempfile.TemporaryDirectory() as tmp:
            guion_path = Path(tmp) / "guion.yaml"
            out_path = Path(tmp) / "out" / "scenes.json"
            guion_path.write_text(_yaml.safe_dump(VALID_GUION), encoding="utf-8")
            result = gv.convert_file(guion_path, out_path)
            self.assertTrue(out_path.exists())
            on_disk = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(on_disk, result)


if __name__ == "__main__":
    unittest.main()
