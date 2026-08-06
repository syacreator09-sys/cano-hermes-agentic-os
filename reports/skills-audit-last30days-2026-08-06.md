# Auditoría de skills — últimos 30 días (2026-07-07 → 2026-08-06)

Fuente: historial real de git (`git log`) en ambos repos, más `gh pr list` para
estado real de PRs en GitHub. Command-center se trató estrictamente de solo
lectura: cero escritura, cero ejecución.

---

## Repo 1 — `cano-hermes-agentic-os` (StarHome, editable)

### Contexto importante

El repo entero tiene **48 commits**, todos fechados entre 2026-07-31 y
2026-08-06 (primer commit: `afe539f "chore: initialize Cano Hermes OS
repository"`, 2026-07-31). Es decir: **el 100% de los 58 skills que existen
hoy en `skills/` nacieron dentro de la ventana de 30 días** — no hay skills
"viejos" que se hayan tocado ahora; todo el árbol es nuevo. Por eso, en vez de
una columna nuevo/modificado poco informativa (todo sería "nuevo"), la tabla
marca **iterado** cuando un skill recibió un commit adicional después de su
creación inicial (indica que se retocó tras el primer merge, no solo que
nació en la ventana).

`python scripts/validate.py` (el mismo validador que usa `SkillRegistry`)
corre limpio sobre el estado actual de `main`:

```json
{"status": "ok", "agents": 53, "skills": 58, "notes": 4}
```

Es decir: los 58 skills que están en `main` tienen `manifest.json` + `SKILL.md`
válidos. El problema no está en los 58 que están — está en uno que **falta**.

### Tabla — skills tocados en la ventana

| Skill | Nuevo/Iterado | Última fecha | manifest+SKILL.md ok | Tests dedicados | Referenciado por agente | Estado |
|---|---|---|---|---|---|---|
| container-sandbox | Nuevo (07-31), iterado (08-05: wiring approvals/budget) | 2026-08-05 | Sí | `tests/test_container_sandbox.py` + `tests/test_execution_wiring.py` — 31 tests, **todos pasan** | Sí (`agents/forge/container-builder.yaml`, `agents/candidates/media-render-worker.yaml`) | **Sano** |
| factory-v5-contract | Nuevo | 2026-08-06 | Sí | Ninguno dedicado | No — solo mencionado en `infrastructure/offices/content/README.md`, ningún agente lo trae en `skills:` | **A medias** — existe y es válido, pero no está enganchado a ningún agente |
| command-center-contract | Nuevo | 2026-08-06 | Sí | Ninguno dedicado | No — solo mencionado en `infrastructure/offices/publish/README.md` | **A medias** — mismo patrón que el anterior |
| adaptive-content-orchestrator | Nuevo | 2026-08-06 | Sí | Ninguno dedicado | No — cero referencias fuera de su propia carpeta | **A medias** — huérfano |
| reel-dedup-check | Nuevo | 2026-08-06 | Sí | Ninguno dedicado | No — cero referencias fuera de su propia carpeta | **A medias** — huérfano |
| engineering-loop | Nuevo (solo en rama, **no en `main`**) | 2026-08-06 | Sí en la rama `fix/engineering-loop-skill`; **no existe en `main`** | N/A (no aplica en main) | **Sí, y ahí está el problema**: `agents/engineering/engineering-lead.yaml` referencia `engineering-loop` en su `skills:`, pero el skill no existe en `main` | **ROTO en `main`** — ver hallazgo abajo |
| blocker-review, capture-anything, cash-position, content-opportunity-brief, daily-brief, document-consistency-audit, expense-capture, finance-close, investment-thesis-review, lead-next-action, learning-session, pipeline-review, project-status, weekly-review | Nuevo (Personal Runtime v0.3, PR #2 mergeado) | 2026-08-05 | Sí (los 14) | Sin tests dedicados por skill individual; cubiertos agregadamente por `tests/test_personal_runtime_pack.py` | Sí, cada uno referenciado por su agente correspondiente en `agents/personal/*` | Sanos |
| agent-blueprint, architecture-spec, batch-analysis, browser-automation, budget-routing, capability-audit, capability-routing, code-review, communications, content-pipeline, creative-brief, deep-research, editorial-scoring, evaluation-gates, factory-v5, forge-governance, git-worktrees, graphify-map, infra-ops, integration-build, mcp-build, metrics-learning, nexus-context, repo-analysis, research-plan, scriptwriting, security-review, skill-authoring, source-verification, storyboard, structured-processing, task-governance, task-planning, tdd-build, testing, trend-analysis, trend-radar, ui-review, voice-flow | Nuevo (foundation v0.2.0, PR #1) | 2026-07-31 | Sí (los 38) | Cubiertos por `tests/test_foundation.py` (suite general) | 51/55 referenciados por al menos un agente (ver nota) | Sanos |

Nota sobre referencias: de los 58 skills en `main`, **4 no están referenciados
por ningún agente** (`adaptive-content-orchestrator`, `command-center-contract`,
`factory-v5-contract`, `reel-dedup-check` — filas de arriba). El resto sí
aparece en al menos un `agents/**/*.yaml` bajo `skills:`.

### Hallazgo principal: `engineering-loop` sigue roto en `main`

El propio prompt de esta auditoría citaba `engineering-loop` como un caso
"ya arreglado en PR #6". **Eso no es exacto todavía**: verifiqué con
`git merge-base --is-ancestor` y `gh pr list`:

```
6  fix: create missing engineering-loop skill   fix/engineering-loop-skill   OPEN
5  feat(finance): create finance team...        feat/finance-office          OPEN
```

Ambas PRs existen y contienen el trabajo correcto, pero **ninguna está
mergeada a `main`**. En `main` tal cual está hoy:

- `agents/engineering/engineering-lead.yaml` sigue declarando
  `skills: [engineering-loop]`.
- `skills/engineering-loop/` **no existe** en `main` (solo en la rama
  `fix/engineering-loop-skill`, commit `d9fd357`).

Esto es exactamente la clase de problema que el plan Prometeo ya había
detectado y "arreglado" — el arreglo existe, está bien hecho, pero se quedó
sin mergear. No abrí una PR nueva porque ya existe una correcta esperando
aprobación; mergearla es una decisión de cierre que le corresponde a Cano
(no es ambigua, pero tocar `main` en esta fase de cierre no me toca a mí sin
que él lo pida explícitamente).

### Otros 3 skills "a medias" (huérfanos, no rotos)

`factory-v5-contract`, `command-center-contract`, `adaptive-content-orchestrator`
y `reel-dedup-check` están bien formados (manifest + SKILL.md válidos, pasan
`validate.py`) pero **ningún agente los invoca** todavía vía `skills:` — dos de
ellos (`factory-v5-contract`, `command-center-contract`) sí aparecen
mencionados en la documentación de las oficinas `content` y `publish`, lo que
sugiere que la intención de engancharlos existe pero el wiring en YAML no se
completó. Los otros dos (`adaptive-content-orchestrator`, `reel-dedup-check`)
no tienen ninguna mención fuera de su propia carpeta.

---

## Repo 2 — `cano-ai-command-center` (solo lectura)

Repo enorme; hay **6 directorios `skills/`** distintos más `.agents/skills/`
y `.command-center/skills/` (catálogo/gobernanza). En la ventana de 30 días
hubo **17 commits** que tocaron rutas de skills, afectando **162 carpetas de
skill** (cada una con su propio `SKILL.md`) más un puñado de archivos de
catálogo/spec que no son skills completos.

### Resumen por origen

| Origen | Commits | Carpetas de skill tocadas | Formato | Notas |
|---|---|---|---|---|
| `01-offices/factory-ia-channel-v5/skills/**` | 13 commits (07-27 → 08-05) | ~130 | `SKILL.md` con frontmatter YAML (`name:`/`description:`) — estándar de Claude Skills, **no** `manifest.json` al estilo StarHome | Ver hallazgo de frontmatter faltante abajo |
| `.agents/skills/*` (carousel-production, ugc-video-production, omnichannel-inbound-routing, viral-research) | 2 commits (07-27) | 4 | `SKILL.md` con frontmatter completo | Bien formados, con `references/` y `agents/openai.yaml` donde aplica |
| `.command-center/skills/deprecated/junction-conflicts/20260727-144847/**` | 1 commit (08-05, `ca5e9a7`) | 22 | `SKILL.md` completo | **No es trabajo nuevo real** — es la primera vez que se comitea al repo un árbol de cuarentena que ya existía localmente desde el 2026-07-27 (el nombre de la carpeta lleva esa fecha). El commit del 08-05 solo versiona `.command-center/` por primera vez, no modifica contenido. Incluye una versión *deprecated* de `reel-dedup-check` — homónima mas no relacionada con la de StarHome. |
| `.command-center/skills/specs/*.md` (6 archivos) | 1 commit (08-05) | — | Markdown suelto, **sin frontmatter, sin carpeta propia** | No son skills completos, son fichas-spec de 5 líneas apuntando a un script (`office-readiness`, `production-gatekeeper`, `mcp-auth-healthcheck`, etc.) — trabajo a medias por diseño, pendientes de construir |
| `scripts/skills/*.ps1` + `.command-center/skills/catalog/*` | 2 commits (07-27) | — | Scripts/catálogo, no skills | Infraestructura del catálogo de skills, no un skill en sí |

### Hallazgo: 35 de ~130 skills de factory-v5 son stubs de 2-3 líneas sin frontmatter

Del commit masivo `9c22ed8` (2026-07-27, "sync untracked Factory V5 work"),
**35 carpetas** de skill tienen un `SKILL.md` sin el bloque YAML
`---\nname:\ndescription:\n---` que sí tienen sus ~95 hermanas del mismo
commit. Ejemplos verificados directamente:

- `01-offices/factory-ia-channel-v5/skills/video/build-18-minute-documentary/SKILL.md`
  — 3 líneas: `# Build 18 Minute Documentary` + una frase.
- `01-offices/factory-ia-channel-v5/skills/identity/face-consistency/SKILL.md`
  — 4 líneas, mismo patrón.
- Comparar con `skills/distribution/upload-post-multichannel/SKILL.md` —
  165 líneas, con tablas, ledgers y contratos reales.

Lista completa de las 35 rutas quedó registrada en el análisis (categorías:
`video/*` en su mayoría — 13 de las 35 —, además `identity/*`, `quality/*`,
`assets/*`, `channels/*`, `youtube/*`, `carousel/*`, `render/*`,
`reference/*`, `apify/*`, `compute/*`, `storyboard/*`). Esto sugiere que la
oficina Factory V5 declaró la superficie completa de skills que necesita
(130 carpetas) pero solo terminó de redactar ~95 a nivel de contrato real;
el resto son placeholders de una línea que probablemente nunca se
completaron con el frontmatter/contrato que sí exige el resto del catálogo.
**No se puede saber si esto afecta ejecución real** sin ver cómo estos
skills se cargan en factory-v5 (podría ser que ese runtime no dependa del
frontmatter) — se reporta como hallazgo, no se toca (repo de solo lectura).

### Skills con iteración real dentro de la ventana (trabajo activo verificado)

Estos son los que muestran más de un commit — es decir, se escribieron y
luego se corrigieron con base en producción real, no solo se crearon una vez:

| Skill | Commits | Fechas | Motivo (según mensajes de commit) |
|---|---|---|---|
| `skills/quality/score-with-tribe-v2` | 4 | 07-27, 07-29, 07-30 | Iterado hasta "TRIBE v2 real visual frame analysis (v1.1)" |
| `skills/distribution/upload-post-multichannel` | 2 | 08-01, 08-03 | El commit del 08-03 dice explícitamente "capture real carousel incidents in skill, fix stale setup doc" — corrección post-incidente real de producción |
| `skills/distribution/upload-youtube-native` | 2 | 07-31, 08-01 | Consolidación de producción real |
| `skills/video/assemble-long-from-reuse` | 2 | 07-27, 07-28 | "update 3 skills to ground truth" |
| `skills/video/produce-kie-reel` | 2 | 07-27, 07-28 | Idem |
| `skills/video/produce-stock-based-short` | 2 | 07-27, 07-28 | Idem |

`upload-post-multichannel`, `upload-youtube-native`,
`dedup-check-before-publish`, `schedule-campaign-calendar` y
`render-consistent-long-bitrate` son además los skills más recientes
(07-31 → 08-03) y corresponden a la campaña de 10 días que da nombre a la
rama actual (`feat/factory-v5-upload-campaign-10-day`) — son los que más
vale la pena que Cano revise si algo falla en esa campaña, porque son los
que más se tocaron bajo presión real.

### No se ejecutó nada

No corrí tests, scripts `.ps1`, ni nada de `factory-ia-channel-v5` o de la
carpeta `deprecated/`. Cero escritura en el repo (verificado: `git status`
al final sigue mostrando el mismo estado que al inicio, rama
`feat/factory-v5-upload-campaign-10-day` sin cambios).

---

## Resumen de conteos

**StarHome (`cano-hermes-agentic-os`)** — 58 skills en `main` tocados en la
ventana (100%, porque el repo nació hace 6 días):
- Nuevos (creación única): 57
- Iterados (creados y luego retocados): 1 (`container-sandbox`)
- Sanos: 54 (los 58 en `main`, menos los 4 huérfanos; `engineering-loop` no
  cuenta en los 58 de `main` porque no existe ahí — está aparte, como roto)
- A medias: 4 (`factory-v5-contract`, `command-center-contract`,
  `adaptive-content-orchestrator`, `reel-dedup-check` — válidos pero
  huérfanos de agente)
- Rotos: 1 (`engineering-loop` — referenciado por agente, no existe en
  `main`, arreglo correcto ya sentado en PR #6 abierta sin mergear)

**command-center (`cano-ai-command-center`)** — 162 carpetas de skill
tocadas en la ventana:
- Nuevas (primera aparición en git): ~158
- Iteradas (múltiples commits): 6 (`score-with-tribe-v2`,
  `upload-post-multichannel`, `upload-youtube-native`,
  `assemble-long-from-reuse`, `produce-kie-reel`,
  `produce-stock-based-short`)
- Bien formadas (frontmatter completo): ~127 de ~130 en factory-v5, +4 en
  `.agents/skills`, +22 en deprecated (pero esas 22 no son trabajo nuevo real)
- A medias: 35 skills de factory-v5 sin frontmatter (stubs de 2-4 líneas) +
  6 fichas-spec en `.command-center/skills/specs/` que son solo punteros a
  scripts, no skills completos
- Rotas (referencias muertas): ninguna detectada por grep directo, pero no
  se validó contra el runtime real de factory-v5 (solo lectura, no se pudo
  confirmar cómo cada skill se registra en ejecución)

## PRs abiertas en StarHome (no creé ninguna nueva)

No abrí PR nueva. La que hacía falta para `engineering-loop` **ya existe**:

- PR #6 `fix: create missing engineering-loop skill` — rama
  `fix/engineering-loop-skill` — **OPEN, sin mergear**
- PR #5 `feat(finance): create finance team, move budget-controller from
  governance` — rama `feat/finance-office` — **OPEN, sin mergear** (no
  toca skills directamente, pero queda igual de pendiente de cierre)

Recomendación: mergear PR #6 antes de considerar cerrado el ciclo Prometeo —
es la única skill realmente rota que encontré en los 58 vivos de StarHome.
