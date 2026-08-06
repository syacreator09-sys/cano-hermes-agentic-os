# Matriz de Skills — Ecosistema StarHome/Hermes

**Fase:** F6 del plan Prometeo · **Generado:** 2026-08-05 · **Tipo:** inventario, sin cambios de código.

Fuentes leídas directamente (nada inventado):

1. `skills/*/manifest.json` + `SKILL.md` de este repo (StarHome OS) — 54 skills.
2. `agents/*/*.yaml` de este repo — para resolver `skill → agente → oficina(team) → ejecutor`.
3. `~/.hermes/skills/<categoria>/` — 14 categorías del catálogo de hermes-agent.
4. Búsqueda local (`~/.claude/skills`, `~/.codex/`, `factory-ia-channel-v5/renderers/hyperframes`) + catálogo remoto `github.com/heygen-com/hyperframes` (vía `gh api` y fetch de `SKILL.md`) para HyperFrames.
5. `~/.claude/skills/graphify/SKILL.md`.
6. `~/.claude/plans/snuggly-humming-snail.md` (líneas 75-129) para las oficinas Docker planeadas (F11/F14) — no construidas, no se inventó contenido nuevo.

Columnas: `skill | oficina | ejecutor | credenciales | riesgo`.

Nota sobre "ejecutor": los `agents/*/*.yaml` de StarHome declaran `runtime` con 6 valores reales, no solo los 4 esperados (`claude-code`, `codex`, `hermes` → **hermes-agent**, y también `api`, `python`, `browser`). Se preservan tal cual para no falsear la fuente; se explican abajo de la tabla 1.

---

## 1. StarHome nativo (`skills/*`) — 54 skills

**Hallazgo de credenciales (aplica a las 54 filas):** ningún `manifest.json` ni `SKILL.md` de este directorio declara una env var propia — los 54 `SKILL.md` son boilerplate procedimental ("Confirmar objetivo… Ejecutar en modo seguro o sandbox… Registrar evidencia…") sin bloque de configuración. El acceso a credenciales no es un atributo del skill sino del **runtime que lo ejecuta**, aislado por tier en `cano_hermes/runtimes/subprocess_executor.py:26-40` (claude-code→ANTHROPIC, codex→OPENAI, hermes-agent→NVIDIA/KIMI/OPENROUTER, sandbox/openclaw→ninguna). Por eso la columna credenciales dice "No (heredada del tier del ejecutor)" en las 54 filas — es correcto y no un hueco de datos.

Leyenda ejecutor: `claude-code` · `codex` · `hermes-agent` (yaml `runtime: hermes`) · `api` (modelo vía API directa, sin pasar por CLI de hermes) · `python` (script nativo StarHome) · `browser` (automatización vía Playwright/similar).

### Content (9)

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

¹ `factory-v5` invoca Factory V5 **por contrato**; las credenciales reales viven en el `.env` de `factory-ia-channel-v5` (repo externo, no tocado aquí).

### Documents (1)

| skill | oficina | ejecutor | credenciales | riesgo |
|---|---|---|---|---|
| document-consistency-audit | documents | hermes-agent | No (heredada del tier) | medio |

### Engineering (8)

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

## Resumen

**Total de skills/pipelines inventariados: 92**
(54 StarHome nativo + 14 categorías hermes-agent + 19 HyperFrames catálogo remoto + 1 graphify + 4 oficinas Docker F11 + 1 oficina Docker F14)

### Por riesgo

| riesgo | cuenta | dónde |
|---|---|---|
| alto | 5 | StarHome: investment-thesis-review (1) · HyperFrames: media-use, motion-graphics, talking-head-recut (3) · Oficinas Docker: office-publish (1) |
| medio | 24 | StarHome: 9 · hermes-agent (categorías con credencial sensible): autonomous-ai-agents, email, github, productivity, social-media (5) · HyperFrames: hyperframes-router, product-launch-video, pr-to-video, figma (4) · Oficinas Docker: office-ugc, office-market-intel (2) — resto bajo |
| bajo | 63 | el resto |

### Por oficina (solo StarHome nativo, 54 skills — únicas con `team` explícito en `agents/*.yaml`)

content 9 · engineering 8 · governance 7 · forge 6 · research 6 · operations 5 · finance 3 · personal-operations 3 · projects 2 · revenue 2 · documents 1 · investments 1 · learning 1

### Por credenciales requeridas

- **StarHome nativo (54):** 0 declaran env vars propias — 100% heredan del tier del ejecutor.
- **hermes-agent (14 categorías):** 6 de 14 tienen al menos un skill con credencial confirmada por texto (autonomous-ai-agents, email, github, mlops parcial, productivity, social-media) + 2 parciales (creative/comfyui, media/gif-search) = **8 de 14 categorías** tocan credenciales.
- **HyperFrames (19, no instaladas):** 3 con credencial probable no confirmada (media-use, pr-to-video, figma); resto sin evidencia.
- **graphify (1):** 0 obligatorias.
- **Oficinas Docker (5, no construidas):** 0 — aún no hay integración real.

---

## Hallazgos para F15 (bucle de convergencia)

1. **`engineering-lead.yaml` referencia un skill que no existe.** `agents/engineering/engineering-lead.yaml:10` declara `skills: [engineering-loop]`, pero no hay ningún directorio `skills/engineering-loop/` — de los 54 skills reales, este es el único agente cuyo `skills:` apunta a un id inexistente. Hay que crear el skill `engineering-loop` o corregir la referencia (probablemente debería apuntar a una combinación de `architecture-spec`+`code-review`+`testing`, que son los skills de los agentes que coordina).
2. **"25 skills HyperFrames" en el plan maestro no corresponde a la realidad de esta máquina.** No hay instalación local (`~/.claude/skills`, `~/.codex/skills`) ni slash commands. El catálogo remoto actual (`github.com/heygen-com/hyperframes`, carpeta `skills/`) trae 19, no 25 — el número del plan puede venir de una versión anterior del repo o de otra máquina. Antes de tratar HyperFrames como "ya ejecutado" en cualquier fase futura, correr `npx skills add heygen-com/hyperframes` explícitamente y volver a auditar.
3. **Ninguna skill de HyperFrames trae metadata de riesgo en su manifiesto.** El frontmatter de `media-use/SKILL.md` (revisado completo) solo tiene `name` y `description`, sin campo de riesgo. La clasificación ALTO de `media-use`, `motion-graphics`, `talking-head-recut` es 100% juicio humano de Cano (documentado en el plan), no derivable de los archivos — cualquier automatización futura que intente "leer el riesgo del manifiesto" de HyperFrames no encontrará nada y debe seguir tratando estos 3 (+ los que Cano añada) como ALTO por política externa al repo.
4. **Los 54 `SKILL.md` de StarHome son boilerplate idéntico.** Todos (salvo `investment-thesis-review`, que tiene procedimiento propio con verificación) comparten el mismo texto genérico de 5 pasos ("Confirmar objetivo… Recuperar contexto… Ejecutar en modo seguro… Validar… Registrar evidencia"). Es coherente con `progressive_disclosure: true` en el manifiesto (el detalle real vive en otro lado, probablemente en el prompt del agente o en `references/`), pero si F15 espera que estos documentos contengan procedimientos operativos específicos por skill, hoy no los tienen — es deuda de contenido, no de estructura.
5. **`skills/candidates/`** (creado dinámicamente por `SkillFactory` en `cano_hermes/forge/skill_factory.py`) no existía en el momento de este inventario — no hay skills en cuarentena pendientes de promoción ahora mismo.
6. **hermes-agent no tiene concepto de "oficina" StarHome.** Su catálogo de 14 categorías es una biblioteca de capacidades transversal, consumida por cualquier agente `runtime: hermes` de cualquier team. Mapear categorías de hermes-agent 1:1 a oficinas StarHome sería inventar una relación que no existe en el código — se dejó `oficina = N/A` a propósito.
