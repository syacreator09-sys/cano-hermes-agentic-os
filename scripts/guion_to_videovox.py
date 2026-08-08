#!/usr/bin/env python3
"""Plan POTENCIA T9 -- convierte un guion (short-script.yaml, salida del
skill write-viral-short de factory-v5) al formato scenes.json que
cano-video-vox espera como entrada (input/scenes.json -> `npm run assets`).

## Por qué existe este conversor (y no un bridge más grande)

`skills/scripting/write-viral-short/SKILL.md` (factory-v5) es un procedimiento
para un agente LLM -- describe qué debe hacer (leer oportunidad+identidad,
escribir hook/beats/payoff), no código ejecutable. La escritura real del
guion es trabajo de un agente (ver scripts/write_guion.py, que sí invoca a
Kimi vía `hermes --oneshot`), no algo que este script deba fabricar.

Este módulo es la única parte determinista y verificable del paso: valida
que el YAML que el agente escribió tiene la forma correcta, y lo traduce al
shape EXACTO que espera `cano-video-vox` (verificado leyendo
`src/data/short.json` e `input/scenes.example.json` de ese repo):

    scenes.json (input, lo que gen-video-assets.mjs consume):
      { "title": str, "musicPrompt": str,
        "scenes": [{"id","keyword","narration","imagePrompt","from"}, ...] }

## Schema esperado de short-script.yaml

    title: str
    music_prompt: str
    hook:
      keyword: str
      narration: str
      image_prompt: str
    beats:
      - keyword: str
        narration: str
        image_prompt: str
        from: left|right|bottom|diag   # opcional, default alterna
    payoff:
      keyword: str
      narration: str
      image_prompt: str

`hook` + `beats` + `payoff` se aplanan a `scenes[]` en ese orden, con id
"01", "02", ... y `from` alternado (left/bottom/right/diag) si no se
especifica -- mismo patrón visual que ya usan los ejemplos reales de
video-vox.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

_FROM_CYCLE = ["left", "bottom", "right", "diag"]

REQUIRED_SCENE_FIELDS = ("keyword", "narration", "image_prompt")

# A4 (plan AUTONOMÍA TOTAL, 2026-08-08): los 6 beats fijos que
# `cano-video-vox` espera para long-form (verificado leyendo
# `src/data/long.json` y el tipo `Beat` real en
# `src/scenes/EscenaShort.tsx` de ese repo) -- a diferencia de short
# (hook + 2-4 beats flexibles + payoff), largo es una estructura
# documental fija de 6 beats con nombre semántico propio, no una lista
# genérica.
BEATS_LARGO = ("hook", "context", "claims", "evidence", "counterpoint", "conclusion")


class GuionValidationError(ValueError):
    pass


def _validate_scene_block(block: dict[str, Any], label: str) -> None:
    if not isinstance(block, dict):
        raise GuionValidationError(f"{label}: se esperaba un mapeo, llegó {type(block).__name__}")
    missing = [f for f in REQUIRED_SCENE_FIELDS if not block.get(f)]
    if missing:
        raise GuionValidationError(f"{label}: faltan campos obligatorios {missing}")


def parse_guion(raw: dict[str, Any]) -> dict[str, Any]:
    """Valida el shape completo. Lanza GuionValidationError con un mensaje
    claro por cada problema -- nunca produce un scenes.json a medias."""
    if not raw.get("title"):
        raise GuionValidationError("falta 'title'")
    if not raw.get("music_prompt"):
        raise GuionValidationError("falta 'music_prompt'")
    hook = raw.get("hook")
    payoff = raw.get("payoff")
    beats = raw.get("beats") or []
    if hook is None:
        raise GuionValidationError("falta 'hook'")
    if payoff is None:
        raise GuionValidationError("falta 'payoff'")
    if not isinstance(beats, list) or len(beats) == 0:
        raise GuionValidationError("'beats' debe ser una lista no vacía")

    _validate_scene_block(hook, "hook")
    _validate_scene_block(payoff, "payoff")
    for i, beat in enumerate(beats, start=1):
        _validate_scene_block(beat, f"beats[{i}]")

    return {"title": raw["title"], "music_prompt": raw["music_prompt"], "hook": hook, "beats": beats, "payoff": payoff}


def to_scenes_json(guion: dict[str, Any]) -> dict[str, Any]:
    """Aplana hook + beats + payoff a scenes[] en el shape real de video-vox."""
    ordered_blocks = [guion["hook"], *guion["beats"], guion["payoff"]]
    scenes = []
    for i, block in enumerate(ordered_blocks):
        scene_id = str(i + 1).zfill(2)
        from_dir = block.get("from") or _FROM_CYCLE[i % len(_FROM_CYCLE)]
        scenes.append({
            "id": scene_id,
            "keyword": block["keyword"],
            "narration": block["narration"],
            "imagePrompt": block["image_prompt"],
            "from": from_dir,
        })
    return {"title": guion["title"], "musicPrompt": guion["music_prompt"], "scenes": scenes}


def parse_guion_largo(raw: dict[str, Any]) -> dict[str, Any]:
    """Valida el shape largo: title, music_prompt, y un bloque por cada uno
    de los 6 BEATS_LARGO (no 'beats' genérico como short). Mismos mensajes
    de error claros por problema, nunca produce un resultado a medias."""
    if not raw.get("title"):
        raise GuionValidationError("falta 'title'")
    if not raw.get("music_prompt"):
        raise GuionValidationError("falta 'music_prompt'")
    blocks: dict[str, Any] = {}
    for beat in BEATS_LARGO:
        block = raw.get(beat)
        if block is None:
            raise GuionValidationError(f"falta el beat '{beat}'")
        _validate_scene_block(block, beat)
        blocks[beat] = block
    return {"title": raw["title"], "music_prompt": raw["music_prompt"], **blocks}


def to_scenes_json_largo(guion: dict[str, Any]) -> dict[str, Any]:
    """Aplana los 6 beats fijos a scenes[] en el shape largo de video-vox
    -- igual que to_scenes_json() pero cada escena lleva además su
    "beat" (hook/context/claims/.../conclusion), que gen-video-assets.mjs
    de cano-video-vox todavía no consume hoy (confirmado leyendo ese
    script: no referencia "beat" en ninguna parte) -- lo incluye igual
    porque src/data/long.json, la forma final que sí llega al render, sí
    lo requiere; enchufar ese threading en gen-video-assets.mjs queda
    como follow-up explícito en ese repo, no inventado aquí."""
    scenes = []
    for i, beat in enumerate(BEATS_LARGO):
        block = guion[beat]
        scene_id = str(i + 1).zfill(2)
        from_dir = block.get("from") or _FROM_CYCLE[i % len(_FROM_CYCLE)]
        scenes.append({
            "id": scene_id,
            "beat": beat,
            "keyword": block["keyword"],
            "narration": block["narration"],
            "imagePrompt": block["image_prompt"],
            "from": from_dir,
        })
    return {"title": guion["title"], "musicPrompt": guion["music_prompt"], "scenes": scenes}


def convert_file(guion_path: Path, out_path: Path, *, formato: str = "corto") -> dict[str, Any]:
    raw = yaml.safe_load(guion_path.read_text(encoding="utf-8"))
    if formato == "largo":
        guion = parse_guion_largo(raw)
        scenes_json = to_scenes_json_largo(guion)
    else:
        guion = parse_guion(raw)
        scenes_json = to_scenes_json(guion)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(scenes_json, indent=2, ensure_ascii=False), encoding="utf-8")
    return scenes_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("guion", type=Path, help="ruta a short-script.yaml (o long-script.yaml con --formato largo)")
    parser.add_argument("--out", type=Path, required=True, help="ruta de salida scenes.json")
    parser.add_argument("--formato", choices=("corto", "largo"), default="corto")
    args = parser.parse_args(argv)

    try:
        scenes_json = convert_file(args.guion, args.out, formato=args.formato)
    except GuionValidationError as exc:
        print(f"guion inválido: {exc}", file=sys.stderr)
        return 1
    except (OSError, yaml.YAMLError) as exc:
        print(f"error leyendo/parseando {args.guion}: {exc}", file=sys.stderr)
        return 1

    print(f"OK: {len(scenes_json['scenes'])} escenas -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
