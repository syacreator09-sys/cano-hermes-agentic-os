"""A2 (plan AUTONOMÍA TOTAL, 2026-08-08) -- NotificationService.notify_order_done
sends real Telegram documents for eligible artifacts (md/png/mp4/pdf), on
top of the pre-existing text summary from K7. Only the delivery step
touches send_telegram_document; the text-summary behavior is already
covered by tests/test_k7_kanban_events.py and must stay unchanged.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cano_hermes.domain.models import OrderRecord
from cano_hermes.notifications.service import NotificationService
from cano_hermes.storage.sqlite import SQLiteStore


class DeliverDocumentsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = SQLiteStore(f"sqlite:///{self.tmp.name}/db.sqlite")
        self.notifier = NotificationService(self.store)
        self.order = OrderRecord(objective="Investigar y entregar reporte", source="telegram")

    def _write(self, name: str, content: bytes = b"content") -> str:
        path = Path(self.tmp.name) / name
        path.write_bytes(content)
        return str(path)

    def test_deliverable_extensions_are_sent_as_documents(self):
        md = self._write("report.md")
        png = self._write("chart.png")
        with patch("cano_hermes.notifications.service.send_telegram_message"), \
             patch("cano_hermes.notifications.service.send_telegram_document") as fake_doc:
            fake_doc.return_value = True
            self.notifier.notify_order_done(self.order, [md, png])
        sent_paths = [call.args[0] for call in fake_doc.call_args_list]
        self.assertIn(md, sent_paths)
        self.assertIn(png, sent_paths)
        self.assertEqual(fake_doc.call_count, 2)

    def test_non_deliverable_extensions_are_skipped(self):
        """Workspace scratch files (json/log/txt/...) stay text-only in
        the summary message, same as before A2 -- not every artifact is
        worth a document upload."""
        scratch = self._write("scratch.json")
        with patch("cano_hermes.notifications.service.send_telegram_message"), \
             patch("cano_hermes.notifications.service.send_telegram_document") as fake_doc:
            self.notifier.notify_order_done(self.order, [scratch])
        fake_doc.assert_not_called()

    def test_missing_file_is_skipped_without_attempting_upload(self):
        missing = str(Path(self.tmp.name) / "gone.md")
        with patch("cano_hermes.notifications.service.send_telegram_message"), \
             patch("cano_hermes.notifications.service.send_telegram_document") as fake_doc:
            self.notifier.notify_order_done(self.order, [missing])
        fake_doc.assert_not_called()

    def test_oversized_deliverable_is_skipped_before_calling_send(self):
        """Checked here too (not just inside send_telegram_document) so a
        big batch doesn't even attempt an upload doomed to fall back."""
        big = self._write("huge.pdf")
        with patch("cano_hermes.notifications.service.send_telegram_message"), \
             patch("cano_hermes.notifications.service.send_telegram_document") as fake_doc, \
             patch("cano_hermes.notifications.service.TELEGRAM_MAX_DOCUMENT_BYTES", 1):
            self.notifier.notify_order_done(self.order, [big])
        fake_doc.assert_not_called()

    def test_one_failing_upload_does_not_block_the_rest_of_the_batch(self):
        md = self._write("first.md")
        png = self._write("second.png")
        with patch("cano_hermes.notifications.service.send_telegram_message"), \
             patch("cano_hermes.notifications.service.send_telegram_document") as fake_doc:
            fake_doc.side_effect = [False, True]
            self.notifier.notify_order_done(self.order, [md, png])
        self.assertEqual(fake_doc.call_count, 2)

    def test_text_summary_is_still_sent_alongside_documents(self):
        """A2 adds document delivery on top of K7's existing text
        summary -- it must never replace it."""
        md = self._write("report.md")
        with patch("cano_hermes.notifications.service.send_telegram_message") as fake_msg, \
             patch("cano_hermes.notifications.service.send_telegram_document"):
            self.notifier.notify_order_done(self.order, [md])
        fake_msg.assert_called_once()
        text = fake_msg.call_args[0][0]
        self.assertIn("ORDEN DONE", text)
        self.assertIn(md, text)


if __name__ == "__main__":
    unittest.main()
