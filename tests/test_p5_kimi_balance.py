"""Plan POTENCIA P5 -- scripts/validators/registry.py::validate_kimi_moonshot
now also fetches /users/me/balance (confirmed live: real free endpoint,
returns {"available_balance": 17.7633, "cash_balance": 15,
"voucher_balance": 2.7633} for the real KIMI_API_KEY). Mocked here --
never real network in the unit suite."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from scripts.validators import registry


class KimiBalanceQuotaTests(unittest.TestCase):
    def test_no_key_unaffected(self):
        result = registry.validate_kimi_moonshot({})
        self.assertEqual(result["status"], "—")

    def test_balance_populates_quota_on_success(self):
        def fake_http_get(url, headers=None):
            if url.endswith("/models"):
                return 200, b"{}", None, 100
            if url.endswith("/users/me/balance"):
                body = json.dumps({"data": {"available_balance": 17.76, "cash_balance": 15, "voucher_balance": 2.76}}).encode()
                return 200, body, None, 50
            raise AssertionError(f"unexpected url {url}")

        with patch("scripts.validators.registry.http_get", side_effect=fake_http_get):
            result = registry.validate_kimi_moonshot({"KIMI_API_KEY": "fake"})

        self.assertEqual(result["status"], "✓")
        self.assertEqual(result["quota"]["available_balance_usd"], 17.76)
        self.assertEqual(result["quota"]["cash_balance_usd"], 15)

    def test_balance_endpoint_failure_does_not_break_the_auth_result(self):
        def fake_http_get(url, headers=None):
            if url.endswith("/models"):
                return 200, b"{}", None, 100
            if url.endswith("/users/me/balance"):
                return 500, b"", "server error", 50
            raise AssertionError(f"unexpected url {url}")

        with patch("scripts.validators.registry.http_get", side_effect=fake_http_get):
            result = registry.validate_kimi_moonshot({"KIMI_API_KEY": "fake"})

        self.assertEqual(result["status"], "✓")
        self.assertIsNone(result.get("quota"))

    def test_auth_failure_never_attempts_balance_call(self):
        calls = []

        def fake_http_get(url, headers=None):
            calls.append(url)
            return 401, b"", None, 50

        with patch("scripts.validators.registry.http_get", side_effect=fake_http_get):
            registry.validate_kimi_moonshot({"KIMI_API_KEY": "fake"})

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].endswith("/models"))


if __name__ == "__main__":
    unittest.main()
