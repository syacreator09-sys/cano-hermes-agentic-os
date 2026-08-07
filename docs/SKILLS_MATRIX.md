# Matriz de Skills — Ecosistema StarHome/Hermes

**Fase:** F6 del plan Prometeo · **Generado:** 2026-08-05 · **Tipo:** inventario, sin cambios de código.

Fuentes leídas directamente (nada inventado):

1. `skills/*/manifest.json` + `SKILL.md` de este repo (StarHome OS) — 59 skills (era 54 en F6; ver nota K15 en `## Resumen`).
2. `agents/*/*.yaml` de este repo — para resolver `skill → agente → oficina(team) → ejecutor`.
3. `~/.hermes/skills/<categoria>/` — 14 categorías del catálogo de hermes-agent.
4. Búsqueda local (`~/.claude/skills`, `~/.codex/`, `factory-ia-channel-v5/renderers/hyperframes`) + catálogo remoto `github.com/heygen-com/hyperframes` (vía `gh api` y fetch de `SKILL.md`) para HyperFrames.
5. `~/.claude/skills/graphify/SKILL.md`.
6. `~/.claude/plans/snuggly-humming-snail.md` (líneas 75-129) para las oficinas Docker planeadas (F11/F14) — no construidas, no se inventó contenido nuevo.
7. **F7 (2026-08-05, añadido después de la generación original de este documento):** `gh search repos --owner tecnomanu` + `gh api` (licencia/contenido de repos), lectura de `~/repos/cano-tutorial-suite`, `~/repos/cano-screen-tutorial-skill`, `~/repos/cano-video-vox` (repos propios), lectura de `CLAUDE-CODE-LAUNCHERS/fba-hunter/` en command-center (solo lectura), y un dry-run real de `video-docs-builder` (`rehearse.ts` contra una app local de una sola página, sin gasto, sin tocar command-center).

Columnas: `skill | oficina | ejecutor | credenciales | riesgo`.

Nota sobre "ejecutor": los `agents/*/*.yaml` de StarHome declaran `runtime` con 6 valores reales, no solo los 4 esperados (`claude-code`, `codex`, `hermes` → **hermes-agent**, y también `api`, `python`, `browser`). Se preservan tal cual para no falsear la fuente; se explican abajo de la tabla 1.

---

## 1. StarHome nativo (`skills/*`) — 59 skills

**Hallazgo de credenciales (aplica a las 59 filas):** ningún `manifest.json` ni `SKILL.md` de este directorio declara una env var propia — los 59 `SKILL.md` son boilerplate procedimental ("Confirmar objetivo… Ejecutar en modo seguro o sandbox… Registrar evidencia…") sin bloque de configuración. El acceso a credenciales no es un atributo del skill sino del **runtime que lo ejecuta**, aislado por tier en `cano_hermes/runtimes/subprocess_executor.py:26-40` (claude-code→ANTHROPIC, codex→OPENAI, hermes-agent→NVIDIA/KIMI/OPENROUTER, sandbox/openclaw→ninguna). Por eso la columna credenciales dice "No (heredada del tier del ejecutor)" en las 59 filas — es correcto y no un hueco de datos.

Leyenda ejecutor: `claude-code` · `codex` · `hermes-agent` (yaml `runtime: hermes`) · `api` (modelo vía API directa, sin pasar por CLI de hermes) · `python` (script nativo StarHome) · `browser` (automatización vía Playwright/similar).

### Content (13)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| metrics-learning | content | api | No (heredada del tier) | bajo |
| content-opportunity-brief | content | hermes-agent | No (heredada del tier) | medio |
| content-pipeline | content | hermes-agent | No (heredada del tier) | bajo |
| creative-brief | content | claude-code | No (heredada del tier) | bajo |
| editorial-scoring | content | hermes-agent | No (heredada del tier) | bajo |
| factory-v5 | content | hermes-agent | No (heredada del tier)¹ | bajo |
| scriptwriting | content | api | No (heredada del tier) | bajo |
| storyboard | content | api | No (heredada del tier) | bajo |
| trend-radar | content | api | No (heredada del tier) | bajo |
| adaptive-content-orchestrator² | content | hermes-agent | No (heredada del tier) | bajo (declarado `"risk": "low"` en su manifest) |
| factory-v5-contract² | content | hermes-agent | No (heredada del tier)¹ | bajo (declarado `"risk": "low"`; solo-lectura de `factory-ia-channel-v5`, dry-run salvo aprobación explícita) |
| command-center-contract² | content | api | No (heredada del tier) | bajo (declarado `"risk": "low"`; solo-lectura de `cano-ai-command-center`) |
| reel-dedup-check² | content | hermes-agent | No (heredada del tier) | bajo (declarado `"risk": "low"`; es el check de dedup en sí, no publica) |

¹ `factory-v5`/`factory-v5-contract` invocan Factory V5 **por contrato**; las credenciales reales viven en el `.env` de `factory-ia-channel-v5` (repo externo, no tocado aquí).
² **Añadido en K15** — existía en `skills/` desde F8/F9 (auditoría de 30 días los marcó "a medias/huérfanos") y K9 ya los había cableado a un agente (`agents/content/factory-operator.yaml`, `agents/content/analytics-learner.yaml`, `agents/content/distributor.yaml`), pero nunca se añadieron como fila propia a esta tabla — K15 lo corrige. `scripts/validate.py` (extendido en K15) confirma que los 4 ya no son huérfanos: cada uno aparece en el `skills:` de al menos un agente.

### Documents (1)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| document-consistency-audit | documents | hermes-agent | No (heredada del tier) | medio |

### Engineering (9)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| architecture-spec | engineering | claude-code | No (heredada del tier) | bajo |
| repo-analysis | engineering | claude-code | No (heredada del tier) | bajo |
| code-review | engineering | claude-code | No (heredada del tier) | bajo |
| tdd-build | engineering | codex | No (heredada del tier) | bajo |
| git-worktrees | engineering | codex | No (heredada del tier) | bajo |
| graphify-map | engineering | python | No (heredada del tier) | bajo |
| testing | engineering | python | No (heredada del tier) | bajo |
| ui-review | engineering | browser | No (heredada del tier) | bajo |
| engineering-loop³ | engineering | hermes-agent | No (heredada del tier) | bajo (declarado `"risk": "low"`) |

³ **Añadido en K0** (fase previa a este plan) para reparar `agents/engineering/engineering-lead.yaml` (referenciaba un skill inexistente en `main`, hallazgo de la auditoría de 30 días) — mismo patrón de coordinación que los otros "-lead" (`forge-governance`, `content-pipeline`, `research-plan`). Nunca se había añadido como fila a esta tabla hasta K15.

### Finance (3)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| expense-capture | finance | hermes-agent | No (heredada del tier) | medio |
| cash-position | finance | hermes-agent | No (heredada del tier) | medio |
| finance-close | finance | hermes-agent | No (heredada del tier) | medio |

### Forge (6) — PROMETEO

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| agent-blueprint | forge | claude-code | No (heredada del tier) | bajo |
| capability-audit | forge | hermes-agent | No (heredada del tier) | bajo |
| container-sandbox | forge | codex | No (heredada del tier) | bajo |
| forge-governance | forge | hermes-agent | No (heredada del tier) | bajo |
| mcp-build | forge | codex | No (heredada del tier) | bajo |
| skill-authoring | forge | codex | No (heredada del tier) | bajo |

### Governance (7)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| budget-routing | governance | hermes-agent | No (heredada del tier) | bajo |
| task-planning | governance | hermes-agent | No (heredada del tier) | bajo |
| capability-routing | governance | hermes-agent | No (heredada del tier) | bajo |
| nexus-context | governance | hermes-agent | No (heredada del tier) | bajo |
| evaluation-gates | governance | hermes-agent | No (heredada del tier) | bajo |
| security-review | governance | hermes-agent | No (heredada del tier) | bajo |
| task-governance | governance | hermes-agent | No (heredada del tier) | bajo |

### Investments (1)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| investment-thesis-review | investments | hermes-agent | No (heredada del tier) | **alto** |

### Learning (1)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| learning-session | learning | hermes-agent | No (heredada del tier) | bajo |

### Operations (5)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| integration-build | operations | codex | No (heredada del tier) | bajo |
| browser-automation | operations | browser | No (heredada del tier) | bajo |
| communications | operations | hermes-agent | No (heredada del tier) | bajo |
| infra-ops | operations | hermes-agent | No (heredada del tier) | bajo |
| voice-flow | operations | hermes-agent | No (heredada del tier) | bajo |

### Personal-operations (3)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| daily-brief | personal-operations | hermes-agent | No (heredada del tier) | bajo |
| capture-anything | personal-operations | hermes-agent | No (heredada del tier) | medio |
| weekly-review | personal-operations | hermes-agent | No (heredada del tier) | bajo |

### Projects (2)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| project-status | projects | hermes-agent | No (heredada del tier) | bajo |
| blocker-review | projects | hermes-agent | No (heredada del tier) | medio |

### Research (6)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| batch-analysis | research | api | No (heredada del tier) | bajo |
| source-verification | research | hermes-agent | No (heredada del tier) | bajo |
| trend-analysis | research | api | No (heredada del tier) | bajo |
| deep-research | research | api | No (heredada del tier) | bajo |
| structured-processing | research | api | No (heredada del tier) | bajo |
| research-plan | research | hermes-agent | No (heredada del tier) | bajo |

### Revenue (2)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| lead-next-action | revenue | hermes-agent | No (heredada del tier) | medio |
| pipeline-review | revenue | hermes-agent | No (heredada del tier) | medio |

---

## 2. hermes-agent (`~/.hermes/skills/`) — 14 categorías

Formato adaptado para esta sección (a pedido de la tarea: listar contenido de cada categoría, no detalle por skill individual). `ejecutor` = `hermes-agent` en las 14 filas (todo corre vía `hermes` CLI / `hermes --oneshot`). `oficina` = N/A — es una biblioteca transversal de hermes-agent, no pertenece a un team StarHome específico; cualquier agente `runtime: hermes` puede invocarla.

| categoría | contiene | credenciales detectadas (env vars, sin valores) | riesgo |
|---|---|---|---|
| apple | apple-notes, apple-reminders, findmy, imessage | No (requiere macOS local + permisos del SO, no env var) | bajo |
| autonomous-ai-agents | claude-code, codex, computer-use, hermes-agent, opencode | Sí: `ANTHROPIC_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN` (claude-code), `OPENAI_API_KEY`/`COPILOT_GITHUB_TOKEN` (codex) | medio |
| creative | architecture-diagram, ascii-art, ascii-video, baoyu-infographic, claude-design, comfyui, design-md, excalidraw, humanizer, manim-video, p5js, popular-web-designs, pretext, sketch, songwriting-and-ai-music, touchdesigner-mcp | Sí (parcial): `COMFY_CLOUD_API_KEY` (comfyui); resto sin credencial declarada | bajo |
| email | himalaya | Sí: credenciales de cuenta de correo (config de `himalaya`, no capturado como env var estándar) | medio |
| github | codebase-inspection, github-auth, github-code-review, github-issues, github-pr-workflow, github-repo-management | Sí: `GITHUB_TOKEN` / `GITHUB_PERSONAL_ACCESS_TOKEN` / `GITHUB_WEBHOOK_SECRET` | medio |
| graphify | (skill único, ver sección 4) | No (opcional `GEMINI_API_KEY`/`GOOGLE_API_KEY`, nunca bloqueante) | bajo |
| media | gif-search, songsee, youtube-content | Sí (parcial): `TENOR_API_KEY` (gif-search) | bajo |
| mlops | evaluation, huggingface-hub, inference, models | Sí: `WANDB_API_KEY`, HF token vía `huggingface-hub` (`hf_whoami`/hub tools) | bajo |
| note-taking | obsidian | No (vault local en filesystem) | bajo |
| productivity | airtable, docx, google-workspace, maps, nano-pdf, notion, ocr-and-documents, pdf, powerpoint, teams-meeting-pipeline, xlsx | Sí: `AIRTABLE_API_KEY`, `NOTION_API_KEY`/`NOTION_API_TOKEN`, `GOOGLE_WORKSPACE_CLI_TOKEN`, `MSGRAPH_CLIENT_ID`/`MSGRAPH_CLIENT_SECRET` (teams-meeting-pipeline) | medio |
| research | arxiv, blogwatcher, grounded-citations, llm-wiki, polymarket, research-paper-writing | No declarado de forma explícita en `SKILL.md` (polymarket puede requerir clave de API de mercado, no confirmado en texto) | bajo |
| smart-home | openhue | Sí: credencial local de Hue Bridge (no es env var estándar; pairing local) | bajo |
| social-media | xurl | Sí: credenciales OAuth de X/Twitter (vía `xurl` config, no env var suelta) | medio |
| software-development | dogfood, hermes-agent-skill-authoring, inspecting-hermes-desktop-dom, node-inspect-debugger, plan, python-debugpy, requesting-code-review, simplify-code, spike, systematic-debugging, test-driven-development | No declarado | bajo |

---

## 3. HyperFrames — HALLAZGO: no instaladas localmente en esta máquina

El plan maestro (`snuggly-humming-snail.md:108`) registra en "YA EJECUTADO": *"25 skills HyperFrames"*. Se buscó activamente y **no se encontró instalación local**:

- `~/.claude/skills/` → solo contiene `graphify/`. Ningún directorio `hyperframes*`.
- `~/.codex/skills/` → solo contiene `graphify`.
- No existen slash commands `/hyperframes`, `/hyperframes-cli`, `/hyperframes-media` en ningún settings/config local.
- `~/repos/factory-ia-channel-v5/renderers/hyperframes/` **no es** el catálogo de skills: es un proyecto npm de plantilla (`package.json` con dependencia `"hyperframes": "^0.7.61"` + `gsap`), usado para renderizar una secuencia de intro/motion, sin relación con `npx skills add heygen-com/hyperframes`.
- Lo único activo es el **conector MCP "HyperFrames by HeyGen"** (evidencia: logs en `~/.cache/claude-cli-nodejs/.../mcp-logs-claude-ai-HyperFrames-by-HeyGen/`), que expone `compose`/`render_video`/`list_projects`/etc. — pero sus propias instrucciones dicen que `compose` y `render_video` están **deshabilitados** desde un cliente CLI/IDE local (como Claude Code) hasta instalar las skills vía `npx skills add heygen-com/hyperframes`, cosa que no se ha hecho.

Para no dejar la fila vacía se consultó el catálogo remoto real (`github.com/heygen-com/hyperframes`, vía `gh api` sobre el árbol del repo): el directorio `skills/` del repo tiene **19 skills**, no 25 — otra discrepancia con el plan. Ninguno de los `SKILL.md` remotos revisados (se abrió `media-use/SKILL.md` completo) trae metadata de riesgo en el frontmatter; el nivel "ALTO" de `media-use`, `motion-graphics`, `talking-head-recut` es un juicio de Cano en el plan maestro, no un campo del manifiesto. No se encontraron skills adicionales con bandera de riesgo explícita — no se inventaron más "ALTO" además de los 3 ya conocidos.

| skill (catálogo remoto, no instalado) | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| media-use | **PENDIENTE_REVISION_CANO** | N/A (no instalado) | Probable: claves de generación TTS/imagen si el catálogo local no resuelve el asset | **alto** |
| motion-graphics | **PENDIENTE_REVISION_CANO** | N/A (no instalado) | No confirmado | **alto** |
| talking-head-recut | **PENDIENTE_REVISION_CANO** | N/A (no instalado) | No confirmado | **alto** |
| hyperframes (router) | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | medio |
| hyperframes-core | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| hyperframes-animation | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| hyperframes-keyframes | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| hyperframes-creative | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| hyperframes-cli | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| hyperframes-registry | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| remotion-to-hyperframes | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| product-launch-video | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | medio |
| faceless-explainer | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| pr-to-video | PENDIENTE_REVISION_CANO | N/A (no instalado) | Probable: `GITHUB_TOKEN`/`gh` CLI autenticado | medio |
| embedded-captions | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| music-to-video | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| slideshow | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| general-video | PENDIENTE_REVISION_CANO | N/A (no instalado) | No confirmado | bajo |
| figma | PENDIENTE_REVISION_CANO | N/A (no instalado) | Probable: token de acceso a Figma | medio |

El **conector MCP "HyperFrames by HeyGen"** en sí (distinto de las skills locales) se autentica vía el login HeyGen de Claude.ai, no vía env var local — no se imprimió ni se necesitó ningún valor de credencial para esta observación.

---

## 4. graphify

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| graphify | N/A — capacidad transversal (`/graphify`, gobernada por `CLAUDE.md` global del usuario) | claude-code, codex, hermes-agent (instalado en los 3: `~/.claude/skills/graphify`, `~/.codex/skills/graphify`, `~/.hermes/skills/graphify`) | No — `GEMINI_API_KEY`/`GOOGLE_API_KEY` son opcionales para extracción semántica; sin ellas usa el host LLM. El propio `SKILL.md` prohíbe explícitamente pedir `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` | bajo |

---

## 5. Oficinas Docker (PLANEADO — todavía no construidas)

Contenido tomado literalmente de la tabla en `~/.claude/plans/snuggly-humming-snail.md:82-88`. No se inventó pipeline nuevo; solo se transcribe lo planeado. Nota: el plan dice "empezar con 4, NO 12" pero su propia tabla trae **5** filas — la 5ª (`office-market-intel`) corresponde a la fase separada **F14**, no a F11; se lista aparte para no mezclar fases.

### F11 — 4 oficinas núcleo

| skill (=pipeline) | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| scraper→scout→orchestrator→daily-producer→performance-tracker→sales-dashboard | office-ugc — PLANEADO (F11) | sandbox (Docker, supervisor-ugc) | No aplica aún (no construido) | medio (prioridad 1, pipeline más completo, aún sin dispatch real) |
| producción factory-v5: reels, carruseles, largos, imagegen bridge | office-content — PLANEADO (F11) | sandbox (Docker, supervisor-content) | No aplica aún (no construido) | bajo |
| dedup→release guard→draft→dry-run→gate humano→dispatch→ledger | office-publish — PLANEADO (F11) | sandbox (Docker, supervisor-publish) | No aplica aún (no construido) | **alto** (única con dispatch/publicación real al final; "nunca autónomo al final" según el plan) |
| costos, métricas, auditoría calidad, salud | office-analytics — PLANEADO (F11) | sandbox (Docker, supervisor-analytics) | No aplica aún (no construido) | bajo (read-only, "el más seguro" según el plan) |

### F14 — 5ª oficina (fase separada)

| skill (=pipeline) | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| investment-intelligence (Risk Guardian con veto) + fba-hunter (research Amazon) + señales de producto (scout UGC, trend-scout/THENEWSAPI, Apify) — solo análisis, jamás ejecuta trades ni compras | office-market-intel — PLANEADO (F14) | sandbox (Docker, supervisor-market-intel) | No aplica aún (no construido) | medio (análisis puro, "segunda más segura" según el plan, pero toca datos financieros) |

---

## 6. Herramientas externas — F7 (video, grabación, research, generación de docs)

Añadido en F7 del plan Prometeo (2026-08-05). Detalle completo de la
evaluación tecnomanu en `docs/TECNOMANU_REPOS_REVIEW.md`; detalle del
launcher fba-hunter en `docs/FBA_HUNTER_LAUNCHER_NOTES.md`; detalle santmun
(solo contexto, no repos nuevos) en `docs/SANTMUN_REFERENCE_MAP.md`.

### Video / documentación (standalone, no oficina StarHome todavía)

| skill/herramienta | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| `video-docs-builder` (tecnomanu, MIT, clonado en `~/repos/video-docs-builder`) | N/A — herramienta externa standalone; usada hoy también dentro de Factory V5 vía command-center (`tools/external/video-docs-builder/`, solo lectura) | node/npx (Playwright + FFmpeg + Piper, fuera de los runtimes StarHome) | No obligatoria — Piper TTS local es gratis; ElevenLabs/OpenAI TTS son opcionales y de pago | bajo — graba `localhost`/apps propias; dry-run `rehearse.ts` verificado en F7 contra una app de una sola página servida localmente, 2/2 pasos OK, sin gasto |
| `agent-rules-kit` (tecnomanu, ISC, clonado en `~/repos/agent-rules-kit`) | forge (generación de reglas/documentación para agentes IA — Cursor, Claude, VS Code, etc.) | node CLI (`npx agent-rules-kit`) | No — escribe archivos locales; integraciones MCP (ej. `pampa`) son opcionales | bajo |
| `cano-tutorial-suite` (`~/repos/cano-tutorial-suite`, MIT, propio) | content — orquesta screen-tutorial + HeyGen presenter + VideoVox + hybrid composer para el pipeline editorial CANO Digital | node CLI (`bin/cano-tutorial.js`) | No obligatoria en modo mock; HeyGen API solo si se activa el presentador live | bajo — modo mock sin llaves; rama `feature/clone-ready-v0.2` tiene ~20 commits sin fusionar a `main`, pero el diff neto actual es que **`main` ya tiene más contenido** que esa rama (la rama elimina `docs/CONTENT-FORMATS.md` y `docs/VIDEO-ANALYSIS-WATCH.md` respecto a `main`) — no se fusionó nada, solo se inventarió por instrucción explícita |
| `cano-screen-tutorial-skill` (`~/repos/cano-screen-tutorial-skill`, propio) | content — graba tutoriales de navegador reproducibles con Playwright (video WebM, screenshots, trazas) | node CLI (`bin/cano-screen.js`) | No obligatoria en modo mock; sesiones live requieren autorización explícita de dominio | bajo |
| `cano-video-vox` (`~/repos/cano-video-vox`, propio) | content — shorts verticales animados estilo documental con Remotion | node + Python aislado (recorte de fondos) + Remotion | Sí, para el flujo completo: Kie.ai (imágenes) + ElevenLabs (voz) vía Llavero de macOS, no `.env` | medio — usa proveedores de pago para su flujo principal (no tiene camino 100% gratis documentado); el propio README dice que el repo debe permanecer privado hasta cerrar revisión de licencia/procedencia — **no confundir con el `video-vox` de santmun** (repo de terceros, licencia UNKNOWN, solo referencia visual — ver `docs/SANTMUN_REFERENCE_MAP.md`); este es un repo propio distinto |

### Research / market-intel (relacionado con F14 `office-market-intel`)

| skill/herramienta | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| `fba-hunter` launcher (command-center, `CLAUDE-CODE-LAUNCHERS/fba-hunter/`, solo lectura) | market-intel (relacionado a F14, no construido aún) | python (scripts propios de un proyecto completo aparte) | Ninguna declarada en el launcher en sí (solo texto/knowledge base); el proyecto completo real trae su propio `.env.example` | bajo — research-only, nunca ejecuta compras; ver `docs/FBA_HUNTER_LAUNCHER_NOTES.md` para la distinción launcher-vs-repo-completo |
| `amazon-fba-product-hunter` (`~/repos/amazon-fba-product-hunter`, propio — el proyecto completo referenciado por el launcher de arriba, no el launcher en sí) | office-ugc / office-analytics — research de productos FBA Wholesale (relacionado a F14 `office-market-intel`) | python (venv propio) + Playwright (Chromium) + Postgres 16/Redis en docker-compose local | `.env` propio (gitignored): `CONTARMARKET_EMAIL/PASSWORD`, `FLYBY_API_KEY`, `KEEPA_API_KEY`, `AMAZON_SP_API_*`, `ANTHROPIC_API_KEY` — ninguna resuelta desde el vault compartido (`~/.secrets/credenciales/credenciales/.env`) por ahora, todas siguen `PENDIENTE_DECISION`; Postgres/Redis/pgAdmin con contraseñas locales propias en `.env` (no vault) | bajo — pipeline de scoring puro (APROBADO / CON CAUTELA / DESCARTADO), scraping respetuoso (rate-limited), dry-run por defecto, cero compras reales, cero credenciales de broker/marketplace manejadas por el LLM; 156/156 tests pasando (2026-08-06) |

**No clonado en F7** (evaluado y rechazado): `framevox` y `agent-rules-kit-mcp`
(ambos de tecnomanu, sin archivo `LICENSE` en la raíz). `qwen3-tts-api`
(tecnomanu) fue evaluado pero descartado por categoría (TTS/audio, no
video/grabación/documentación) — ver `docs/TECNOMANU_REPOS_REVIEW.md` para
el detalle completo de los 40 repos revisados.

---

## Resumen

**Total de skills/pipelines inventariados: 103** (actualizado en K15; era 98 en F6/F7)
(59 StarHome nativo + 14 categorías hermes-agent + 19 HyperFrames catálogo remoto + 1 graphify + 4 oficinas Docker F11 + 1 oficina Docker F14 + 6 herramientas externas F7: video-docs-builder, agent-rules-kit, cano-tutorial-suite, cano-screen-tutorial-skill, cano-video-vox, fba-hunter launcher)

**K15 — de dónde salen los 5 StarHome nativo nuevos (54→59):** `adaptive-content-orchestrator`,
`factory-v5-contract`, `command-center-contract`, `reel-dedup-check` (creados F8/F9, cableados a
un agente por K9, pero nunca añadidos como fila a esta tabla hasta ahora) + `engineering-loop`
(creado K0 para reparar la referencia rota que la auditoría de 30 días encontró en
`agents/engineering/engineering-lead.yaml`). Ninguno es contenido nuevo de K15 — K15 solo
corrigió que esta matriz no los reflejaba. `scripts/validate.py`, extendido en K15 con un
chequeo de huérfanos/referencias colgantes, confirma **cero huérfanos** sobre los 59 actuales
(ver `## Hallazgos para K15` abajo).

### Por riesgo

| riesgo | cuenta | dónde |
|---|---|---|
| alto | 5 | StarHome: investment-thesis-review (1) · HyperFrames: media-use, motion-graphics, talking-head-recut (3) · Oficinas Docker: office-publish (1) |
| medio | 25 | StarHome: 9 · hermes-agent (categorías con credencial sensible): autonomous-ai-agents, email, github, productivity, social-media (5) · HyperFrames: hyperframes-router, product-launch-video, pr-to-video, figma (4) · Oficinas Docker: office-ugc, office-market-intel (2) · F7: cano-video-vox (1, proveedores de pago sin camino gratis documentado) — resto bajo |
| bajo | 73 | el resto (68 previo + 5 filas StarHome nuevas de K15, todas declaradas `"risk": "low"` en su manifest) |

### Por oficina (solo StarHome nativo, 59 skills — únicas con `team` explícito en `agents/*.yaml`)

content 13 · engineering 9 · governance 7 · forge 6 · research 6 · operations 5 · finance 3 · personal-operations 3 · projects 2 · revenue 2 · documents 1 · investments 1 · learning 1

### Por credenciales requeridas

- **StarHome nativo (59):** 0 declaran env vars propias — 100% heredan del tier del ejecutor.
- **hermes-agent (14 categorías):** 6 de 14 tienen al menos un skill con credencial confirmada por texto (autonomous-ai-agents, email, github, mlops parcial, productivity, social-media) + 2 parciales (creative/comfyui, media/gif-search) = **8 de 14 categorías** tocan credenciales.
- **HyperFrames (19, no instaladas):** 3 con credencial probable no confirmada (media-use, pr-to-video, figma); resto sin evidencia.
- **graphify (1):** 0 obligatorias.
- **Oficinas Docker (5, no construidas):** 0 — aún no hay integración real.
- **Herramientas externas F7 (6):** 1 de 6 toca credenciales de pago para su flujo principal (`cano-video-vox` → Kie.ai + ElevenLabs); las otras 5 tienen camino 100% gratis (modo mock o TTS local).

---

## Hallazgos para F15 (bucle de convergencia)

1. **RESUELTO en F15 iteración 1.** `agents/engineering/engineering-lead.yaml:10` declaraba `skills: [engineering-loop]` sin que existiera `skills/engineering-loop/`. Se creó el skill (`skills/engineering-loop/manifest.json` + `SKILL.md`, mismo formato boilerplate que el resto) en vez de redirigir la referencia: los otros tres agentes "-lead" del repo (`forge-lead` → `forge-governance`, `content-lead` → `content-pipeline`, `research-lead` → `research-plan`) siguen todos el mismo patrón — un skill de coordinación propio y exclusivo por lead, distinto de los skills de los agentes que coordinan. Apuntar `engineering-lead` a `architecture-spec`+`code-review`+`testing` habría roto ese patrón (además de que `skills:` en el schema de agente es una lista de ids, no admite composición). El `SKILL.md` nuevo documenta el procedimiento de delegación real: `claude-architect` → `codex-builder` → `test-engineer` → `code-reviewer`/`ui-reviewer`.
2. **"25 skills HyperFrames" en el plan maestro no corresponde a la realidad de esta máquina.** No hay instalación local (`~/.claude/skills`, `~/.codex/skills`) ni slash commands. El catálogo remoto actual (`github.com/heygen-com/hyperframes`, carpeta `skills/`) trae 19, no 25 — el número del plan puede venir de una versión anterior del repo o de otra máquina. Antes de tratar HyperFrames como "ya ejecutado" en cualquier fase futura, correr `npx skills add heygen-com/hyperframes` explícitamente y volver a auditar.
3. **Ninguna skill de HyperFrames trae metadata de riesgo en su manifiesto.** El frontmatter de `media-use/SKILL.md` (revisado completo) solo tiene `name` y `description`, sin campo de riesgo. La clasificación ALTO de `media-use`, `motion-graphics`, `talking-head-recut` es 100% juicio humano de Cano (documentado en el plan), no derivable de los archivos — cualquier automatización futura que intente "leer el riesgo del manifiesto" de HyperFrames no encontrará nada y debe seguir tratando estos 3 (+ los que Cano añada) como ALTO por política externa al repo.
4. **Los 54 `SKILL.md` de StarHome son boilerplate idéntico.** Todos (salvo `investment-thesis-review`, que tiene procedimiento propio con verificación) comparten el mismo texto genérico de 5 pasos ("Confirmar objetivo… Recuperar contexto… Ejecutar en modo seguro… Validar… Registrar evidencia"). Es coherente con `progressive_disclosure: true` en el manifiesto (el detalle real vive en otro lado, probablemente en el prompt del agente o en `references/`), pero si F15 espera que estos documentos contengan procedimientos operativos específicos por skill, hoy no los tienen — es deuda de contenido, no de estructura.
5. **`skills/candidates/`** (creado dinámicamente por `SkillFactory` en `cano_hermes/forge/skill_factory.py`) no existía en el momento de este inventario — no hay skills en cuarentena pendientes de promoción ahora mismo.
6. **hermes-agent no tiene concepto de "oficina" StarHome.** Su catálogo de 14 categorías es una biblioteca de capacidades transversal, consumida por cualquier agente `runtime: hermes` de cualquier team. Mapear categorías de hermes-agent 1:1 a oficinas StarHome sería inventar una relación que no existe en el código — se dejó `oficina = N/A` a propósito.
7. **Contradicción sin resolver en command-center sobre `thumbnail-simple-skill` (santmun).** `reuse-map-santmun.md` lo da por extraído en `thumbnail_engine`, pero `SANTMUN_QUARANTINE_AUDIT_20260727.md` lo lista bajo "Bloqueadas por licencia desconocida". No se pudo resolver desde este repo (command-center es solo lectura) — ver `docs/SANTMUN_REFERENCE_MAP.md`. Si F15 toca Factory V5, marcar como pendiente de aclarar con quien mantiene ese repo, no asumir ninguna de las dos versiones.
8. **El mecanismo MCP portable de esta máquina existe pero está vacío.** `hermes_cli/mcp_config.py` (hermes-agent) declara que los MCP servers viven en `~/.hermes/config.yaml` bajo la clave `mcp_servers`, interpolando secretos desde un `~/.hermes/.env` opcional. En esta máquina, `~/.hermes/config.yaml` tiene `mcp_servers: {}` (vacío) y `~/.hermes/.env` **no existe**. Ninguno de los 4 MCP portables (`n8n-mcp`, `notion`, `rapidapi-tiktok`, `factory-ia-channel`) está registrado todavía. No se creó el archivo a ciegas — ver `docs/MCP_PORTABLE_CONNECTORS.md` para el hallazgo completo y qué falta antes de activarlos.
   **Actualización K15: ya no vacío.** `n8n-mcp` y `notion-mcp` fueron activados poco después de este hallazgo (ver `docs/MCP_PORTABLE_CONNECTORS.md`, sección "2026-08-06 — n8n-mcp y notion-mcp ACTIVADOS") y siguen `✓ enabled` (`hermes mcp list`) tras todos los restarts del gateway de K0/K10/K13/K14 — verificado en vivo hoy: `~/.hermes/logs/agent.log` muestra el último restart (18:34:22) registrando `MCP: registered 51 tool(s) from 2 server(s)` (24 de `notion-mcp`, 27 de `n8n-mcp`). `rapidapi-tiktok` sigue bloqueado — `RAPIDAPI_KEY` sigue ausente de `~/.secrets/credenciales/credenciales/.env`, confirmado por quinta vez (F1, F2, F7, F15, K15). Ver `docs/OPERATIONS.md` para el patrón `PENDING_NATIVE_TOOL` documentado en K15 para los MCP de Claude.ai (Shopify/Meta/Gamma/Adobe/Canva/Vercel/Upload-post), que son un caso aparte: no viven en `~/.hermes/config.yaml`, solo son invocables desde una sesión Claude.

## Hallazgos para K15 (mejora continua de memoria, skills, MCP)

9. **RESUELTO — cero skills huérfanos.** `scripts/validate.py` ganó un chequeo real de huérfanos (skill sin ningún agente que lo referencie en `skills:`) y de referencias colgantes (agente que referencia un skill inexistente), corrido sobre el estado actual (59 skills StarHome / 54 agentes). Resultado: **0 huérfanos, 0 referencias colgantes** — los 4 huérfanos de la auditoría de 30 días (`adaptive-content-orchestrator`, `factory-v5-contract`, `command-center-contract`, `reel-dedup-check`) ya habían sido cableados por K9; esta fase solo lo verificó con código, no con grep manual, y dejó el chequeo permanente (`tests/test_k15_validate_orphans.py`, 5 tests). El chequeo excluye a propósito `skills/candidates/*` (cuarentena de `SkillFactory`, no cableada por diseño hasta que un humano la promueve).
10. **Los 5 skills que ya existían en `skills/` pero nunca habían sido añadidos como fila propia a esta matriz** (`adaptive-content-orchestrator`, `factory-v5-contract`, `command-center-contract`, `reel-dedup-check`, `engineering-loop`) quedaron añadidos en las secciones §Content y §Engineering arriba, con oficina/ejecutor/riesgo resueltos desde su `manifest.json` real y el agente que los referencia — ver la nota "K15 — de dónde salen los 5" en `## Resumen`.
11. **Deuda de contenido de los 59 `SKILL.md` boilerplate — decisión: no se reescriben en esta fase.** El hallazgo #4 de F15 (boilerplate idéntico de 5 pasos, `progressive_disclosure: true`) sigue siendo cierto para los 59 actuales. K15 decide **no** invertir en reescribir contenido específico por skill: no hay evidencia de que algo lo consuma mal (nada roto, cero huérfanos, `validate.py` pasa), y el detalle real ya vive donde el propio manifiesto dice que vive (prompt del agente / `references/`). Reescribir 59 procedimientos a mano sin un caso de uso real que lo exija sería "polish de bajo valor" (instrucción explícita de esta fase) a costa de tiempo mejor gastado en lo roto/huérfano — que hoy es cero. Se deja como deuda documentada, no como pendiente activo.
