#!/usr/bin/env python3
"""Plan POTENCIA P2 -- oficina hermes-ads: genera paquetes de campaña DRAFT
invocando por contrato el motor de `cano-ai-command-center/01-offices/
ads-studio` (repo SOLO LECTURA -- se importa, nunca se edita ni se copia).

## Por qué reutilizar ads-studio y no construir de cero

Ya existe, maduro: 11 motores (campaign_builder, ad_copywriter, budget_plan,
creative_adapter/sourcer/brief_gen, image/video_ad_gen, meta/tiktok/
google_publisher), 14 archivos de test, y guardarraíles explícitos en
`config/guardrails.py` (`AUTHORIZED_DEFAULT=False`, `PUBLISH_ENABLED=False`,
`DEFAULT_STATUS="DRAFT"`) que este bridge NUNCA fuerza a True. Comparado con
el skill `meta-ads-launch` de santmun (solo Meta, llama al MCP directo): se
adopta su convención de nombrar toda campaña de prueba con prefijo
`[TEST] <slug> -- <fecha>` (ver `_slug_with_test_prefix`), pero el motor de
producción sigue siendo ads-studio por ser multi-plataforma y ya guardado.

## Publicación

`build_campaign()` de ads-studio jamás publica -- solo escribe
`outputs/<canal>/<platform>/<slug>/` con `campaign.json` (status DRAFT) +
`BRIEF.md` diciendo explícitamente "NO PUBLICAR SIN APROBACIÓN". Publicar de
verdad es un paso manual humano desde el Ads Manager de cada plataforma, o
(cuando Cano decida activarlo) el mismo patrón PENDING_NATIVE_TOOL que ya usa
`cano_hermes/business/cass.py` para Shopify/Meta vía MCP de una sesión Claude.

## Canales

Nuestros 8 canales de YouTube no son 1:1 con los 4 canales de ads-studio
(cano-digital, cass-aspid, sya-motive, sya-animals -- los negocios reales
que sí anuncian, no cada canal de contenido). CHANNEL_MAP mapea explícito;
un canal sin equivalente comercial (unsolved-lens, cosmic-lens,
wild-whiskers, sleepy-lofi -- canales de contenido puro, no negocios con
producto que anunciar) no tiene entrada y el bridge lo rechaza con un
mensaje claro, no lo fuerza a un canal ads-studio arbitrario.

## Uso

    python scripts/ads_bridge.py --canal cano-digital-ia --platform meta --slug prueba-t10 --dry-run
    python scripts/ads_bridge.py --canal cano-digital-ia --platform meta --slug prueba-t10 --apply
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ADS_STUDIO_ROOT = Path.home() / "repos/cano-ai-command-center/01-offices/ads-studio"
# NUNCA escribir dentro de cano-ai-command-center (solo lectura, regla dura
# de toda la sesion) -- build_campaign() acepta outputs_root, se redirige
# aqui. Un intento anterior de generar de verdad escribio en el outputs/
# del repo solo-lectura por usar el default de la funcion sin overridearlo;
# corregido antes de commitear.
ADS_OUTPUTS_ROOT = ROOT / "storage" / "workspaces" / "ads"

# Nuestro canal (YouTube/contenido) -> canal de negocio real en ads-studio.
CHANNEL_MAP = {
    "cano-digital-ia": "cano-digital",
    "cass-healt": "cass-aspid",
    "sya-motive": "sya-motive",
    "sya-animals": "sya-animals",
}


def _load_ads_studio():
    """Importa por contrato (sys.path), nunca copia ni edita el repo
    solo-lectura. Falla con un mensaje claro si ads-studio no está donde
    se espera -- nunca inventa un resultado."""
    if str(ADS_STUDIO_ROOT) not in sys.path:
        sys.path.insert(0, str(ADS_STUDIO_ROOT))
    from engine import campaign_builder  # noqa: PLC0415
    return campaign_builder


def slug_with_test_prefix(base_slug: str) -> str:
    """Convención adoptada del skill meta-ads-launch de santmun: toda
    campaña generada por este bridge lleva [TEST] + fecha en el nombre,
    para nunca confundirla con una campaña real ya aprobada/publicada."""
    fecha = datetime.date.today().isoformat()
    return f"[TEST] {base_slug} -- {fecha}"


def build_draft_campaign(
    canal: str, platform: str, base_slug: str, *,
    objective: str | None = None, daily_budget_mxn: float = 100.0,
    duration_days: int = 14, apply: bool,
) -> dict[str, Any]:
    if canal not in CHANNEL_MAP:
        return {
            "status": "sin_canal_comercial",
            "detail": f"'{canal}' no tiene canal de negocio equivalente en ads-studio ({sorted(CHANNEL_MAP)}); es contenido puro, no un negocio con producto que anunciar.",
        }
    ads_canal = CHANNEL_MAP[canal]
    slug = slug_with_test_prefix(base_slug)

    if not apply:
        return {
            "status": "dry_run", "canal": canal, "ads_canal": ads_canal, "platform": platform,
            "slug": slug, "would_generate": True, "publish": False,
        }

    campaign_builder = _load_ads_studio()
    ADS_OUTPUTS_ROOT.mkdir(parents=True, exist_ok=True)
    output_dir = campaign_builder.build_campaign(
        ads_canal, platform, slug,
        objective=objective, daily_budget_mxn=daily_budget_mxn, duration_days=duration_days,
        generate_images=False, generate_video=False,  # opt-in explicito, nunca por defecto
        outputs_root=ADS_OUTPUTS_ROOT,  # NUNCA en command-center -- ver nota arriba
    )
    campaign_json = json.loads((output_dir / "campaign.json").read_text(encoding="utf-8"))
    return {
        "status": "ok", "canal": canal, "ads_canal": ads_canal, "platform": platform,
        "slug": slug, "output_dir": str(output_dir),
        "campaign_status": campaign_json.get("status"),
        "publish": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--canal", required=True, choices=sorted(CHANNEL_MAP) + ["unsolved-lens", "cosmic-lens", "wild-whiskers", "sleepy-lofi"])
    parser.add_argument("--platform", required=True, choices=["meta", "tiktok", "google"])
    parser.add_argument("--slug", required=True)
    parser.add_argument("--objective")
    parser.add_argument("--daily-budget-mxn", type=float, default=100.0)
    parser.add_argument("--duration-days", type=int, default=14)
    parser.add_argument("--apply", action="store_true", help="genera el paquete DRAFT de verdad (default: dry-run, no toca disco)")
    args = parser.parse_args(argv)

    result = build_draft_campaign(
        args.canal, args.platform, args.slug, objective=args.objective,
        daily_budget_mxn=args.daily_budget_mxn, duration_days=args.duration_days, apply=args.apply,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in ("ok", "dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
