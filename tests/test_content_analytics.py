"""P4 (parte A) — tests de scripts/content_analytics.py.

Todo mockeado: cero red real, cero vault real, cero Baserow real.
Cubre: parseo/clasificación de duración, degradación por canal,
Upload-Post con urlopen inyectado, generación de filas y que el
dry-run no escriba nada.
"""
from __future__ import annotations

import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import content_analytics as ca  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes del servicio Data API v3 (encadenado .x().list(...).execute())
# ---------------------------------------------------------------------------

class _FakeRequest:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _FakeCollection:
    def __init__(self, payload):
        self._payload = payload

    def list(self, **_kwargs):
        return _FakeRequest(self._payload)


class _FakeYouTube:
    def __init__(self, channels_payload, playlist_payload=None, videos_payload=None):
        self._channels = channels_payload
        self._playlist = playlist_payload or {"items": []}
        self._videos = videos_payload or {"items": []}

    def channels(self):
        return _FakeCollection(self._channels)

    def playlistItems(self):
        return _FakeCollection(self._playlist)

    def videos(self):
        return _FakeCollection(self._videos)


class _FakeAnalyticsService:
    def __init__(self, payload):
        self._payload = payload

    def reports(self):
        payload = self._payload

        class _R:
            def query(self, **_kwargs):
                return _FakeRequest(payload)

        return _R()


def _channels_payload(subs="1200", views="45000", videos="80"):
    return {
        "items": [{
            "id": "UCabc",
            "snippet": {"title": "Canal Demo"},
            "statistics": {
                "subscriberCount": subs, "viewCount": views, "videoCount": videos,
            },
            "contentDetails": {"relatedPlaylists": {"uploads": "UUabc"}},
        }]
    }


def _playlist_payload(video_ids):
    return {"items": [{"contentDetails": {"videoId": vid}} for vid in video_ids]}


def _videos_payload():
    return {
        "items": [
            {
                "id": "v-short",
                "snippet": {"title": "Un short", "publishedAt": "2026-08-01T00:00:00Z"},
                "statistics": {"viewCount": "500", "likeCount": "50", "commentCount": "5"},
                "contentDetails": {"duration": "PT58S"},
            },
            {
                "id": "v-long",
                "snippet": {"title": "Un largo", "publishedAt": "2026-08-02T00:00:00Z"},
                "statistics": {"viewCount": "9000", "likeCount": "300", "commentCount": "40"},
                "contentDetails": {"duration": "PT12M3S"},
            },
        ]
    }


# ---------------------------------------------------------------------------
# Duración
# ---------------------------------------------------------------------------

class DurationTests(unittest.TestCase):
    def test_parse_variants(self):
        self.assertEqual(ca.parse_duration_seconds("PT58S"), 58)
        self.assertEqual(ca.parse_duration_seconds("PT1M"), 60)
        self.assertEqual(ca.parse_duration_seconds("PT1M32S"), 92)
        self.assertEqual(ca.parse_duration_seconds("PT2H3M4S"), 7384)
        self.assertEqual(ca.parse_duration_seconds("P1DT1S"), 86401)
        self.assertEqual(ca.parse_duration_seconds("P0D"), 0)
        self.assertIsNone(ca.parse_duration_seconds(""))
        self.assertIsNone(ca.parse_duration_seconds("garbage"))

    def test_classification_boundary(self):
        self.assertEqual(ca.classify_duration(60), "corto")
        self.assertEqual(ca.classify_duration(61), "largo")
        self.assertEqual(ca.classify_duration(None), "desconocido")


# ---------------------------------------------------------------------------
# fetch_youtube_stats
# ---------------------------------------------------------------------------

class FetchYouTubeTests(unittest.TestCase):
    def _build_fn_ok(self, service, analytics_payload=None):
        def build_fn(api, _version, **_kwargs):
            if api == "youtube":
                return service
            return _FakeAnalyticsService(
                analytics_payload if analytics_payload is not None
                else {"rows": [[1234, 567, 89.5]]}
            )
        return build_fn

    def test_happy_path_with_classification(self):
        service = _FakeYouTube(
            _channels_payload(), _playlist_payload(["v-short", "v-long"]), _videos_payload()
        )
        with mock.patch.object(ca, "load_channel_credentials", return_value=object()):
            results = ca.fetch_youtube_stats(
                {"demo": "carpeta-demo"}, build_fn=self._build_fn_ok(service)
            )
        data = results["demo"]
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["subs"], 1200)
        self.assertEqual(data["views_total"], 45000)
        self.assertEqual(len(data["videos"]), 2)
        classes = {v["id"]: v["duration_class"] for v in data["videos"]}
        self.assertEqual(classes, {"v-short": "corto", "v-long": "largo"})
        self.assertEqual(data["analytics_28d"]["status"], "ok")
        self.assertEqual(data["analytics_28d"]["views_28d"], 1234)

    def test_per_channel_degradation_does_not_stop_others(self):
        good_service = _FakeYouTube(
            _channels_payload(), _playlist_payload(["v-short"]), _videos_payload()
        )

        def load_creds(folder, token_dir=None):
            if folder == "rota":
                raise FileNotFoundError("youtube_token.json no existe")
            return object()

        with mock.patch.object(ca, "load_channel_credentials", side_effect=load_creds):
            results = ca.fetch_youtube_stats(
                {"bueno": "carpeta-ok", "malo": "rota"},
                build_fn=self._build_fn_ok(good_service),
            )
        self.assertEqual(results["bueno"]["status"], "ok")
        self.assertEqual(results["malo"]["status"], "error")
        self.assertIn("FileNotFoundError", results["malo"]["error"])

    def test_api_exception_degrades_to_error(self):
        # channels().list().execute() lanza -> el canal degrada a error
        raising = _FakeYouTube(RuntimeError("HttpError 403 quota"))
        with mock.patch.object(ca, "load_channel_credentials", return_value=object()):
            results = ca.fetch_youtube_stats(
                {"demo": "x"}, build_fn=self._build_fn_ok(raising)
            )
        self.assertEqual(results["demo"]["status"], "error")
        self.assertIn("RuntimeError", results["demo"]["error"])

    def test_analytics_error_does_not_break_channel(self):
        service = _FakeYouTube(
            _channels_payload(), _playlist_payload(["v-short"]), _videos_payload()
        )

        def build_fn(api, _version, **_kwargs):
            if api == "youtube":
                return service
            raise RuntimeError("Analytics API no habilitada")

        with mock.patch.object(ca, "load_channel_credentials", return_value=object()):
            results = ca.fetch_youtube_stats({"demo": "x"}, build_fn=build_fn)
        self.assertEqual(results["demo"]["status"], "ok")
        self.assertEqual(results["demo"]["analytics_28d"]["status"], "error")


# ---------------------------------------------------------------------------
# Upload-Post
# ---------------------------------------------------------------------------

def _fake_urlopen_factory(responses: dict[str, dict]):
    """responses: fragmento de path → payload JSON."""

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        for fragment, payload in responses.items():
            if fragment in url:
                return _Resp(payload)
        raise AssertionError(f"URL inesperada en test: {url}")

    return fake_urlopen


class UploadPostTests(unittest.TestCase):
    def test_missing_key_returns_sin_llave(self):
        with mock.patch.object(ca, "_vault_value", return_value=None):
            result = ca.fetch_uploadpost_stats()
        self.assertEqual(result["status"], "sin_llave")

    def test_happy_path(self):
        responses = {
            "/api/uploadposts/users": {"profiles": [{"username": "cano_digital"}]},
            "/api/uploadposts/history": {
                "history": [
                    {"platform": "tiktok", "success": True},
                    {"platform": "youtube", "success": False},
                    {"platform": "tiktok", "success": True},
                ],
                "total": 42,
            },
            "/api/uploadposts/total-impressions/cano_digital": {
                "success": True, "total_impressions": 9876,
                "per_platform": {"tiktok": 9000, "youtube": 876},
            },
        }
        result = ca.fetch_uploadpost_stats(
            api_key="k", urlopen_fn=_fake_urlopen_factory(responses)
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["profiles"], ["cano_digital"])
        self.assertEqual(result["posts_total"], 42)
        self.assertEqual(result["posts_per_platform"], {"tiktok": 2, "youtube": 1})
        self.assertEqual(
            result["impressions_30d"]["cano_digital"]["total_impressions_30d"], 9876
        )

    def test_network_error_never_raises(self):
        def exploding_urlopen(req, timeout=None):
            raise OSError("red caída")

        result = ca.fetch_uploadpost_stats(api_key="k", urlopen_fn=exploding_urlopen)
        self.assertEqual(result["status"], "error")
        self.assertIn("_error", result["profiles_error"])
        self.assertIn("_error", result["history_error"])

    def test_extract_profiles_shapes(self):
        self.assertEqual(
            ca._extract_profile_usernames([{"username": "a"}, {"name": "b"}, "c"]),
            ["a", "b", "c"],
        )
        self.assertEqual(
            ca._extract_profile_usernames({"profiles": [{"username": "x"}]}), ["x"]
        )
        self.assertEqual(ca._extract_profile_usernames({"raro": 1}), [])


# ---------------------------------------------------------------------------
# Filas Baserow
# ---------------------------------------------------------------------------

class BuildRowsTests(unittest.TestCase):
    def _youtube_ok(self):
        return {
            "canal-a": {
                "status": "ok", "channel_title": "Canal A",
                "subs": 100, "views_total": 5000, "videos_total": 20,
                "videos": [
                    {"id": "s1", "title": "short", "duration_class": "corto",
                     "views": 10, "likes": 1, "comments": 0},
                    {"id": "l1", "title": "largo", "duration_class": "largo",
                     "views": 900, "likes": 30, "comments": 2},
                ],
                "analytics_28d": {"status": "ok", "views_28d": 321.567,
                                  "watch_minutes_28d": 55},
            },
            "canal-roto": {"status": "error", "error": "FileNotFoundError: x"},
        }

    def _uploadpost_ok(self):
        return {
            "status": "ok", "profiles": ["perfil1"], "posts_total": 7,
            "posts_per_platform": {"tiktok": 5, "youtube": 2},
            "impressions_30d": {
                "perfil1": {"status": "ok", "total_impressions_30d": 1234},
            },
        }

    def test_rows_generated_and_rounded(self):
        rows = ca.build_metric_rows(self._youtube_ok(), self._uploadpost_ok(), "2026-08-07")
        by_key = {(r["oficina"], r["metrica"]): r for r in rows}

        self.assertEqual(by_key[("canal-a", "yt_subs")]["valor"], 100.0)
        self.assertEqual(by_key[("canal-a", "yt_views_total")]["valor"], 5000.0)
        self.assertEqual(by_key[("canal-a", "yt_top_video_views_recientes")]["valor"], 900.0)
        self.assertIn("largo", by_key[("canal-a", "yt_top_video_views_recientes")]["nota"])
        self.assertEqual(by_key[("canal-a", "yt_videos_recientes_cortos")]["valor"], 1.0)
        self.assertEqual(by_key[("canal-a", "yt_videos_recientes_largos")]["valor"], 1.0)
        # redondeo a 2 decimales
        self.assertEqual(by_key[("canal-a", "yt_views_28d")]["valor"], 321.57)
        self.assertEqual(by_key[("uploadpost", "up_posts_total")]["valor"], 7.0)
        self.assertEqual(by_key[("uploadpost", "up_posts_tiktok")]["valor"], 5.0)
        self.assertEqual(by_key[("perfil1", "up_impressions_30d")]["valor"], 1234.0)
        # el canal en error no genera NINGUNA fila
        self.assertFalse(any(r["oficina"] == "canal-roto" for r in rows))
        # todas las filas llevan la fecha pedida
        self.assertTrue(all(r["fecha"] == "2026-08-07" for r in rows))

    def test_error_sources_generate_no_rows(self):
        rows = ca.build_metric_rows(
            {"x": {"status": "error", "error": "y"}}, {"status": "sin_llave"}, "2026-08-07"
        )
        self.assertEqual(rows, [])


class WriteToBaserowTests(unittest.TestCase):
    def test_counts_ok_and_failed(self):
        rows = [
            {"fecha": "2026-08-07", "oficina": "a", "metrica": "m1", "valor": 1.0, "nota": ""},
            {"fecha": "2026-08-07", "oficina": "b", "metrica": "m2", "valor": 2.0, "nota": ""},
        ]
        outcomes = iter([{"status": "ok", "row_id": 1}, {"status": "error", "detail": "x"}])
        write_fn = mock.Mock(side_effect=lambda *a, **k: next(outcomes))
        result = ca.write_to_baserow(rows, write_fn=write_fn)
        self.assertEqual(result["written"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(write_fn.call_count, 2)


# ---------------------------------------------------------------------------
# CLI: dry-run no escribe, --apply sí
# ---------------------------------------------------------------------------

class MainTests(unittest.TestCase):
    def _patched(self):
        return (
            mock.patch.object(ca, "fetch_youtube_stats", return_value={
                "demo": {"status": "ok", "channel_title": "d", "subs": 1,
                         "views_total": 2, "videos_total": 3, "videos": []},
            }),
            mock.patch.object(ca, "fetch_uploadpost_stats",
                              return_value={"status": "sin_llave", "detail": ""}),
        )

    def test_dry_run_default_does_not_write(self):
        p_yt, p_up = self._patched()
        with p_yt, p_up, mock.patch.object(ca.monitoring, "write_metric_row") as w, \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            rc = ca.main([])
        self.assertEqual(rc, 0)
        w.assert_not_called()

    def test_apply_writes(self):
        p_yt, p_up = self._patched()
        with p_yt, p_up, mock.patch.object(
            ca.monitoring, "write_metric_row",
            return_value={"status": "ok", "row_id": 9},
        ) as w, mock.patch("sys.stdout", new_callable=io.StringIO):
            rc = ca.main(["--apply"])
        self.assertEqual(rc, 0)
        self.assertEqual(w.call_count, 3)  # yt_subs, yt_views_total, yt_videos_total

    def test_json_output_is_parseable(self):
        p_yt, p_up = self._patched()
        buf = io.StringIO()
        with p_yt, p_up, mock.patch("sys.stdout", buf):
            rc = ca.main(["--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("youtube", payload)
        self.assertIsNone(payload["baserow"])


if __name__ == "__main__":
    unittest.main()
