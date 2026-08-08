"""Thin Telegram Bot API client — K4 (plan HERMES-KICKOFF, gap 6).

Deliberately independent of `hermes-gateway`: this calls
`https://api.telegram.org/bot<token>/sendMessage` directly over HTTP instead
of going through that separate process, so a StarHome notification does not
go dark just because the gateway happens to be down or restarting. K0
already proved this exact call works end to end (Cano was notified of the
approved plan the same way, by hand, on the day K0 landed).

Env vars: `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`. Two names existed
in the wild for the chat id -- hermes-agent's own `.env` calls it
`TELEGRAM_HOME_CHANNEL`, the shared vault (`~/.secrets/credenciales/
credenciales/.env`) calls it `TELEGRAM_CHAT_ID` -- confirmed to hold the
exact same value. `TELEGRAM_CHAT_ID` was picked because it is what this
repo's own `.env` already defines (loaded into the `starhome-os` systemd
unit via `EnvironmentFile=`, see `~/.config/systemd/user/starhome-os.
service`) -- no second env var or alias needed to make this work in
production.
"""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

from cano_hermes.config import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"

# A2 (plan AUTONOMÍA TOTAL, 2026-08-08): Telegram's own Bot API hard limit
# for `sendDocument` -- uploads above this are rejected by Telegram itself
# (413), so this is checked BEFORE ever making the request, not learned
# from a failed one.
TELEGRAM_MAX_DOCUMENT_BYTES = 50 * 1024 * 1024


def send_telegram_message(text: str, timeout: float = 10.0) -> bool:
    """Best-effort send. Returns True on a confirmed 2xx from Telegram,
    False otherwise -- for every failure mode (no credentials configured,
    network error, non-2xx from Telegram) this logs a warning and returns
    False. It NEVER raises: a notification is a side effect of a task
    transition, not part of it, and must never be able to take the
    transition down with it (see `notifications/service.py`).

    Never logs `text`, the token, or the chat id. The one thing this is
    careful about beyond that: `httpx`'s own exception `str()` embeds the
    full request URL, which for this call includes the bot token
    (`.../bot<token>/sendMessage`) -- so failures are logged by exception
    *class name* only, never by `str(exc)`.
    """
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        logger.warning(
            "Telegram no configurado (falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID) -- notificación omitida"
        )
        return False

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    try:
        response = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=timeout)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Envío a Telegram falló (%s) -- notificación omitida", exc.__class__.__name__)
        return False
    return True


def send_telegram_document(path: str, caption: str = "", timeout: float = 60.0) -> bool:
    """Best-effort file delivery via `sendDocument` (multipart/form-data).
    Same never-raise contract as `send_telegram_message`: every failure
    mode (no credentials, missing file, oversized file, network error,
    non-2xx from Telegram) logs a warning and returns False, never raises
    -- a delivery is a side effect of a task/cycle completing, not part of
    it (see A2's callers in aggregator.py / daily_cycle.py).

    A file over `TELEGRAM_MAX_DOCUMENT_BYTES` is never uploaded (Telegram
    itself would reject it) -- instead this falls back to
    `send_telegram_message` with the local path appended to `caption`, so
    Cano still gets an honest notification pointing at where the file
    actually lives, rather than a silent failure.

    Never logs the token or the file's content. Longer timeout default
    than `send_telegram_message` (60s vs 10s) since this uploads a real
    file body, not a short JSON payload.
    """
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        logger.warning(
            "Telegram no configurado (falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID) -- envío de documento omitido"
        )
        return False

    file_path = Path(path)
    if not file_path.is_file():
        logger.warning("Documento no encontrado en %s -- envío omitido", file_path)
        return False

    size = file_path.stat().st_size
    if size > TELEGRAM_MAX_DOCUMENT_BYTES:
        logger.warning(
            "Documento %s excede el límite de Telegram (%d bytes > %d) -- "
            "se envía la ruta local por texto en su lugar",
            file_path, size, TELEGRAM_MAX_DOCUMENT_BYTES,
        )
        fallback = f"{caption}\n\n[archivo demasiado grande para Telegram, {size} bytes]\n{file_path}".strip()
        return send_telegram_message(fallback, timeout=timeout)

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendDocument"
    try:
        with file_path.open("rb") as fh:
            response = httpx.post(
                url,
                data={"chat_id": chat_id, "caption": caption},
                files={"document": (file_path.name, fh)},
                timeout=timeout,
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("Envío de documento a Telegram falló (%s) -- notificación omitida", exc.__class__.__name__)
        return False
    return True
