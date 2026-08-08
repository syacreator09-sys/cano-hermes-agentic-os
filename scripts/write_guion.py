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
from guion_to_videovox import (  # noqa: E402
    BEATS_LARGO,
    GuionValidationError,
    parse_guion,
    parse_guion_largo,
    to_scenes_json,
    to_scenes_json_largo,
)

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

# A4 (plan AUTONOMÍA TOTAL, 2026-08-08): estructura documental fija de 6
# beats -- verificado leyendo el schema REAL que cano-video-vox espera
# (src/data/long.json + el tipo Beat en src/scenes/EscenaShort.tsx), no
# los "7 capitulos" que decía la mission de la oficina hermes-guiones
# (offices/hermes-guiones/office.yaml -- corregida también en A4). Un
# guion de 7 capítulos no tendría dónde mapear el 7mo en el render real.
LONG_GUION_PROMPT_TEMPLATE = """Eres un guionista de documentales cortos en español (formato largo: 3-10 minutos, estructura de 6 beats fijos).

Perfil de canal: {profile} -- {profile_brief}
Tema: {tema}

Referencias de qué está funcionando ahora mismo en este nicho (de una búsqueda real de contenido viral, úsalas como inspiración de FORMATO y GANCHO, nunca copies texto ni datos):
{referencias}

Escribe un guion documental largo en ESPAÑOL siguiendo EXACTAMENTE este formato YAML, sin texto antes ni después, sin bloque de código markdown. Debe tener EXACTAMENTE estos 6 bloques, con estos nombres exactos:

title: "<titulo corto y llamativo>"
music_prompt: "<descripcion en ingles del estilo de musica de fondo, para un generador de musica IA>"
hook:
  keyword: "<3-5 palabras en MAYUSCULAS, el gancho visual>"
  narration: "<1-2 frases que enganchan en los primeros segundos>"
  image_prompt: "<descripcion en ingles de la imagen para ese momento>"
context:
  keyword: "<palabras clave>"
  narration: "<frase(s) que dan contexto/antecedente del tema>"
  image_prompt: "<descripcion en ingles de la imagen>"
claims:
  keyword: "<palabras clave>"
  narration: "<frase(s) con la afirmación central del video>"
  image_prompt: "<descripcion en ingles de la imagen>"
evidence:
  keyword: "<palabras clave>"
  narration: "<frase(s) con evidencia o fuente concreta que respalda la afirmación>"
  image_prompt: "<descripcion en ingles de la imagen>"
counterpoint:
  keyword: "<palabras clave>"
  narration: "<frase(s) con un contrapunto, objeción o matiz honesto>"
  image_prompt: "<descripcion en ingles de la imagen>"
conclusion:
  keyword: "<palabras clave del cierre>"
  narration: "<frase(s) de cierre con CTA suave o remate>"
  image_prompt: "<descripcion en ingles de la imagen final>"

Reglas: EXACTAMENTE 6 bloques (hook, context, claims, evidence, counterpoint, conclusion), ninguno de más ni de menos. Narración siempre en español natural, hablado, sin sonar a IA. image_prompt siempre en inglés, concreto y visual. Nunca inventes datos/cifras que no estén en las referencias; en 'evidence' cita la fuente real si está en las referencias, o deja el punto como pregunta abierta si no la hay."""


def build_prompt(brief: dict[str, Any], canal: str, tema: str, *, formato: str = "corto") -> str:
    profile = CHANNEL_PROFILE.get(canal, "systems-explainer")
    ranking = brief.get("viral_ranking") or []
    referencias = "\n".join(
        f"- \"{r.get('title', '')[:80]}\" ({r.get('platform', '?')}, opportunity_score={r.get('opportunity_score')})"
        for r in ranking[:5]
    ) or "(sin referencias reales disponibles para este brief)"
    template = LONG_GUION_PROMPT_TEMPLATE if formato == "largo" else GUION_PROMPT_TEMPLATE
    return template.format(
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


def write_guion(canal: str, brief_path: Path, tema: str | None, *, apply: bool, formato: str = "corto") -> dict[str, Any]:
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    tema_real = tema or brief.get("engine_result", {}).get("run_id", canal).rsplit("-", 1)[0]
    prompt = build_prompt(brief, canal, tema_real, formato=formato)

    fecha = brief_path.parent.name
    out_dir = ROOT / "storage" / "workspaces" / "guiones" / fecha
    usage_file = out_dir / f"{canal}.usage.json"
    suffix = "long-script" if formato == "largo" else "short-script"
    yaml_path = out_dir / f"{canal}.{suffix}.yaml"
    scenes_path = out_dir / f"{canal}.scenes.json"

    if not apply:
        return {"status": "dry_run", "prompt_preview": prompt[:400], "would_write": str(scenes_path)}

    raw_output = invoke_hermes(prompt, usage_file=usage_file)
    yaml_text = _strip_markdown_fence(raw_output)
    out_dir.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(yaml_text, encoding="utf-8")

    try:
        raw = yaml.safe_load(yaml_text)
        guion = parse_guion_largo(raw) if formato == "largo" else parse_guion(raw)
    except (yaml.YAMLError, GuionValidationError) as exc:
        return {"status": "error", "detail": f"guion invalido: {exc}", "raw_output_path": str(yaml_path)}

    scenes_json = to_scenes_json_largo(guion) if formato == "largo" else to_scenes_json(guion)
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
    parser.add_argument("--formato", choices=("corto", "largo"), default="corto",
                         help="corto: hook+2-4 beats+payoff (default). largo: 6 beats documentales fijos "
                              f"({', '.join(BEATS_LARGO)}), ver cano-video-vox src/data/long.json.")
    args = parser.parse_args(argv)

    if not args.brief.exists():
        print(f"no existe el brief: {args.brief}", file=sys.stderr)
        return 1

    result = write_guion(args.canal, args.brief, args.tema, apply=args.apply, formato=args.formato)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in ("ok", "dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
