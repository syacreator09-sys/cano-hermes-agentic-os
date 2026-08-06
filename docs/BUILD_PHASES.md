# Build Phases — auto-construccion de Hermes desde git

> El contrato para que el Claude Code de la maquina Hermes construya TODO con
> una sola instruccion del operador:
> **"analiza los ultimos commits de cano-ai-command-center y cano-hermes-agentic-os y construye"**
>
> Fuente de verdad de capacidades: `cano-ai-command-center/.command-center/
> hermes-remote/CAPABILITY_HANDOFF_FACTORY_V5.md` (auditoria 2026-08-06).
> Ese doc manda sobre cualquier doc viejo que lo contradiga.

## Fase H0 — Sincronizar y leer (sin instalar nada)

1. `git pull` de ambos repos.
2. Leer `START-HERE-HERMES-REMOTE.md` (tiene la instruccion de arranque),
   `CAPABILITY_HANDOFF_FACTORY_V5.md`, `REPOS_MANIFEST.md`,
   `INSTALL_MANIFEST_HERMES.md`.
3. Reportar al operador el plan de la corrida ANTES de instalar.

## Fase H1 — Instalar base

Seguir `INSTALL_MANIFEST_HERMES.md` §1-4 (binarios, npm globales, pip,
node_modules internos). i5: saltar todo lo CUDA/GPU local.

## Fase H2 — Clonar el arbol completo

`REPOS_MANIFEST.md`: monorepo + los 12 repos anidados EN SUS RUTAS EXACTAS
+ launchers prioritarios. Los solo-locales (ugc-forge, etc.) se piden al
operador como transferencia out-of-band.

## Fase H3 — Credenciales (solo operador)

Presentar `ENV_TEMPLATE_HERMES.env.example` al operador y esperar los valores
out-of-band. NUNCA pedirlos por chat ni aceptarlos por git. Sin valores, las
fases H5+ corren en modo $0 (research metadata off, renders locales on).

## Fase H4 — Gate de paridad

`python scripts/factory_v5_preflight.py --output preflight-hermes.json`
(0 llamadas facturables). Reportar tabla OK/PARCIAL/N-A por capacidad.
`pytest -q` en factory-v5 y en ugc-commerce-studio deben pasar.

## Fase H5 — Nucleo autonomo

1. Implementar el loop de `HEADLESS_ENGINE.md` como proceso PM2
   (`hermes-master`): cola SQLite, lanzador de sesiones headless, validador,
   ruteo de modelos (portar `ai.py` + `scripts/council/` del monorepo).
2. Bot de Telegram (comandos /estado /aprobar /rechazar /tarea /briefing /parar,
   restringido a TELEGRAM_OPERATOR_CHAT_ID).
3. Scheduler node-cron con las cadencias de `KAI_AUTONOMOUS_DESIGN.md`.

## Fase H6 — Oficinas

Crear `offices/` desde `_TEMPLATE-OFICINA/` segun `SPAWNING_PROTOCOL.md`:
las 6 iniciales, registradas, en modo `isolation: folder` (Docker despues).

## Fase H7 — Prueba en seco (1 dia, $0)

Un ciclo completo sin gastar: research con artefactos ya existentes en
`storage/research/` → guion nuevo → render local (edge-tts + Remotion/ffmpeg)
→ draft → gate de publicacion en Telegram (el operador NO aprueba; se verifica
que la cola retiene). Criterio: video draft real en deliveries/ + gate visible
en Telegram + cero gasto.

## Fase H8 — Encendido gradual de gasto (cada uno con gate)

Orden: 1) Kie smoke (1 task, nano-banana o grok-imagine, ~4-35 creditos)
→ 2) ElevenLabs voz aprobada → 3) Higgsfield UGC con producto REAL
(plan → approve → generate). Cada paso: aprobacion Telegram previa + reporte
de costo posterior.

## Fase H9 — Operacion continua

Cadencias activas + briefing diario + jueves de auto-actualizacion
("revisar commits nuevos de ambos repos, aplicar cambios, reportar").

## Backlog de MEJORA (donde Hermes supera al origen)

| # | Mejora | Contexto |
|---|---|---|
| 1 | Atribucion UTM (greenfield total — palanca #1 identificada) | ningun repo la tiene; diseñar UTM por content_key + tabla clicks/conversiones |
| 2 | research→guion cableado (en origen NUNCA se conecto) | consumir storage/research/ para escribir prosa con NIM/Sonnet |
| 3 | Stage-dispatcher real de pipelines YAML (en origen son decorativos) | unir pipelines/*.yaml con providers en codigo |
| 4 | Render HyperFrames real (en origen instalado pero jamas invocado) | reemplazar el ffmpeg-still por render CLI real |
| 5 | Guiones UGC generativos (en origen: plantilla fija de 5 escenas) | scripts por producto con evidencia verificada |

## Reglas permanentes

- Nada se publica ni se paga sin gate Telegram del operador.
- Todo commit de Hermes es tematico y sin secretos (escanear staged antes).
- Ante contradiccion docs vs codigo: gana el codigo; reportar el doc mentiroso.
- Ante duda de arquitectura: gana este repo (StarHome OS); ante duda de dominio
  de negocio: gana `.command-center/hermes-remote/` del monorepo.
