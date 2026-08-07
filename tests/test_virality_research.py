"""Plan POTENCIA P4-B -- scripts/virality_research.py.

Todo mockeado (urllib.request.urlopen nunca se llama de verdad); la
verificación con red real (Apify + engine de factory-v5) se hizo a mano
como smoke test (ver reports/virality/2026-08-07.md) antes de escribir
estos tests, no se repite aquí -- este archivo cubre la lógica pura:
parseo de duración, clasificación de formato, normalización por
plataforma, rotación (round-robin + exclusión + agote), stub de Supadata,
y lectura segura del vault (nunca el valor real).
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import virality_research as vr  # noqa: E402


class DurationParsingTests(unittest.TestCase):
    def test_numeric_seconds(self):
        self.assertEqual(vr._parse_duration(45), 45.0)
        self.assertEqual(vr._parse_duration(45.5), 45.5)

    def test_hh_mm_ss_string(self):
        self.assertEqual(vr._parse_duration("02:00:50"), 2 * 3600 + 50)

    def test_mm_ss_string(self):
        self.assertEqual(vr._parse_duration("01:05"), 65.0)

    def test_none_or_empty(self):
        self.assertEqual(vr._parse_duration(None), 0.0)
        self.assertEqual(vr._parse_duration(""), 0.0)

    def test_garbage_string_degrades_to_zero(self):
        self.assertEqual(vr._parse_duration("no-a-duration"), 0.0)


class FormatClassificationTests(unittest.TestCase):
    def test_youtube_short(self):
        self.assertEqual(vr.classify_format("youtube", 45), "corto")

    def test_youtube_long(self):
        self.assertEqual(vr.classify_format("youtube", 600), "largo")

    def test_tiktok_is_reel_regardless_of_duration(self):
        self.assertEqual(vr.classify_format("tiktok", 5), "reel")
        self.assertEqual(vr.classify_format("tiktok", 500), "reel")

    def test_instagram_carousel_overrides_duration(self):
        self.assertEqual(vr.classify_format("instagram", 30, is_carousel=True), "carrusel")


class NormalizeTests(unittest.TestCase):
    def test_normalize_youtube_real_shape(self):
        item = vr._normalize_youtube({
            "id": "abc", "url": "https://youtube.com/watch?v=abc", "title": "T",
            "description": "D", "channelName": "canal", "duration": "02:00:50",
            "viewCount": 1000, "likes": 50, "commentsCount": 3, "date": "2026-08-01T00:00:00Z",
        })
        self.assertEqual(item["platform"], "youtube")
        self.assertEqual(item["duration"], 2 * 3600 + 50)
        self.assertEqual(item["formato"], "largo")
        self.assertEqual(item["views"], 1000)

    def test_normalize_tiktok_uses_video_meta_duration(self):
        item = vr._normalize_tiktok({
            "id": "1", "webVideoUrl": "u", "text": "hola", "authorMeta": {"name": "a"},
            "videoMeta": {"duration": 20}, "playCount": 5000, "diggCount": 400,
            "commentCount": 10, "shareCount": 2, "createTimeISO": "2026-08-06T00:00:00Z",
        })
        self.assertEqual(item["platform"], "tiktok")
        self.assertEqual(item["formato"], "reel")

    def test_normalize_instagram_detects_carousel(self):
        item = vr._normalize_instagram({
            "id": "1", "url": "u", "caption": "c", "ownerUsername": "o",
            "type": "Sidecar", "likesCount": 100, "commentsCount": 5, "timestamp": "2026-08-01T00:00:00Z",
        })
        self.assertEqual(item["formato"], "carrusel")


class VaultReadingTests(unittest.TestCase):
    def test_reads_only_requested_names(self):
        with unittest.mock.patch("pathlib.Path.exists", return_value=True), \
             unittest.mock.patch("pathlib.Path.read_text", return_value="APIFY_KEY_1=abc123\nOTHER_SECRET=xyz\nAPIFY_KEY_2=\n"):
            found = vr.read_vault_keys(["APIFY_KEY_1", "APIFY_KEY_2", "APIFY_KEY_3"])
        self.assertEqual(found, {"APIFY_KEY_1": "abc123"})
        self.assertNotIn("OTHER_SECRET", found)

    def test_missing_vault_returns_empty(self):
        with unittest.mock.patch("pathlib.Path.exists", return_value=False):
            found = vr.read_vault_keys(["APIFY_KEY_1"])
        self.assertEqual(found, {})


class ApifyRotationTests(unittest.TestCase):
    def test_requires_at_least_one_key(self):
        with self.assertRaises(vr.ApifyRotationError):
            vr.ApifyRotation({})

    def test_round_robin_order(self):
        rotation = vr.ApifyRotation({"A": "va", "B": "vb"})
        first = rotation._next()
        second = rotation._next()
        self.assertNotEqual(first[0], second[0])

    def test_run_actor_sync_rotates_on_401(self):
        rotation = vr.ApifyRotation({"A": "va", "B": "vb"})

        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload
            def read(self):
                return json.dumps(self._payload).encode()
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        calls = []

        def fake_urlopen(req, timeout):
            calls.append(req.full_url)
            if len(calls) == 1:
                import urllib.error
                raise urllib.error.HTTPError(req.full_url, 401, "unauthorized", {}, None)
            return FakeResponse([{"id": "x"}])

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            items = rotation.run_actor_sync("some/actor", {"q": "x"}, max_items=5)
        self.assertEqual(len(calls), 2)
        self.assertEqual(items, [{"id": "x"}])

    def test_run_actor_sync_exhausts_all_keys(self):
        rotation = vr.ApifyRotation({"A": "va", "B": "vb"})

        def fake_urlopen(req, timeout):
            import urllib.error
            raise urllib.error.HTTPError(req.full_url, 429, "rate limited", {}, None)

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            with self.assertRaises(vr.ApifyRotationError):
                rotation.run_actor_sync("some/actor", {"q": "x"}, max_items=5)

    def test_run_actor_sync_includes_max_charge_cap(self):
        rotation = vr.ApifyRotation({"A": "va"})
        captured = {}

        class FakeResponse:
            def read(self):
                return b"[]"
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            return FakeResponse()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            rotation.run_actor_sync("some/actor", {"q": "x"}, max_items=5, max_charge_usd=0.2)
        self.assertIn("maxTotalChargeUsd=0.2", captured["url"])


class SupadataStubTests(unittest.TestCase):
    def test_absent_key_is_honest(self):
        result = vr.enrich_supadata([{"id": "1"}], {})
        self.assertEqual(result["status"], "sin_llave")

    def test_present_key_does_not_fabricate_transcripts(self):
        result = vr.enrich_supadata([{"id": "1"}], {"SUPADATA_API_KEY": "present"})
        self.assertEqual(result["status"], "llave_presente_sin_probar")
        self.assertNotIn("transcript", result["items"][0])


class ChannelMapTests(unittest.TestCase):
    def test_all_real_channels_mapped(self):
        real_channels = {
            "cano-digital-ia", "cass-healt", "sya-animals", "sya-motive",
            "unsolved-lens", "cosmic-lens", "wild-whiskers", "sleepy-lofi",
        }
        self.assertEqual(set(vr.CHANNEL_MAP), real_channels)


if __name__ == "__main__":
    unittest.main()
