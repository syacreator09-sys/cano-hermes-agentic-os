#!/usr/bin/env python3
"""Plan POTENCIA P4 (parte A) — lector de métricas reales de contenido.

Cierra el hueco del bucle de retroalimentación: hasta hoy el sistema
publicaba contenido pero nunca leía cómo le fue. Este script jala métricas
REALES de dos fuentes ya vivas y las persiste en la tabla Baserow
`metricas_diarias` (id 141, la misma que usa `scripts/daily_cycle.py`),
una fila por (canal, métrica), oficina = nombre del canal.

Fuentes y qué dan de verdad (verificado, no asumido):

1. **YouTube Data API v3** — tokens OAuth del vault
   (`~/.secrets/credenciales/credenciales/youtube-tokens/<carpeta>/
   youtube_token.json`, 8 canales). Scopes reales leídos de los tokens el
   2026-08-07: los 8 incluyen `youtube.upload` + `yt-analytics.readonly`;
   7 de 8 incluyen `youtube` completo y `cano-digital-ia` tiene
   `youtube.readonly` — todos suficientes para lectura de estadísticas.
   Por canal: `channels.list(part=snippet,statistics,contentDetails,
   mine=True)` (subs, vistas totales, playlist de subidas) →
   `playlistItems.list` (últimos ~10 videos) → `videos.list(part=
   statistics,contentDetails,snippet)` (vistas/likes/comentarios por video
   + duración ISO-8601 → clasificación corto ≤60s / largo).

2. **YouTube Analytics API v2** — el scope `yt-analytics.readonly` está en
   los 8 tokens, así que se INTENTA `reports().query(ids="channel==MINE",
   metrics="views,estimatedMinutesWatched,averageViewDuration")` de los
   últimos 28 días. Nota honesta: CTR de impresiones y retención por
   impresión NO existen en la API de consultas dirigidas (son exclusivos
   de YouTube Studio / Reporting API bulk), así que no se prometen. Si la
   API no está habilitada en el proyecto GCP del token, se degrada por
   canal a `{"status": "error", ...}` sin tumbar el resto.

3. **Upload-Post REST API** — llave `UPLOADPOST_API_KEY` del vault
   (validador `uploadpost` en `scripts/validators/registry.py`, mismo
   header `Authorization: Apikey <key>`). Endpoints reales confirmados en
   docs.upload-post.com el 2026-08-07:
     - `GET /api/uploadposts/users` — perfiles conectados (el que usa el
       validador; docs.upload-post.com/api/user-profiles/).
     - `GET /api/uploadposts/history?limit=100` — historial de subidas
       con `total` global (docs.upload-post.com/api/upload-history/).
     - `GET /api/uploadposts/total-impressions/<perfil>` — impresiones
       agregadas últimos 30 días, desglose por plataforma
       (docs.upload-post.com/api/get-analytics/).

Contratos duros:
  - NUNCA imprime tokens/llaves; el vault se parsea línea por línea
    extrayendo solo el valor en memoria (patrón de
    `monitoring._baserow_token()`).
  - Los fetchers NUNCA lanzan: cada canal/fuente degrada a un dict con
    `{"status": "error", ...}` y el resto sigue.
  - `--dry-run` es el default (imprime resumen, cero escrituras);
    `--apply` escribe a Baserow vía `monitoring.write_metric_row` (no se
    reimplementa el cliente Baserow). `--json` vuelca el resultado crudo.

Uso:
    . .venv/bin/activate
    python scripts/content_analytics.py            # dry-run
    python scripts/content_analytics.py --apply    # escribe Baserow
    python scripts/content_analytics.py --json     # salida JSON

La integración al dashboard/ciclo diario es la parte B de P4 (otro
agente); este módulo expone funciones puras importables para eso.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cano_hermes import monitoring  # noqa: E402

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Carpeta local del vault con un subdirectorio por canal
# (client_secret.json + youtube_token.json). Mismo backup que documenta
# el INDEX.md del vault; validado en vivo con channels.list(mine=True).
TOKEN_DIR = Path.home() / ".secrets/credenciales/credenciales/youtube-tokens"

# Copiado de cano-ai-command-center/01-offices/factory-ia-channel-v5/
# providers/youtube_native/tokens.py (repo de solo lectura — se replica el
# mapa aquí en vez de importarlo para no acoplar rutas entre repos).
# 4 de las 8 carpetas usan nombres genéricos heredados de cuando esas
# cuentas se aprovisionaron con identidades placeholder; los 8 alias
# resuelven a su canal real (validado 2026-07-31 vía channels.list).
CHANNEL_MAP = {
    "cano": "cano-digital-ia",
    "cass": "cass-healt",
    "sya-animals": "sya-animals",
    "sya-motive": "sya-motive",
    "unsolved-lens": "_sh_can",
    "cosmic-lens": "_sya_tester",
    "wild-whiskers": "_sya_testerwork",
    "sleepy-lofi": "_sya_automotriz09",
}

SHORT_MAX_SECONDS = 60          # ≤60s = corto (Shorts); >60s = largo
VIDEOS_PER_CHANNEL = 10         # últimos N videos por canal
ANALYTICS_WINDOW_DAYS = 28      # ventana de la consulta Analytics v2
UPLOADPOST_BASE = "https://api.upload-post.com"
HTTP_TIMEOUT = 20

_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?$"
)


# ---------------------------------------------------------------------------
# Vault — nunca imprime valores; parseo línea por línea (patrón de
# monitoring._baserow_token()).
# ---------------------------------------------------------------------------

def _vault_value(key: str, vault_path: Path | None = None) -> str | None:
    path = vault_path or monitoring.VAULT_ENV_PATH
    if not path.exists():
        return None
    prefix = f"{key}="
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def load_channel_credentials(folder: str, token_dir: Path | None = None):
    """Carga las credenciales OAuth de un canal desde el vault local.

    Réplica del `load_credentials` de tokens.py (command-center, solo
    lectura): entre los 8 tokens reales conviven DOS formas — el dict
    OAuth crudo (`access_token` + `scope` como string separado por
    espacios) y la forma `Credentials.to_json()` de google-auth (`token` +
    `scopes` lista) — se soportan ambas en vez de asumir una.
    """
    from google.oauth2.credentials import Credentials  # import perezoso

    token_path = (token_dir or TOKEN_DIR) / folder / "youtube_token.json"
    data = json.loads(token_path.read_text(encoding="utf-8"))
    access_token = data.get("access_token") or data["token"]
    scopes = data.get("scope", "").split() or data.get("scopes", [])
    return Credentials(
        token=access_token,
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=scopes,
    )


# ---------------------------------------------------------------------------
# Duración / clasificación corto-largo
# ---------------------------------------------------------------------------

def parse_duration_seconds(iso_duration: str) -> int | None:
    """`PT1M32S` → 92. Devuelve None si el formato no se reconoce (la API
    puede dar `P0D` para vivos/premieres; eso parsea a 0)."""
    if not iso_duration:
        return None
    match = _DURATION_RE.match(iso_duration.strip())
    if not match:
        return None
    parts = {k: int(v) for k, v in match.groupdict().items() if v}
    return (
        parts.get("days", 0) * 86400
        + parts.get("hours", 0) * 3600
        + parts.get("minutes", 0) * 60
        + parts.get("seconds", 0)
    )


def classify_duration(seconds: int | None) -> str:
    if seconds is None:
        return "desconocido"
    return "corto" if seconds <= SHORT_MAX_SECONDS else "largo"


# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------

def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def fetch_channel_stats(youtube: Any) -> dict[str, Any]:
    """Estadísticas de UN canal vía un servicio Data API v3 ya construido
    (inyectable para tests). Puede lanzar — `fetch_youtube_stats` es quien
    degrada por canal."""
    chan_resp = youtube.channels().list(
        part="snippet,statistics,contentDetails", mine=True
    ).execute()
    items = chan_resp.get("items") or []
    if not items:
        return {"status": "error", "error": "channels.list(mine=True) sin items"}
    chan = items[0]
    stats = chan.get("statistics", {})
    uploads_playlist = (
        chan.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    )

    video_ids: list[str] = []
    if uploads_playlist:
        pl_resp = youtube.playlistItems().list(
            part="contentDetails", playlistId=uploads_playlist,
            maxResults=VIDEOS_PER_CHANNEL,
        ).execute()
        video_ids = [
            it["contentDetails"]["videoId"]
            for it in pl_resp.get("items", [])
            if it.get("contentDetails", {}).get("videoId")
        ]

    videos: list[dict[str, Any]] = []
    if video_ids:
        vid_resp = youtube.videos().list(
            part="snippet,statistics,contentDetails", id=",".join(video_ids)
        ).execute()
        for item in vid_resp.get("items", []):
            seconds = parse_duration_seconds(
                item.get("contentDetails", {}).get("duration", "")
            )
            vstats = item.get("statistics", {})
            videos.append({
                "id": item.get("id"),
                "title": item.get("snippet", {}).get("title", ""),
                "published_at": item.get("snippet", {}).get("publishedAt", ""),
                "duration_seconds": seconds,
                "duration_class": classify_duration(seconds),
                "views": _int_or_none(vstats.get("viewCount")),
                "likes": _int_or_none(vstats.get("likeCount")),
                "comments": _int_or_none(vstats.get("commentCount")),
            })

    return {
        "status": "ok",
        "channel_id": chan.get("id"),
        "channel_title": chan.get("snippet", {}).get("title", ""),
        "subs": _int_or_none(stats.get("subscriberCount")),
        "views_total": _int_or_none(stats.get("viewCount")),
        "videos_total": _int_or_none(stats.get("videoCount")),
        "videos": videos,
    }


def fetch_channel_analytics(analytics: Any, today: datetime.date | None = None) -> dict[str, Any]:
    """Intento honesto de YouTube Analytics API v2 (el scope está en los 8
    tokens; que la API esté habilitada en el proyecto GCP del token es otra
    cosa — de ahí el try). Métricas de la ventana de 28 días. Nunca lanza."""
    end = today or datetime.date.today()
    start = end - datetime.timedelta(days=ANALYTICS_WINDOW_DAYS)
    try:
        resp = analytics.reports().query(
            ids="channel==MINE",
            startDate=start.isoformat(),
            endDate=end.isoformat(),
            metrics="views,estimatedMinutesWatched,averageViewDuration",
        ).execute()
        rows = resp.get("rows") or []
        if not rows:
            return {"status": "sin_datos", "detail": "Analytics respondió sin filas"}
        views, minutes, avg_duration = (rows[0] + [None, None, None])[:3]
        return {
            "status": "ok",
            "views_28d": views,
            "watch_minutes_28d": minutes,
            "avg_view_duration_s_28d": avg_duration,
        }
    except Exception as exc:  # noqa: BLE001 — degradación deliberada
        return {"status": "error", "error": f"{exc.__class__.__name__}: {exc}"[:300]}


def fetch_youtube_stats(
    channel_map: dict[str, str] | None = None,
    build_fn: Callable[..., Any] | None = None,
    token_dir: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Métricas de todos los canales del CHANNEL_MAP. NUNCA lanza: cada
    canal degrada a `{"status": "error", ...}` de forma independiente.
    `build_fn` inyectable (default `googleapiclient.discovery.build`) para
    que los tests no toquen red."""
    channel_map = channel_map if channel_map is not None else CHANNEL_MAP
    if build_fn is None:
        try:
            from googleapiclient.discovery import build as build_fn  # type: ignore
        except ImportError as exc:
            return {
                slug: {"status": "error", "error": f"ImportError: {exc}"}
                for slug in channel_map
            }

    results: dict[str, dict[str, Any]] = {}
    for slug, folder in channel_map.items():
        try:
            creds = load_channel_credentials(folder, token_dir=token_dir)
            youtube = build_fn("youtube", "v3", credentials=creds, cache_discovery=False)
            result = fetch_channel_stats(youtube)
            if result.get("status") == "ok":
                try:
                    analytics = build_fn(
                        "youtubeAnalytics", "v2", credentials=creds, cache_discovery=False
                    )
                    result["analytics_28d"] = fetch_channel_analytics(analytics)
                except Exception as exc:  # noqa: BLE001
                    result["analytics_28d"] = {
                        "status": "error",
                        "error": f"{exc.__class__.__name__}: {exc}"[:300],
                    }
            results[slug] = result
        except Exception as exc:  # noqa: BLE001 — un canal caído no tumba el resto
            results[slug] = {
                "status": "error",
                "error": f"{exc.__class__.__name__}: {exc}"[:300],
            }
    return results


# ---------------------------------------------------------------------------
# Upload-Post
# ---------------------------------------------------------------------------

def _uploadpost_get(
    path: str, api_key: str,
    urlopen_fn: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """GET autenticado a la API de Upload-Post. Devuelve el JSON o un dict
    de error — nunca lanza y nunca incluye la llave en el resultado."""
    req = urllib.request.Request(
        f"{UPLOADPOST_BASE}{path}",
        headers={"Authorization": f"Apikey {api_key}"},
    )
    try:
        with urlopen_fn(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"_error": f"HTTP {exc.code}", "_detail": exc.read().decode(errors="replace")[:200]}
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"{exc.__class__.__name__}: {exc}"[:200]}


def _extract_profile_usernames(users_payload: Any) -> list[str]:
    """El payload de /api/uploadposts/users puede venir como lista directa
    o envuelto (`{"profiles": [...]}`); cada perfil trae `username`.
    Extracción defensiva sin asumir una sola forma."""
    if isinstance(users_payload, dict):
        for key in ("profiles", "users", "data"):
            if isinstance(users_payload.get(key), list):
                users_payload = users_payload[key]
                break
        else:
            return []
    if not isinstance(users_payload, list):
        return []
    names = []
    for item in users_payload:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            name = item.get("username") or item.get("profile_username") or item.get("name")
            if name:
                names.append(str(name))
    return names


def fetch_uploadpost_stats(
    api_key: str | None = None,
    urlopen_fn: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    """Métricas reales de Upload-Post. Endpoints documentados (ver docstring
    del módulo): users, history, total-impressions por perfil. Nunca lanza."""
    api_key = api_key or _vault_value("UPLOADPOST_API_KEY")
    if not api_key:
        return {"status": "sin_llave", "detail": "UPLOADPOST_API_KEY no está en el vault"}

    result: dict[str, Any] = {"status": "ok"}

    users = _uploadpost_get("/api/uploadposts/users", api_key, urlopen_fn)
    if "_error" in users:
        result["profiles_error"] = users
        profiles: list[str] = []
    else:
        profiles = _extract_profile_usernames(users)
        result["profiles"] = profiles

    history = _uploadpost_get("/api/uploadposts/history?limit=100", api_key, urlopen_fn)
    if "_error" in history:
        result["history_error"] = history
    else:
        entries = history.get("history") or []
        per_platform: dict[str, int] = {}
        successes = 0
        for entry in entries:
            platform = str(entry.get("platform") or "desconocida")
            per_platform[platform] = per_platform.get(platform, 0) + 1
            if entry.get("success"):
                successes += 1
        result["posts_total"] = history.get("total", len(entries))
        result["posts_in_page"] = len(entries)
        result["posts_success_in_page"] = successes
        result["posts_per_platform"] = per_platform

    impressions: dict[str, Any] = {}
    for profile in profiles:
        resp = _uploadpost_get(
            f"/api/uploadposts/total-impressions/{urllib.parse.quote(profile)}",
            api_key, urlopen_fn,
        )
        if "_error" in resp:
            impressions[profile] = {"status": "error", **resp}
        else:
            impressions[profile] = {
                "status": "ok",
                "total_impressions_30d": resp.get("total_impressions"),
                "per_platform": resp.get("per_platform", {}),
            }
    if impressions:
        result["impressions_30d"] = impressions

    if "profiles_error" in result and "history_error" in result:
        result["status"] = "error"
    return result


# ---------------------------------------------------------------------------
# Filas Baserow
# ---------------------------------------------------------------------------

def build_metric_rows(
    youtube_results: dict[str, dict[str, Any]],
    uploadpost_results: dict[str, Any],
    fecha: str,
) -> list[dict[str, Any]]:
    """Traduce los resultados crudos a filas de `metricas_diarias`:
    una por (oficina=canal, métrica), valores redondeados a 2 decimales.
    Solo emite filas de datos que EXISTEN (canal en error → 0 filas)."""
    rows: list[dict[str, Any]] = []

    def add(oficina: str, metrica: str, valor: Any, nota: str = "") -> None:
        if valor is None:
            return
        rows.append({
            "fecha": fecha, "oficina": oficina, "metrica": metrica,
            "valor": round(float(valor), 2), "nota": nota[:250],
        })

    for slug, data in youtube_results.items():
        if data.get("status") != "ok":
            continue
        nota_canal = data.get("channel_title", "")
        add(slug, "yt_subs", data.get("subs"), nota_canal)
        add(slug, "yt_views_total", data.get("views_total"), nota_canal)
        add(slug, "yt_videos_total", data.get("videos_total"), nota_canal)

        videos = [v for v in data.get("videos", []) if v.get("views") is not None]
        if videos:
            top = max(videos, key=lambda v: v["views"])
            add(
                slug, "yt_top_video_views_recientes", top["views"],
                f"[{top['duration_class']}] {top.get('title', '')} ({top.get('id', '')})",
            )
            shorts = sum(1 for v in data.get("videos", []) if v["duration_class"] == "corto")
            largos = sum(1 for v in data.get("videos", []) if v["duration_class"] == "largo")
            add(slug, "yt_videos_recientes_cortos", shorts,
                f"de {len(data.get('videos', []))} recientes")
            add(slug, "yt_videos_recientes_largos", largos,
                f"de {len(data.get('videos', []))} recientes")

        analytics = data.get("analytics_28d") or {}
        if analytics.get("status") == "ok":
            add(slug, "yt_views_28d", analytics.get("views_28d"), "Analytics API v2")
            add(slug, "yt_watch_min_28d", analytics.get("watch_minutes_28d"), "Analytics API v2")

    if uploadpost_results.get("status") == "ok":
        add("uploadpost", "up_posts_total", uploadpost_results.get("posts_total"),
            "historial /api/uploadposts/history")
        per_platform = uploadpost_results.get("posts_per_platform") or {}
        for platform, count in sorted(per_platform.items()):
            add("uploadpost", f"up_posts_{platform}", count, "últimos 100 del historial")
        for profile, imp in (uploadpost_results.get("impressions_30d") or {}).items():
            if imp.get("status") == "ok":
                add(profile, "up_impressions_30d", imp.get("total_impressions_30d"),
                    "total-impressions 30d")
    return rows


def write_to_baserow(
    rows: list[dict[str, Any]],
    write_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Escribe cada fila vía `monitoring.write_metric_row` (que ya maneja
    token del vault, Host header y nunca lanza). Devuelve conteos + el
    resultado por fila para el reporte."""
    write_fn = write_fn or monitoring.write_metric_row
    outcomes = []
    written = failed = 0
    for row in rows:
        res = write_fn(row["fecha"], row["oficina"], row["metrica"], row["valor"], row["nota"])
        ok = res.get("status") == "ok"
        written += ok
        failed += not ok
        outcomes.append({"oficina": row["oficina"], "metrica": row["metrica"], **res})
    return {"written": written, "failed": failed, "results": outcomes}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(
    youtube_results: dict[str, dict[str, Any]],
    uploadpost_results: dict[str, Any],
    rows: list[dict[str, Any]],
) -> None:
    print("== YouTube (Data API v3) ==")
    for slug, data in youtube_results.items():
        if data.get("status") == "ok":
            analytics = data.get("analytics_28d") or {}
            a28 = (
                f"views_28d={analytics.get('views_28d')}"
                if analytics.get("status") == "ok"
                else f"analytics: {analytics.get('status', 'n/a')}"
            )
            print(
                f"  {slug:15s} subs={data.get('subs')} views={data.get('views_total')} "
                f"videos={data.get('videos_total')} recientes={len(data.get('videos', []))} | {a28}"
            )
        else:
            print(f"  {slug:15s} ERROR: {data.get('error', '')[:120]}")

    print("== Upload-Post ==")
    status = uploadpost_results.get("status")
    if status == "ok":
        print(
            f"  perfiles={len(uploadpost_results.get('profiles', []))} "
            f"posts_total={uploadpost_results.get('posts_total')} "
            f"plataformas={uploadpost_results.get('posts_per_platform')}"
        )
        for profile, imp in (uploadpost_results.get("impressions_30d") or {}).items():
            print(f"  {profile}: impresiones_30d={imp.get('total_impressions_30d')} ({imp.get('status')})")
    else:
        print(f"  {status}: {uploadpost_results.get('detail', '')}")

    print(f"== Filas Baserow candidatas: {len(rows)} ==")
    for row in rows:
        print(f"  {row['oficina']:18s} {row['metrica']:28s} {row['valor']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply", action="store_true",
        help="escribe las filas a Baserow (default: dry-run, solo imprime)",
    )
    parser.add_argument("--json", action="store_true", help="salida JSON cruda")
    args = parser.parse_args(argv)

    fecha = datetime.date.today().isoformat()
    youtube_results = fetch_youtube_stats()
    uploadpost_results = fetch_uploadpost_stats()
    rows = build_metric_rows(youtube_results, uploadpost_results, fecha)

    baserow_outcome: dict[str, Any] | None = None
    if args.apply:
        baserow_outcome = write_to_baserow(rows)

    if args.json:
        print(json.dumps({
            "fecha": fecha,
            "youtube": youtube_results,
            "uploadpost": uploadpost_results,
            "rows": rows,
            "baserow": baserow_outcome,
        }, indent=2, ensure_ascii=False))
    else:
        _print_summary(youtube_results, uploadpost_results, rows)
        if baserow_outcome is None:
            print("(dry-run: nada escrito a Baserow; usa --apply para persistir)")
        else:
            print(
                f"Baserow: {baserow_outcome['written']} filas escritas, "
                f"{baserow_outcome['failed']} fallidas"
            )

    if args.apply and baserow_outcome and baserow_outcome["failed"] and not baserow_outcome["written"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
