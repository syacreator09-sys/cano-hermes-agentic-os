# adaptive-content-orchestrator

Skill de orquestación de `office-content` que envuelve
`~/repos/cano-adaptive-content-skill` (repo propio, editable, F8.4 del plan Prometeo).
Convierte una solicitud de contenido en un **brief editorial de producción usable** por
canal — no una simple clasificación — sin ejecutar nunca un proveedor real.

## Qué planifica (según lo que el propio repo declara — `docs/PROVIDERS.md`, `skill.yaml`)

- **Research**: descubrimiento (`apify`, modo mock) y transcripts (`supadata`, modo
  mock_cache, cache_first) — decisiones, no transporte real.
- **Video**: ruteo por duración (`video_vox_short` ≤60s, `video_explainer_pro` 61-180s,
  explainer seccionado >180s), destino de ejecución futuro
  `syacreator09-sys/factory-ia-channel-v5`, adapter `PLAN_ONLY`.
- **Carrusel**: repo `syacreator09-sys/cano-carousel-skills`, rama por canal
  (`feature/cano-carousel-skills-v1` para Cano, `feature/cass-native-carousel-skills-v1`
  para Cass), slide count adaptativo (1 apertura + 1 por punto + 1 cierre, tope 12).
- **ImageGen nativa**: `chatgpt_native_imagegen` como proveedor primario, fallback
  `GPT_NATIVE_HANDOFF` — solo se emite "capability acknowledgement" explícito, nunca
  ejecución de imagen.
- **Voz**: `edge_tts_current` (primario), `modal_tts_existing` (fallback),
  `elevenlabs` (premium, solo si se declara explícito) — ejecución deshabilitada en
  modo standalone.
- **Remotion**: destino de render de video declarado en `docs/PROVIDERS.md`
  (`video: remotion`) y `docs/INTEGRATION.md` — ejecución deshabilitada aquí.
- **QA por canal**: `creative_brief` obligatorio (tesis, 3 hooks terminados + 1
  recomendado, outline narrativo, 1-3 CTA + 1 recomendado, dirección visual,
  guardrails editoriales/claims, 5 quality checks) validado contra
  `contracts/*.schema.json` antes de emitir `PLAN_ONLY_NOT_EXECUTED`.

## Canales cubiertos

`cano-digital-ai`, `sya-animals`, `sya-motive`, `cass-health-beauty`, `unsolved-lens`,
`sleepy-lofi`, `cosmic-lens-tv`, `wild-whiskers` — perfiles operativos en
`profiles/channel-profiles.json`, perfiles editoriales en `profiles/editorial-profiles.json`.

## Invocación

```bash
cd ~/repos/cano-adaptive-content-skill
source .venv/bin/activate
python -c "
from adaptive_content_orchestrator import build_plan
plan = build_plan({
    'channel_id': 'cano-digital-ai',
    'topic': '...',
    'execution_mode': 'CONSTRUCTION_ONLY',
    'external_calls': False,
    'paid_calls': False,
    'publication': False,
    'human_review_required': True,
    'allow_kie': False,
})
"
```

O por CLI instalada (`pyproject.toml`): `cano-adaptive-validate`, `cano-adaptive-plan`.

## Construction-only por diseño (verificado, no asumido)

`skill.yaml`: `execution_mode: CONSTRUCTION_ONLY`, `integrated_with_factory: false`.
`docs/PROVIDERS.md`: contadores de seguridad obligatorios
`external_calls=0, paid_calls=0, kie_invocations=0, publication_attempts=0,
repository_installations=0`. Corrida real de `scripts/validate_skill.py`
(2026-08-06, ver abajo) confirma los 5 contadores en cero — el código coincide con lo
que declara, sin contradicción.

Cualquier intento de request que cambie
`{execution_mode, external_calls, paid_calls, publication, human_review_required,
allow_kie}` debe fallar (`SKILL.md` del propio repo, sección "Immutable safety").

## Integración con Factory V5 — aditiva, no invasiva

Este skill NO trae su propio puente a Factory V5 (no hay ningún archivo con "factory"
en el nombre dentro del repo salvo la referencia declarativa en `skill.yaml`:
`repositories.factory_video.execution: prohibited_in_standalone`). El puente real es
el skill `factory-v5-contract` (Parte 1 de F8): cuando un brief de este orquestador
necesite ejecutarse de verdad, se entrega como input al comando correspondiente de
`factory.py` vía ese skill — con su propio gating de `ApprovalRequest` para todo lo
sensible. Este skill no reescribe nada de Factory V5, solo produce el plan que
Factory V5 (por contrato) podría consumir más adelante.

## Procedure

1. Confirmar objetivo, canal, tema y restricciones explícitas del operador.
2. Recuperar contexto mínimo desde Nexus (briefs previos del mismo canal/tema, para
   evitar duplicados).
3. Ejecutar `build_plan(...)` en modo seguro (`CONSTRUCTION_ONLY` forzado, sin
   excepción) dentro del venv propio del repo.
4. Validar el `creative_brief` resultante contra `contracts/*.schema.json` y los
   quality gates (hook no genérico, outline no repite la intro, CTA alineado al
   objetivo, claims con gate de verificación si aplica).
5. Registrar el brief, costo (siempre 0 en esta etapa) y aprendizajes candidatos en
   Nexus. La ejecución real (research, imagen, voz, render, publicación) es un paso
   humano/posterior fuera de este skill.

## Estado de rama y validación (2026-08-06)

- `main` de `cano-adaptive-content-skill` solo tenía `README.md` (2 commits). Dos
  ramas remotas sin mergear: `agent/restructure-adaptive-content-v2` (102 commits,
  v0.3.0, CI en GitHub Actions con 10/10 corridas recientes en verde) y
  `feature/standalone-v1` (72 commits, sin `.github/workflows/`, tope v0.2 según su
  propio changelog). Ganadora confirmada por evidencia:
  `agent/restructure-adaptive-content-v2` — más commits, único con CI, superset de
  `feature/standalone-v1` (`git diff --stat` entre ambas: +1701/-929 líneas, incluye
  `creative_brief.py` nuevo, `profiles/editorial-profiles.json` nuevo,
  `docs/EDITORIAL_OUTPUT.md` nuevo).
- Checkout local de `agent/restructure-adaptive-content-v2`, venv propio
  (`.venv`, Python 3.11), `pip install -e ".[dev]"`.
- `pytest -q` → **49 passed** (coincide exacto con `docs/VALIDATION_REPORT.md` del
  propio repo: `TESTS=49_PASSED`).
- `python scripts/validate_skill.py` → `STANDALONE_SKILL_VALIDATION=PASS`,
  `status: PASS`, `external_calls: 0`, `paid_calls: 0`, `kie_invocations: 0`,
  `publication_attempts: 0`, `repository_installations: 0`, `profile_count: 8`,
  `example_count: 11`.
- PR abierto en `cano-adaptive-content-skill` proponiendo merge de
  `agent/restructure-adaptive-content-v2` → `main` (sin mergear — decisión de Cano).
