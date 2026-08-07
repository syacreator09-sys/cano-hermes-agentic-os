#!/usr/bin/env python3
"""Plan POTENCIA P4-B — investigación de viralidad ANTES de producir contenido.

Cierra el primer paso del bucle de contenido: antes de escribir un guion,
buscar qué está funcionando de verdad en cada nicho, POR CANAL.

## Por qué este diseño (verificado leyendo el código, no asumido)

`~/repos/factory-ia-channel-v5/factory/creative/viral_research_engine.py` dice
literal en su docstring "Mock-first ... no external provider calls" -- su
`_raw()` devuelve items FIJOS de prueba, nunca llama a Apify. Y
`providers/apify_reference_radar.py::build_viral_radar_live_request()` solo
CONSTRUYE la petición ("Prepare, but never execute"). **No hay ninguna llamada
Apify real en todo factory-v5** -- son andamiaje/tests, no un buscador vivo.

Lo único real y en producción es el skill
`~/repos/cano-skill-vault/skills/claude/videos-virales/` (uso confirmado por
Cano): HTTP real a api.apify.com, actores reales documentados
(`clockworks/tiktok-scraper` por hashtag, `streamers/youtube-scraper` con
searchQueries, `apify/instagram-hashtag-scraper`), rotación entre varias
cuentas Apify para repartir presupuesto.

Este script hace el FETCH real (rotando entre las llaves `APIFY_API_KEY` +
`APIFY_KEY_1..7` del vault -- 8 en total, verificado) y luego alimenta los
items reales al motor de scoring de factory-v5 vía su parámetro `mock_items=`
(que YA existe en `run()` para esto exacto -- lee su código antes de asumir
que hacía falta forkearlo). Así se reutiliza gratis todo el
dedup/outlier-score/channel-fit/production-brief de
`factory/creative/santmun_integration.py` sin reimplementarlo, y el fetch de
arriba es real de verdad. `viral_research_engine.py` NUNCA se edita -- se usa
por contrato, importado con sys.path, tal cual está.

## Supadata

`SUPADATA_API_KEY` NO existe en el vault (confirmado 5+ veces en la sesión).
`enrich_supadata()` es un stub honesto: si la llave no está, lo dice y no
inventa transcripts. El día que Cano dé de alta la cuenta, basta con que la
llave aparezca en el vault -- el código ya está listo, no hace falta tocarlo.

## Formatos

La búsqueda cubre reels/shorts, largos y carruseles (no solo shorts) --
`classify_format()` usa duración + plataforma para etiquetar cada hallazgo;
el brief final lo separa por formato para que hermes-guiones/produccion
decidan con qué motor producir (video-vox corto/largo, o el motor de
carruseles de factory-v5 si el formato es carrusel).

## Uso

    python scripts/virality_research.py --canal cano-digital-ia --tema "IA en 2026" --dry-run
    python scripts/virality_research.py --canal cano-digital-ia --tema "IA en 2026" --apply --max-items 5

`--dry-run` (default): no llama a Apify, solo muestra el plan.
`--apply`: llama a Apify de verdad, rotando cuentas, con `--max-items` bajo.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VAULT_PATH = Path.home() / ".secrets/credenciales/credenciales/.env"
FACTORY_V5_ROOT = Path.home() / "repos/factory-ia-channel-v5"

# Nuestros 8 canales reales (verificados en vivo con channels.list) -> alias
# del engine de factory-v5 (santmun_integration.CHANNELS/CHANNEL_ALIASES) +
# tema semilla por defecto para la búsqueda. El tema semilla es solo un
# default -- `--tema` en la CLI siempre lo sobreescribe.
CHANNEL_MAP: dict[str, dict[str, str]] = {
    "cano-digital-ia": {"factory_channel": "cano", "tema_semilla": "inteligencia artificial y automatizacion"},
    "cass-healt": {"factory_channel": "cass", "tema_semilla": "medicina estetica y belleza"},
    "sya-animals": {"factory_channel": "sya-animals", "tema_semilla": "animales curiosos"},
    "sya-motive": {"factory_channel": "sya-motive", "tema_semilla": "motivacion y disciplina"},
    "unsolved-lens": {"factory_channel": "unsolved-lens", "tema_semilla": "misterios sin resolver"},
    "cosmic-lens": {"factory_channel": "cosmic-lens", "tema_semilla": "espacio y astronomia"},
    "wild-whiskers": {"factory_channel": "wild-whiskers", "tema_semilla": "gatos y mascotas"},
    "sleepy-lofi": {"factory_channel": "sleepy-lofi", "tema_semilla": "musica lofi para dormir"},
}

APIFY_KEY_ENV_NAMES = ["APIFY_API_KEY"] + [f"APIFY_KEY_{n}" for n in range(1, 8)]
APIFY_RUN_TIMEOUT_S = 120
# Tope de gasto por llamada a un actor -- mismo resguardo que ya usa el
# skill de santmun (--apify-run-budget-usd 0.50 default), portado aqui.
# Apify aborta el run apenas se acerca a este limite (maxTotalChargeUsd es
# un parametro real de su API de actor runs), asi que una corrida nunca
# puede costar mas de esto por plataforma, pase lo que pase.
DEFAULT_MAX_CHARGE_USD_PER_CALL = 0.20


def read_vault_keys(names: list[str], vault_path: Path = VAULT_PATH) -> dict[str, str]:
    """Lee SOLO los nombres pedidos del vault, nunca el resto. Nunca imprime valores."""
    if not vault_path.exists():
        return {}
    wanted = set(names)
    found: dict[str, str] = {}
    for line in vault_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name in wanted:
            value = value.strip().strip('"').strip("'")
            if value:
                found[name] = value
    return found


class ApifyRotationError(RuntimeError):
    def __init__(self, status: int | None, message: str):
        super().__init__(message)
        self.status = status


class ApifyRotation:
    """Puerto a Python del patron de rotacion real de
    cano-skill-vault/skills/claude/videos-virales/scripts/apify_rotation.py
    (ahi via Keychain de macOS; aqui via las llaves numeradas del vault de
    Cano, ya verificadas: 8 en total). Nunca imprime valores de llave."""

    def __init__(self, keys: dict[str, str]):
        if not keys:
            raise ApifyRotationError(None, "sin llaves Apify disponibles en el vault")
        self.keys = list(keys.items())  # [(env_name, value), ...]
        self._cursor = 0
        self._excluded: set[str] = set()

    def _next(self) -> tuple[str, str]:
        for offset in range(len(self.keys)):
            idx = (self._cursor + offset) % len(self.keys)
            name, value = self.keys[idx]
            if name not in self._excluded:
                self._cursor = (idx + 1) % len(self.keys)
                return name, value
        raise ApifyRotationError(None, f"todas las llaves Apify fallaron esta corrida ({sorted(self._excluded)})")

    def run_actor_sync(
        self, actor: str, input_body: dict[str, Any], *, max_items: int,
        max_charge_usd: float = DEFAULT_MAX_CHARGE_USD_PER_CALL,
    ) -> list[dict[str, Any]]:
        """Ejecuta un actor y espera el dataset (run-sync-get-dataset-items),
        rotando de cuenta si la actual devuelve 401/402/429. `max_charge_usd`
        se manda como `maxTotalChargeUsd` -- Apify aborta el run si se
        acerca a ese tope, es un resguardo real de su API, no solo de este
        script."""
        last_error: Exception | None = None
        for _ in range(len(self.keys)):
            env_name, token = self._next()
            url = (
                f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
                f"?token={token}&maxTotalChargeUsd={max_charge_usd}"
            )
            body = json.dumps(input_body).encode("utf-8")
            req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=APIFY_RUN_TIMEOUT_S) as resp:
                    items = json.loads(resp.read())
                    if not isinstance(items, list):
                        raise ApifyRotationError(None, f"respuesta inesperada del actor {actor}")
                    return items[:max_items]
            except urllib.error.HTTPError as exc:
                last_error = ApifyRotationError(exc.code, f"Apify {exc.code} ({env_name}) actor={actor}: {exc.read()[:200]!r}")
                if exc.code in (401, 402, 429):
                    self._excluded.add(env_name)
                    continue
                raise last_error
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                last_error = ApifyRotationError(None, f"{exc.__class__.__name__}: {exc}")
                raise last_error
        raise last_error or ApifyRotationError(None, "sin llaves disponibles")


# --------------------------------------------------------------------------
# Fetch real por plataforma. Actores y forma de input documentados en el
# skill de santmun (SKILL.md, "Notas tecnicas" -- lecciones ya horneadas,
# no reinventar): TikTok por HASHTAG (no keyword search, falla con C098);
# YouTube con searchQueries + sortingOrder=views; Instagram por hashtag.
# --------------------------------------------------------------------------

def fetch_youtube(rotation: ApifyRotation, topic: str, max_items: int) -> list[dict[str, Any]]:
    items = rotation.run_actor_sync(
        "streamers~youtube-scraper",
        {"searchQueries": [topic], "sortingOrder": "views", "dateFilter": "month", "maxResults": max_items},
        max_items=max_items,
    )
    return [_normalize_youtube(it) for it in items]


def fetch_tiktok(rotation: ApifyRotation, topic: str, max_items: int) -> list[dict[str, Any]]:
    hashtag = re.sub(r"\s+", "", topic.lower())
    items = rotation.run_actor_sync(
        "clockworks~tiktok-scraper",
        {"hashtags": [hashtag], "resultsPerPage": max_items},
        max_items=max_items,
    )
    return [_normalize_tiktok(it) for it in items]


def fetch_instagram(rotation: ApifyRotation, topic: str, max_items: int) -> list[dict[str, Any]]:
    hashtag = re.sub(r"\s+", "", topic.lower())
    items = rotation.run_actor_sync(
        "apify~instagram-hashtag-scraper",
        {"hashtags": [hashtag], "resultsType": "reels", "resultsLimit": max_items},
        max_items=max_items,
    )
    return [_normalize_instagram(it) for it in items]


def classify_format(platform: str, duration_seconds: float, is_carousel: bool = False) -> str:
    """corto | largo | reel | carrusel -- separado del youtube_segment interno
    del engine (que solo distingue shorts/midform/longform de YouTube)."""
    if is_carousel:
        return "carrusel"
    if platform in ("tiktok", "instagram"):
        return "reel"
    if duration_seconds <= 60:
        return "corto"
    return "largo"


def _parse_duration(value: Any) -> float:
    """Segundos, sea `value` numerico o texto "HH:MM:SS"/"MM:SS" (formato
    real que devuelve streamers~youtube-scraper, distinto de lo asumido
    inicialmente -- corregido tras una corrida real de smoke)."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    if ":" in text:
        parts = [float(p) for p in text.split(":")]
        seconds = 0.0
        for p in parts:
            seconds = seconds * 60 + p
        return seconds
    try:
        return float(text)
    except ValueError:
        return 0.0


def _normalize_youtube(it: dict[str, Any]) -> dict[str, Any]:
    duration = _parse_duration(it.get("duration") or it.get("lengthSeconds"))
    return {
        "id": str(it.get("id") or it.get("videoUrl") or it.get("url") or ""),
        "platform": "youtube",
        "url": it.get("url") or it.get("videoUrl") or "",
        "title": it.get("title") or "",
        "caption": it.get("description") or it.get("title") or "",
        "author": it.get("channelName") or it.get("channelUrl") or "desconocido",
        "duration": duration,
        "views": int(it.get("viewCount") or it.get("views") or 0),
        "likes": int(it.get("likes") or 0),
        "comments": int(it.get("commentsCount") or 0),
        "shares": 0,
        "age_days": _age_days(it.get("date") or it.get("publishedAt")),
        "formato": classify_format("youtube", duration),
    }


def _normalize_tiktok(it: dict[str, Any]) -> dict[str, Any]:
    duration = _parse_duration(it.get("videoMeta", {}).get("duration") or it.get("duration"))
    return {
        "id": str(it.get("id") or ""),
        "platform": "tiktok",
        "url": it.get("webVideoUrl") or it.get("url") or "",
        "title": (it.get("text") or "")[:120],
        "caption": it.get("text") or "",
        "author": it.get("authorMeta", {}).get("name") or "desconocido",
        "duration": duration,
        "views": int(it.get("playCount") or 0),
        "likes": int(it.get("diggCount") or 0),
        "comments": int(it.get("commentCount") or 0),
        "shares": int(it.get("shareCount") or 0),
        "age_days": _age_days(it.get("createTimeISO")),
        "formato": classify_format("tiktok", duration),
    }


def _normalize_instagram(it: dict[str, Any]) -> dict[str, Any]:
    is_carousel = bool(it.get("childPosts")) or str(it.get("type", "")).lower() == "sidecar"
    return {
        "id": str(it.get("id") or ""),
        "platform": "instagram",
        "url": it.get("url") or "",
        "title": (it.get("caption") or "")[:120],
        "caption": it.get("caption") or "",
        "author": it.get("ownerUsername") or "desconocido",
        "duration": _parse_duration(it.get("videoDuration")),
        "views": int(it.get("videoViewCount") or it.get("likesCount") or 0),
        "likes": int(it.get("likesCount") or 0),
        "comments": int(it.get("commentsCount") or 0),
        "shares": 0,
        "age_days": _age_days(it.get("timestamp")),
        "formato": classify_format("instagram", _parse_duration(it.get("videoDuration")), is_carousel=is_carousel),
    }


def _age_days(value: str | None) -> int:
    if not value:
        return 999
    try:
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return max((datetime.datetime.now(datetime.timezone.utc) - dt).days, 0)
    except (ValueError, TypeError):
        return 999


def enrich_supadata(items: list[dict[str, Any]], vault_keys: dict[str, str]) -> dict[str, Any]:
    """Stub listo-apagado. Si SUPADATA_API_KEY existe, aqui es donde se
    llamaria de verdad (endpoint documentado en supadata.ai/documentation);
    hoy no existe en ningun vault (confirmado 5+ veces), asi que se declara
    ausente en vez de inventar transcripts."""
    key = vault_keys.get("SUPADATA_API_KEY")
    if not key:
        return {"status": "sin_llave", "detail": "SUPADATA_API_KEY no esta en el vault -- alta pendiente en supadata.ai", "items": items}
    # TODO cuando exista la llave: llamar a Supadata por cada item['url'] y
    # anexar transcript real bajo item['transcript']. No implementado a
    # ciegas sin la llave para probarlo de verdad.
    return {"status": "llave_presente_sin_probar", "detail": "SUPADATA_API_KEY existe pero este flujo aun no se probo en vivo", "items": items}


def _load_factory_engine():
    """Importa el engine de factory-v5 por contrato (sys.path), sin copiar
    ni editar su codigo -- 'invocar por contrato, no absorber'."""
    if str(FACTORY_V5_ROOT) not in sys.path:
        sys.path.insert(0, str(FACTORY_V5_ROOT))
    from factory.creative import viral_research_engine  # noqa: PLC0415
    return viral_research_engine


def build_brief(canal: str, tema: str, real_items: list[dict[str, Any]], *, budget: float = 0.0) -> dict[str, Any]:
    engine = _load_factory_engine()
    info = CHANNEL_MAP[canal]
    result = engine.run(
        info["factory_channel"], tema, "multichannel",
        mock_items=real_items or None, budget=budget,
    )
    run_dir = Path(result["root"])
    brief = json.loads((run_dir / "production-brief.json").read_text(encoding="utf-8"))
    ranking = json.loads((run_dir / "viral-ranking.json").read_text(encoding="utf-8"))
    return {"engine_result": result, "production_brief": brief, "viral_ranking": ranking}


def write_workspace_brief(canal: str, tema: str, payload: dict[str, Any]) -> Path:
    fecha = datetime.date.today().isoformat()
    out_dir = ROOT / "storage" / "workspaces" / "virality" / fecha
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{canal}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def write_report(entries: list[dict[str, Any]]) -> Path:
    fecha = datetime.date.today().isoformat()
    report_dir = ROOT / "reports" / "virality"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{fecha}.md"
    lines = [f"# Investigacion de viralidad -- {fecha}", ""]
    for e in entries:
        lines.append(f"## {e['canal']} -- \"{e['tema']}\"")
        lines.append(f"- items reales encontrados: {e['items_encontrados']}")
        lines.append(f"- formatos: {e['formatos']}")
        lines.append(f"- brief: `{e['brief_path']}`")
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--canal", choices=sorted(CHANNEL_MAP), help="default: todos")
    parser.add_argument("--tema", help="default: tema semilla del canal")
    parser.add_argument("--platforms", default="youtube,tiktok,instagram")
    parser.add_argument("--max-items", type=int, default=8)
    parser.add_argument("--apply", action="store_true", help="llama a Apify de verdad (default: dry-run)")
    args = parser.parse_args(argv)

    canales = [args.canal] if args.canal else list(CHANNEL_MAP)
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]

    vault_keys = read_vault_keys(APIFY_KEY_ENV_NAMES + ["SUPADATA_API_KEY"])
    apify_keys = {k: v for k, v in vault_keys.items() if k in APIFY_KEY_ENV_NAMES}

    if not args.apply:
        print(f"(dry-run) canales={canales} platforms={platforms} max_items={args.max_items}")
        print(f"(dry-run) llaves Apify detectadas en el vault: {len(apify_keys)}")
        for c in canales:
            tema = args.tema or CHANNEL_MAP[c]["tema_semilla"]
            print(f"  {c}: tema=\"{tema}\" -> factory_channel={CHANNEL_MAP[c]['factory_channel']}")
        print("(dry-run: nada llamado a Apify; usa --apply para correr de verdad)")
        return 0

    rotation = ApifyRotation(apify_keys)
    entries = []
    for canal in canales:
        tema = args.tema or CHANNEL_MAP[canal]["tema_semilla"]
        real_items: list[dict[str, Any]] = []
        for platform in platforms:
            try:
                if platform == "youtube":
                    real_items += fetch_youtube(rotation, tema, args.max_items)
                elif platform == "tiktok":
                    real_items += fetch_tiktok(rotation, tema, args.max_items)
                elif platform == "instagram":
                    real_items += fetch_instagram(rotation, tema, args.max_items)
            except ApifyRotationError as exc:
                print(f"  [{canal}/{platform}] error: {exc}")

        supadata_result = enrich_supadata(real_items, vault_keys)
        payload = build_brief(canal, tema, real_items)
        payload["supadata"] = {"status": supadata_result["status"], "detail": supadata_result["detail"]}
        brief_path = write_workspace_brief(canal, tema, payload)

        formatos = sorted({it.get("formato") for it in real_items}) if real_items else []
        entries.append({
            "canal": canal, "tema": tema, "items_encontrados": len(real_items),
            "formatos": formatos, "brief_path": str(brief_path),
        })
        print(f"[{canal}] \"{tema}\": {len(real_items)} items reales, formatos={formatos} -> {brief_path}")

    report_path = write_report(entries)
    print(f"\nReporte: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
