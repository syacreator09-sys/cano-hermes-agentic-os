"""K19 (plan HERMES-KICKOFF) -- real, read-only YouTube Data API v3 access
for channels StarHome already holds an OAuth token for (F12's
`youtube-tokens/<channel>/youtube_token.json`, one directory per channel,
confirmed live on this host: `cass-healt`, `cano-digital-ia`, `sya-
animals`, plus a few more not yet wired here).

This module talks to exactly TWO Google endpoints, both read-side:
  1. `https://oauth2.googleapis.com/token` (POST) -- the standard OAuth2
     "refresh_token" grant. This is authentication, not a YouTube write --
     it exchanges a long-lived refresh_token for a short-lived
     access_token, the same way any OAuth client must before calling a
     scoped API. It never touches youtube.googleapis.com and never
     mutates channel/video/upload state.
  2. `https://www.googleapis.com/youtube/v3/channels` (GET, `mine=true`)
     -- YouTube Data API v3's own read-only channel lookup. `part=
     snippet,statistics` is the cheapest real call that returns title,
     subscriber/video/view counts -- confirmed live against `cass-healt`
     while building this module (channel "cass healt&beauty",
     UC2_8UzboQUdYivbGupQPRYQ, 33 subs / 107 videos / 19657 views,
     2026-08-06).

`channel_snapshot` is the only public entrypoint and the only function
that does network I/O. It is hardcoded to GET `.../channels` -- there is
no write/upload/delete helper anywhere in this module, on purpose: the
stored tokens carry `youtube.upload`/`youtube.force-ssl` scopes (wide
enough to publish), but K19's dashboard use only ever needs read access,
so this module simply never exposes a way to call a mutating endpoint.
`tests/test_k19_business_cass.py::YoutubeIntegrationNoWriteCallTests`
pins this down by asserting no HTTP verb other than GET/POST-to-oauth-
refresh appears anywhere in this file, not just that a write wasn't
called in one test run.

Same contract as `content.dedup.fetch_rows`/`finance.accounting.fetch_rows`:
never raises, every failure mode (missing token file, bad JSON, expired
refresh token, network error, malformed API response) degrades to an
explicit `status` the caller can branch on.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

TOKENS_ROOT = Path.home() / ".secrets/credenciales/credenciales/youtube-tokens"
OAUTH_TOKEN_REFRESH_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"


def token_path(channel: str) -> Path:
    """`~/.secrets/credenciales/credenciales/youtube-tokens/<channel>/
    youtube_token.json` -- F12's real, confirmed-live layout (one
    directory per channel slug, e.g. `cass-healt`, `cano-digital-ia`).
    Pure path math, no filesystem access -- callers/tests can point
    elsewhere via `channel_snapshot(..., token_path=...)`."""
    return TOKENS_ROOT / channel / "youtube_token.json"


def _load_token(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, f"{path} no existe en este host"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{exc.__class__.__name__}: {exc}"
    missing = [k for k in ("client_id", "client_secret", "refresh_token") if not data.get(k)]
    if missing:
        return None, f"token file le faltan campos: {missing}"
    return data, None


def _refresh_access_token(token_data: dict[str, Any], *, timeout: float) -> tuple[str | None, str | None]:
    """OAuth2 refresh_token grant (POST oauth2.googleapis.com/token) --
    authentication only, never touches youtube.googleapis.com. Returns
    (access_token, error_detail)."""
    body = urllib.parse.urlencode({
        "client_id": token_data["client_id"],
        "client_secret": token_data["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(OAUTH_TOKEN_REFRESH_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return None, f"refresh HTTPError {exc.code}: {exc.read().decode(errors='replace')[:300]}"
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        return None, f"refresh {exc.__class__.__name__}: {exc}"

    access_token = payload.get("access_token")
    if not access_token:
        return None, f"respuesta de refresh sin access_token: {payload}"
    return access_token, None


def channel_snapshot(channel: str, *, token_path_override: Path | None = None, timeout: float = 10.0) -> dict[str, Any]:
    """Real read-only snapshot of one YouTube channel: refreshes the
    stored OAuth token, then GETs `channels?part=snippet,statistics&
    mine=true` (the token IS the channel -- `mine=true` resolves to
    whichever channel the refresh_token's account owns, no channel_id
    needed). Never raises. Returns one of:
      {"status": "sin_token", "detail": ...}
      {"status": "error", "detail": ...}
      {"status": "ok", "channel": {...}}
    """
    path = token_path_override or token_path(channel)
    token_data, err = _load_token(path)
    if token_data is None:
        return {"status": "sin_token", "detail": err, "channel": None}

    access_token, err = _refresh_access_token(token_data, timeout=timeout)
    if access_token is None:
        return {"status": "error", "detail": err, "channel": None}

    url = f"{YOUTUBE_CHANNELS_URL}?part=snippet%2Cstatistics&mine=true"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})  # GET (default)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return {"status": "error", "detail": f"channels.list HTTPError {exc.code}: "
                f"{exc.read().decode(errors='replace')[:300]}", "channel": None}
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
        return {"status": "error", "detail": f"channels.list {exc.__class__.__name__}: {exc}", "channel": None}

    items = payload.get("items") or []
    if not items:
        return {"status": "error", "detail": f"channels.list devolvió 0 items: {payload}", "channel": None}

    item = items[0]
    snippet = item.get("snippet") or {}
    statistics = item.get("statistics") or {}
    return {
        "status": "ok",
        "detail": None,
        "channel": {
            "channel_id": item.get("id"),
            "title": snippet.get("title"),
            "custom_url": snippet.get("customUrl"),
            "published_at": snippet.get("publishedAt"),
            "subscriber_count": int(statistics["subscriberCount"]) if "subscriberCount" in statistics else None,
            "video_count": int(statistics["videoCount"]) if "videoCount" in statistics else None,
            "view_count": int(statistics["viewCount"]) if "viewCount" in statistics else None,
            "hidden_subscriber_count": statistics.get("hiddenSubscriberCount"),
        },
    }
