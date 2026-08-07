#!/usr/bin/env python3
"""Plan POTENCIA T9 -- escribe el guion real de un brief de viralidad.

La escritura del guion es trabajo de un LLM (hook/beats/payoff con
gancho real, no una plantilla determinista) -- este script arma el prompt
siguiendo el procedimiento declarado en
`~/repos/factory-ia-channel-v5/skills/scripting/write-viral-short/SKILL.md`
("Entradas: opportunity, identity" -- opportunity = el brief de viralidad
de P4-B, identity = el perfil del canal) y lo despacha a Kimi vía
`hermes --oneshot` (tier-0, motor gratis de oficinas -- CLAUDE.md raíz,
sección "Invocar Hermes Agent desde script"). NUNCA fabrica el guion en
Python: si `hermes` falla o el YAML que devuelve no es válido, se reporta
el error, no se inventa contenido.

Perfil de producción por canal (santmun_integration.CHANNELS +
videos-virales SKILL.md "Perfiles CANO de búsqueda y producción") --
determina el tono del prompt, no el motor final (eso lo decide
hermes-produccion según formato).

Flujo completo:
  brief de viralidad (storage/workspaces/virality/<fecha>/<canal>.json)
    -> prompt con write-viral-short + perfil del canal
    -> hermes --oneshot --model kimi-k2.6 --provider kimi (YAML crudo)
    -> guion_to_videovox.parse_guion() valida
    -> guion_to_videovox.to_scenes_json() convierte
    -> storage/workspaces/guiones/<fecha>/<canal>.scenes.json

Uso:
    python scripts/write_guion.py --canal cano-digital-ia --brief storage/workspaces/virality/2026-08-07/cano-digital-ia.json --dry-run
    python scripts/write_guion.py --canal cano-digital-ia --brief ... --apply
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from guion_to_videovox import GuionValidationError, parse_guion, to_scenes_json  # noqa: E402

import yaml

ROOT = Path(__file__).resolve().parents[1]

# Perfil de producción por canal (santmun_integration.CHANNELS via
# scripts/virality_research.py::CHANNEL_MAP, mismo alias). El perfil define
# el tono/exigencia editorial del prompt -- ver videos-virales SKILL.md
# "Perfiles CANO de búsqueda y producción".
CHANNEL_PROFILE = {
    "cano-digital-ia": "systems-explainer",
    "cass-healt": "tool-tutorial",
    "sya-animals": "incredible-world",
    "sya-motive": "vox-documentary",
    "unsolved-lens": "vox-documentary",
    "cosmic-lens": "incredible-world",
    "wild-whiskers": "incredible-world",
    "sleepy-lofi": "vox-documentary",
}

PROFILE_BRIEF = {
    "vox-documentary": "noticias, historias y hechos explicables; exige fuente y cronología clara.",
    "tool-tutorial": "pasos reproducibles de una herramienta o rutina; exige pasos comprobables.",
    "systems-explainer": "automatizaciones, sistemas o arquitectura explicados simple; exige ejemplo primario.",
    "incredible-world": "mundos, historias o ciencia sorprendente; exige corroboración.",
}

GUION_PROMPT_TEMPLATE = """Eres un guionista de shorts virales en español (skill write-viral-short: escribe hook, beats y payoff para Short/Reel).

Perfil de canal: {profile} -- {profile_brief}
Tema: {tema}

Referencias de qué está funcionando ahora mismo en este nicho (de una búsqueda real de contenido viral, úsalas como inspiración de FORMATO y GANCHO, nunca copies texto ni datos):
{referencias}

Escribe un guion de short vertical (25-45s) en ESPAÑOL siguiendo EXACTAMENTE este formato YAML, sin texto antes ni después, sin bloque de código markdown:

title: "<titulo corto y llamativo>"
music_prompt: "<descripcion en ingles del estilo de musica de fondo, para un generador de musica IA>"
hook:
  keyword: "<3-5 palabras en MAYUSCULAS, el gancho visual>"
  narration: "<1 frase que engancha en los primeros 3 segundos>"
  image_prompt: "<descripcion en ingles de la imagen para ese momento>"
beats:
  - keyword: "<palabras clave>"
    narration: "<frase que desarrolla la idea>"
    image_prompt: "<descripcion en ingles de la imagen>"
  - keyword: "<palabras clave>"
    narration: "<frase que desarrolla la idea>"
    image_prompt: "<descripcion en ingles de la imagen>"
payoff:
  keyword: "<palabras clave del cierre>"
  narration: "<frase de cierre con CTA suave o remate>"
  image_prompt: "<descripcion en ingles de la imagen final>"

Reglas: 2 a 4 beats. Narración siempre en español natural, hablado, sin sonar a IA. image_prompt siempre en inglés, concreto y visual. Nunca inventes datos/cifras que no estén en las referencias."""


def build_prompt(brief: dict[str, Any], canal: str, tema: str) -> str:
    profile = CHANNEL_PROFILE.get(canal, "systems-explainer")
    ranking = brief.get("viral_ranking") or []
    referencias = "\n".join(
        f"- \"{r.get('title', '')[:80]}\" ({r.get('platform', '?')}, opportunity_score={r.get('opportunity_score')})"
        for r in ranking[:5]
    ) or "(sin referencias reales disponibles para este brief)"
    return GUION_PROMPT_TEMPLATE.format(
        profile=profile, profile_brief=PROFILE_BRIEF[profile], tema=tema, referencias=referencias,
    )


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:ya?ml)?\s*\n(.*?)\n```\s*$", text, re.DOTALL)
    return match.group(1) if match else text


def invoke_hermes(prompt: str, *, usage_file: Path, model: str = "kimi-k2.6", provider: str = "kimi", timeout_s: int = 180) -> str:
    """Invoca `hermes --oneshot` (tier-0, gratis) y devuelve stdout crudo.
    Nunca fabrica un guion si el subproceso falla -- propaga el error."""
    usage_file.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["hermes", "--oneshot", prompt, "--model", model, "--provider", provider, "--usage-file", str(usage_file)],
        capture_output=True, text=True, timeout=timeout_s,
    )
    if result.returncode != 0:
        raise RuntimeError(f"hermes --oneshot salió con código {result.returncode}: {result.stderr[:500]}")
    return result.stdout


def write_guion(canal: str, brief_path: Path, tema: str | None, *, apply: bool) -> dict[str, Any]:
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    tema_real = tema or brief.get("engine_result", {}).get("run_id", canal).rsplit("-", 1)[0]
    prompt = build_prompt(brief, canal, tema_real)

    fecha = brief_path.parent.name
    out_dir = ROOT / "storage" / "workspaces" / "guiones" / fecha
    usage_file = out_dir / f"{canal}.usage.json"
    yaml_path = out_dir / f"{canal}.short-script.yaml"
    scenes_path = out_dir / f"{canal}.scenes.json"

    if not apply:
        return {"status": "dry_run", "prompt_preview": prompt[:400], "would_write": str(scenes_path)}

    raw_output = invoke_hermes(prompt, usage_file=usage_file)
    yaml_text = _strip_markdown_fence(raw_output)
    out_dir.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(yaml_text, encoding="utf-8")

    try:
        raw = yaml.safe_load(yaml_text)
        guion = parse_guion(raw)
    except (yaml.YAMLError, GuionValidationError) as exc:
        return {"status": "error", "detail": f"guion invalido: {exc}", "raw_output_path": str(yaml_path)}

    scenes_json = to_scenes_json(guion)
    scenes_path.write_text(json.dumps(scenes_json, indent=2, ensure_ascii=False), encoding="utf-8")

    usage = json.loads(usage_file.read_text(encoding="utf-8")) if usage_file.exists() else {}
    return {
        "status": "ok", "canal": canal, "escenas": len(scenes_json["scenes"]),
        "yaml_path": str(yaml_path), "scenes_path": str(scenes_path),
        "usage": {"estimated_cost_usd": usage.get("estimated_cost_usd"), "model": usage.get("model")},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--canal", required=True, choices=sorted(CHANNEL_PROFILE))
    parser.add_argument("--brief", required=True, type=Path, help="ruta al brief de viralidad (P4-B)")
    parser.add_argument("--tema", help="default: derivado del brief")
    parser.add_argument("--apply", action="store_true", help="invoca hermes de verdad (default: dry-run)")
    args = parser.parse_args(argv)

    if not args.brief.exists():
        print(f"no existe el brief: {args.brief}", file=sys.stderr)
        return 1

    result = write_guion(args.canal, args.brief, args.tema, apply=args.apply)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in ("ok", "dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
