"""Plan POTENCIA P2 -- scripts/ads_bridge.py.

Real generation against the live ads-studio engine was verified by hand
(see the commit message): a real DRAFT campaign package was written to
storage/workspaces/ads/ (never to cano-ai-command-center, which is
read-only), status=DRAFT, authorized=False, published=False, spend=0.
This file covers the deterministic parts: slug convention, channel
validation, dry-run behavior -- nothing here imports ads-studio itself
(that's exercised live, not in the unit suite, since it lives in a
separate, read-only repo)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ads_bridge  # noqa: E402


class SlugConventionTests(unittest.TestCase):
    def test_slug_has_test_prefix_and_today(self):
        import datetime
        slug = ads_bridge.slug_with_test_prefix("mi-campana")
        self.assertTrue(slug.startswith("[TEST] mi-campana -- "))
        self.assertIn(datetime.date.today().isoformat(), slug)


class ChannelValidationTests(unittest.TestCase):
    def test_unknown_business_channel_rejected_without_calling_ads_studio(self):
        result = ads_bridge.build_draft_campaign(
            "unsolved-lens", "meta", "test-slug", apply=True,
        )
        self.assertEqual(result["status"], "sin_canal_comercial")

    def test_known_channel_maps_to_real_ads_studio_channel(self):
        result = ads_bridge.build_draft_campaign(
            "cano-digital-ia", "meta", "test-slug", apply=False,
        )
        self.assertEqual(result["ads_canal"], "cano-digital")

    def test_all_commercial_channels_have_a_mapping(self):
        for canal in ("cano-digital-ia", "cass-healt", "sya-motive", "sya-animals"):
            self.assertIn(canal, ads_bridge.CHANNEL_MAP)


class DryRunTests(unittest.TestCase):
    def test_dry_run_never_touches_ads_studio_module(self):
        """apply=False must return before `_load_ads_studio()` is ever
        called -- confirmed by monkeypatching it to raise if invoked."""
        original = ads_bridge._load_ads_studio
        ads_bridge._load_ads_studio = lambda: (_ for _ in ()).throw(AssertionError("dry-run must not import ads-studio"))
        try:
            result = ads_bridge.build_draft_campaign("cano-digital-ia", "meta", "s", apply=False)
        finally:
            ads_bridge._load_ads_studio = original
        self.assertEqual(result["status"], "dry_run")
        self.assertFalse(result["publish"])


if __name__ == "__main__":
    unittest.main()
