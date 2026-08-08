"""A2 (plan AUTONOMÍA TOTAL, 2026-08-08) -- send_telegram_document.

Same never-raise / never-log-token conventions as
tests/test_k4_telegram_notifications.py's TelegramClientTests; httpx.post
is monkeypatched, never touches the network.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cano_hermes.notifications.telegram import send_telegram_document


class _FakeResponse:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("boom", request=None, response=self)


class SendTelegramDocumentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _real_file(self, name: str = "report.md", content: bytes = b"hello") -> Path:
        path = Path(self.tmp.name) / name
        path.write_bytes(content)
        return path

    def test_missing_credentials_is_best_effort_no_crash_no_send(self):
        path = self._real_file()
        with patch("cano_hermes.notifications.telegram.settings") as fake_settings, \
             patch("cano_hermes.notifications.telegram.httpx.post") as fake_post:
            fake_settings.telegram_bot_token = ""
            fake_settings.telegram_chat_id = ""
            ok = send_telegram_document(str(path), "caption")
            self.assertFalse(ok)
            fake_post.assert_not_called()

    def test_missing_file_is_best_effort_no_crash_no_send(self):
        with patch("cano_hermes.notifications.telegram.settings") as fake_settings, \
             patch("cano_hermes.notifications.telegram.httpx.post") as fake_post:
            fake_settings.telegram_bot_token = "fake-token"
            fake_settings.telegram_chat_id = "12345"
            ok = send_telegram_document(str(Path(self.tmp.name) / "nope.md"), "caption")
            self.assertFalse(ok)
            fake_post.assert_not_called()

    def test_http_failure_is_best_effort_no_crash(self):
        path = self._real_file()
        with patch("cano_hermes.notifications.telegram.settings") as fake_settings, \
             patch("cano_hermes.notifications.telegram.httpx.post") as fake_post:
            fake_settings.telegram_bot_token = "fake-token"
            fake_settings.telegram_chat_id = "12345"
            fake_post.return_value = _FakeResponse(status_code=500)
            ok = send_telegram_document(str(path), "caption")
            self.assertFalse(ok)

    def test_success_posts_multipart_with_chat_id_and_caption(self):
        path = self._real_file(content=b"real report content")
        with patch("cano_hermes.notifications.telegram.settings") as fake_settings, \
             patch("cano_hermes.notifications.telegram.httpx.post") as fake_post:
            fake_settings.telegram_bot_token = "fake-token"
            fake_settings.telegram_chat_id = "12345"
            fake_post.return_value = _FakeResponse(status_code=200)
            ok = send_telegram_document(str(path), "the caption")
            self.assertTrue(ok)
            fake_post.assert_called_once()
            args, kwargs = fake_post.call_args
            self.assertIn("sendDocument", args[0])
            self.assertIn("fake-token", args[0])
            self.assertEqual(kwargs["data"]["chat_id"], "12345")
            self.assertEqual(kwargs["data"]["caption"], "the caption")
            self.assertIn("document", kwargs["files"])
            filename, filehandle = kwargs["files"]["document"]
            self.assertEqual(filename, path.name)
            self.assertTrue(hasattr(filehandle, "read"))

    def test_oversized_file_falls_back_to_text_message_with_path(self):
        """Never uploads past the configured limit -- Telegram would
        reject it anyway. Falls back to an honest text message pointing
        at the local path instead of failing silently. Uses a real file
        against a monkeypatched (tiny) limit rather than a mocked
        Path.stat(), since Path.is_file() also calls stat() internally
        and a blanket patch there breaks that check too."""
        path = self._real_file(content=b"twelve bytes")
        with patch("cano_hermes.notifications.telegram.settings") as fake_settings, \
             patch("cano_hermes.notifications.telegram.httpx.post") as fake_post, \
             patch("cano_hermes.notifications.telegram.TELEGRAM_MAX_DOCUMENT_BYTES", 4):
            fake_settings.telegram_bot_token = "fake-token"
            fake_settings.telegram_chat_id = "12345"
            fake_post.return_value = _FakeResponse(status_code=200)
            ok = send_telegram_document(str(path), "big report")
            self.assertTrue(ok)
            fake_post.assert_called_once()
            args, kwargs = fake_post.call_args
            self.assertIn("sendMessage", args[0])
            self.assertNotIn("sendDocument", args[0])
            self.assertIn(str(path), kwargs["json"]["text"])
            self.assertIn("big report", kwargs["json"]["text"])


if __name__ == "__main__":
    unittest.main()
