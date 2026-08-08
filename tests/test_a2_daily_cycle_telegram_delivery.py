"""A2 (plan AUTONOMÍA TOTAL, 2026-08-08) -- scripts/daily_cycle.py sends
its report over Telegram. Confirmed live before this change that the
plan's assumption ("ya tiene deliver telegram en cron") did not hold: no
telegram/notify reference existed anywhere in this file.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import daily_cycle


class NotifyDailyReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _report(self, name: str = "2026-08-08.md") -> Path:
        path = Path(self.tmp.name) / name
        path.write_text("# reporte", encoding="utf-8")
        return path

    def test_sends_report_as_document(self):
        report_path = self._report()
        with patch("scripts.daily_cycle.send_telegram_document") as fake_doc:
            fake_doc.return_value = True
            ok = daily_cycle.notify_daily_report(report_path, alerts=[])
            self.assertTrue(ok)
            fake_doc.assert_called_once()
            args, _ = fake_doc.call_args
            self.assertEqual(args[0], str(report_path))
            self.assertIn("Ciclo diario", args[1])

    def test_caption_mentions_alert_count_when_present(self):
        report_path = self._report()
        with patch("scripts.daily_cycle.send_telegram_document") as fake_doc:
            fake_doc.return_value = True
            daily_cycle.notify_daily_report(report_path, alerts=["budget over 80%", "health check failed"])
            args, _ = fake_doc.call_args
            self.assertIn("2 alerta", args[1])

    def test_never_raises_when_delivery_fails(self):
        report_path = self._report()
        with patch("scripts.daily_cycle.send_telegram_document") as fake_doc:
            fake_doc.return_value = False
            ok = daily_cycle.notify_daily_report(report_path, alerts=[])
            self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
