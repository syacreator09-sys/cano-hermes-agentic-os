# Auditoría end-to-end — Plan Prometeo F0-F16 (cierre)

Servidor de agentes de Cano. F16, fase de cierre del plan Prometeo. Consolida
en un solo documento el resultado de la matriz de conexiones, las suites de
test de los 7 repos/paquetes relevantes, el estado de arquitectura construido
F0-F15, la convergencia del bucle F15, los pendientes de Cano, y el checklist
de auditoría de seguridad de F16 (git, permisos, grep de llaves, aislamiento
de credenciales, sandbox/Docker, y el recordatorio de `orion-config`).

Generado 2026-08-06. No se reinventan números: donde F15 ya los verificó, se
cita el reporte fuente en vez de recalcular.

---

## 1. Matriz de conexiones

Última corrida confirmada en F15-iteración-1 (2026-08-06):
`scripts/connection_matrix.py` → `reports/connection-matrix-2026-08-06.md` /
`.json`.

**Totales: ✓306 / ✗537 / —57.**

No se regeneró en F16 — no hay indicio de que algo haya cambiado desde F15-it1
(mismas horas de la misma sesión, sin nuevas credenciales dadas de alta). Los
✗ son proveedores no usados por diseño más los pendientes de la tabla §5.

## 2. Suites — tabla final

La lista real de suites relevantes terminó siendo más larga que las "5
suites" del plan maestro original; aquí están las 7 confirmadas en
F15-iteración-1 (`reports/f15-iteracion-1-2026-08-06.md`, sin re-ejecutar en
F16 salvo `test_credential_isolation.py`, ver §5.4):

| Suite | Comando | Resultado | Target | Estado |
|---|---|---|---|---|
| StarHome (`cano-hermes-agentic-os`, unittest) | `python -m unittest discover -s tests` | 70 OK | — | ✅ |
| StarHome (`cano-hermes-agentic-os`, pytest) | `pytest` | 75 passed | — | ✅ |
| `factory-ia-channel-v5` | `pytest -q` | 196 passed, 7 failed (203 total) | ≥196/203 | ✅ exacto en baseline (bloqueado por pendiente `stage-handlers.yaml`) |
| command-center `agents-platform` (solo lectura, validación externa) | venv externo, ver nota metodológica en F15-it1 | 57 passed, 4 failed, 1 skipped (62 total) | 61 | ⚠️ 3 fallos por credencial Cloudflare ausente, 1 posible bug real (Chatwoot HMAC), no reparable desde aquí |
| command-center `01-offices/content-studio` (solo lectura) | ídem | 14 passed, 9 failed (23 total) | 19 | ⚠️ 9 fallos 100% por path Windows hardcodeado (`D:/...`), esperado fuera del OMEN |
| `amazon-fba-product-hunter` | `pytest tests/ -v` | 156 passed | 156/156 | ✅ |
| `cano-investment-intelligence` | `pytest -q` | 138 passed, 0 failed | 145/145 con 1 roto (conteo bajó por commits de feature intermedios, no regresión) | ✅ |
| `ugc-commerce-studio` | `pytest` | 21 passed (11 preexistentes + 10 de scoring nuevo) | — | ✅ |

Detalle completo de cada fallo (incluida la nota metodológica de cómo se
corrieron las suites de solo-lectura sin dejar huella en command-center) en
`reports/f15-iteracion-1-2026-08-06.md`.

## 3. Arquitectura construida (resumen)

F0-F15 dejó operativas 7 oficinas nativas de StarHome más un team de Finanzas
nuevo (`agents/finance/`, 3 agentes sin colisión de id); PROMETEO/forge
operativo con 3 candidatos en `pending_approval`, probado con un pipeline
Docker real; `ApprovalService` y `BudgetService` reales (no simulados) que
bloquean gasto hasta aprobación explícita de Cano; `ContainerSandboxExecutor`
con imagen `starhome/sandbox-worker:latest` ya construida (rootless,
`--network none`, cero secretos); Baserow self-hosted arriba
(`starhome-baserow`, healthy) más 2 oficinas Docker con corridas reales
(`office-analytics`, `office-ugc`) y 2 diseñadas pero no desplegadas
(`office-content`, `office-publish`, con guardas explícitas de "nunca
credenciales de publicación aquí"); dashboard agregado de F13 con un ciclo
diario ya corrido que escribió en Baserow; y una oficina de Market Intel
diseñada en F14 con 2 repos de research externos ya clonados y operativos
(`.upstreams/`, gitignorados).

## 4. Iteraciones del bucle de convergencia (F15)

F15 corrió 2 iteraciones y convergió en la iteración 2. Iteración 1 reparó 5
items triviales (test frágil de `cano-investment-intelligence`, skill
`engineering-loop` faltante, rebase del PR de finance-office, backup de
`.env` movido fuera del working tree, scoring UGC codificado) y abrió 3 PRs.
Iteración 2 revisó los 16 pendientes restantes, confirmó que ninguno es
reparable por el agente (todos son credencial/cuenta/decisión de producto o
requieren escritura en un repo de solo lectura), verificó punto por punto la
tabla de criterios de éxito del plan maestro, y declaró convergencia.

Fuente completa: `reports/f15-iteracion-1-2026-08-06.md` +
`reports/f15-pendientes-cano-2026-08-06.md` (la declaración de convergencia
y la tabla de criterios están al final de este segundo archivo, bajo
"Iteración 2 — declaración de convergencia").

## 5. Pendientes de Cano (resumen por categoría)

Tabla completa de 16 items en `reports/f15-pendientes-cano-2026-08-06.md` —
no se duplica aquí. Por categoría:

| Categoría | N | Items |
|---|---|---|
| Credenciales / cuentas por dar de alta o renovar | 9 | `wrangler login` (#1), OAuth Nous/Codex/xAI/Qwen (#2), NVIDIA Public API Endpoints (#3), 6 credenciales YouTube (#7), Higgsfield suspendida (#8), META_APP_ID/SECRET (#9), 7 servicios sin llave — Shopify/Meta/Gamma/Canva/Vercel/Adobe (#10), SUPABASE_KEY ambigua (#11), credenciales de `amazon-fba-product-hunter` (#12) |
| Decisiones de producto / seguridad de Cano | 3 | Revisión manual de 3 skills HyperFrames High Risk (#5), rotar token Telegram de `orion-config` (#6), rotación recomendada de Kimi/NVIDIA por exposición en transcript (#13) |
| Repos de solo lectura (solo reportable, no reparable desde este agente) | 4 | `stage-handlers.yaml` de factory-v5 a copiar desde la OMEN (#4, técnicamente "traer un archivo" pero bloqueado por acceso a la OMEN, no por escritura en command-center), posibles llaves hardcodeadas en 3 archivos de command-center (#14), 2 hallazgos de seguridad adicionales ya documentados en command-center (#15), posible bug real de Chatwoot HMAC en command-center (#16) |

## 6. Resultado del checklist de seguridad F16

**1. `git status --short` limpio en los 4 repos propios con `.env`:**
- `cano-hermes-agentic-os`: limpio.
- `factory-ia-channel-v5`: limpio.
- `amazon-fba-product-hunter`: limpio.
- `hermes-agent`: **no limpio** — 4 entradas untracked (`.agents/`, `.claude/`,
  `.nexus/`, `skills-lock.json`), ninguna de esta sesión. Son metadata de
  Nexus/Graphify y skills locales (workspaces registrados hacia
  `cano-ai-command-center`, sin contenido de credenciales — grepeadas contra
  los mismos patrones de llave del punto 3, limpias). No es `.env` ni
  contiene secretos; se deja tal cual por instrucción explícita de no tocar
  a ciegas algo que no es de esta sesión. **Reportado, no tocado.**

**2. Permisos 600 en los `.env`:**
- `cano-hermes-agentic-os/.env`: 600 ✅
- `factory-ia-channel-v5/.env`: 600 ✅
- `hermes-agent/.env`: 600 ✅
- `amazon-fba-product-hunter/.env`: 600 ✅ (corregido en F15-it1, veníade 664)
- `cano-ai-command-center/.env`: 600 ✅ (solo lectura, solo verificado)
- `cano-ai-command-center/01-offices/content-studio/.env`: 600 ✅ (solo lectura, solo verificado)

Los 6 en regla, nada que reportar.

**3. Grep de patrones de llave larga en archivos trackeados (no `.env`):**
Patrones: `sk-[a-zA-Z0-9_-]{20,}`, `nvapi-`, `ghp_`, `xox[baprs]-`, `AKIA`,
bloques `PRIVATE KEY`, JWT-like. Limpio en `cano-hermes-agentic-os`,
`factory-ia-channel-v5` y `amazon-fba-product-hunter` (0 resultados). En
`hermes-agent` el grep sí produce coincidencias, pero las ~25 son 100%
fixtures de test y ejemplos de documentación diseñados para probar el propio
código de redacción/aislamiento de credenciales del repo (`agent/redact.py`,
`tests/agent/test_anthropic_adapter.py`,
`tests/agent/test_anthropic_token_scope_isolation.py`, doctest de
`mask_secret`, ejemplo `sk-xxxxxxxxxxxxxxxxxxxx` en docs de MCP nativo, y la
clave AWS de ejemplo oficial `AKIAIOSFODNN7EXAMPLE`). Ninguna es una
credencial real — los valores dicen explícitamente `FAKE`, `WRONG`,
`LEAKED-PROFILE-B`, `EXAMPLE`, `testtoken`, etc. **Sin hallazgo nuevo.**

**4. `tests/test_credential_isolation.py`:** ejecutado en
`cano-hermes-agentic-os` con el venv del repo — **6 passed**. Sigue verde.

**5. Sandbox y oficinas Docker — env vars reales que entran a cada
contenedor:**
- `ContainerSandboxExecutor` (`cano_hermes/runtimes/container_sandbox.py`):
  `EXECUTOR_SECRET_ALLOWLIST["container-sandbox"]` está vacío por diseño —
  cero secretos, siempre. Corre como uid 10001, `--read-only`, `--cap-drop
  ALL`, `--network none` por defecto, sin socket de Docker montado, `--rm`.
  Confirmado en código, no hay contenedor sandbox corriendo ahora mismo para
  inspeccionar en vivo, pero el diseño no deja superficie para inyección de
  secretos.
- Oficinas Docker (`infrastructure/offices/docker-compose.yml`, F11): no hay
  contenedores de oficina corriendo en este momento (se levantan bajo
  demanda, sin `restart:` — comportamiento esperado, no un hallazgo).
  Inspeccionado el compose directamente: cada servicio declara su
  `environment:` por nombre explícito, nada de `env_file` a granel. Las 4
  oficinas comparten el ancla `hermes-tier0-env` (`KIMI_API_KEY`,
  `KIMI_BASE_URL`, `NVIDIA_API_KEY` opcional) — coherente con el tier 0
  documentado. `office-ugc` además recibe `RAPIDAPI_KEY` y `APIFY_API_KEY`
  (allowlisted para su función de scraping/tracking, aunque el `task.sh` de
  hoy no las usa todavía). `office-publish` explícitamente **no** recibe
  ninguna credencial de publicación — hay un comentario en el compose que
  dice "No publish credentials here, ever", coherente con que el dispatch
  real pasa por `ApprovalService` fuera del contenedor. El `.env` real de
  StarHome se enmascara dentro de cada contenedor con un archivo vacío
  (`common/empty.env`) montado sobre la ruta donde `hermes_cli` esperaría un
  dotenv — los contenedores corren como uid 10001, distinto del dueño del
  `.env` real (0600), así que tampoco podrían leerlo aunque el mount no
  estuviera enmascarado. `cap_drop: ["ALL"]` + `no-new-privileges:true` en
  las 4. Sin hallazgo.
- `infrastructure/baserow/docker-compose.yml`: contenedor corriendo
  (`starhome-baserow`, healthy). Usa su propio `.env` local
  (`infrastructure/baserow/.env`, 600, gitignorado) con una sola variable
  (`BASEROW_SECRET_KEY`) — no comparte ni referencia ninguna credencial de
  StarHome o de las oficinas. Sin hallazgo.
- Búsqueda de valores hardcodeados en los 6 `Dockerfile*` del repo: 0
  resultados.

**6. `orion-config/claude-daemon.py`:** confirmado que el archivo sigue en
el repo (142623 bytes, mtime 2026-08-05), sin editar — sigue siendo el
mismo hallazgo documentado en el `CLAUDE.md` raíz (token de Telegram
filtrado, pendiente de rotar en BotFather). No se tocó, es un repo
archivado ("no usar"). Recordatorio confirmado vigente, no una acción de
este agente.

## 7. PRs abiertos esperando revisión de Cano

`gh pr list --state open` en cada repo propio tocado durante el plan
(filtrado por autor `syacreator09-sys` donde el repo tiene tráfico externo
no relacionado — ver nota sobre `hermes-agent` abajo):

| Repo | # | Título | Rama | Estado |
|---|---|---|---|---|
| `cano-hermes-agentic-os` | 5 | feat(finance): create finance team, move budget-controller from governance | `feat/finance-office` | OPEN |
| `cano-hermes-agentic-os` | 6 | fix: create missing engineering-loop skill | `fix/engineering-loop-skill` | OPEN |
| `factory-ia-channel-v5` | 1 | feat(sya-motive): add six approved storyboard skill systems | `feature/sya-motive-six-style-skills` | DRAFT |
| `factory-ia-channel-v5` | 2 | feat: add SYA Motive Precision Mindset skill | `feat/sya-motive-precision-mindset` | DRAFT |
| `factory-ia-channel-v5` | 3 | feat(sya-motive): add safe varied Precision Mindset carousels | `feature/sya-motive-precision-mindset-safe` | DRAFT |
| `amazon-fba-product-hunter` | 1 | feat: sales_data_source tracking + 6-phase pipeline redesign | `feature/sales-source-and-pipeline-redesign` | OPEN |
| `cano-investment-intelligence` | 1 | feat: CANO Investment Intelligence V0.3 executable read-only market command center | `build/full-platform-v0.1` | DRAFT |
| `ugc-commerce-studio` | 1 | fix: resolve Windows npm .cmd shims and force UTF-8 in subprocess calls | `fix/windows-subprocess-cmd-and-encoding` | OPEN |
| `ugc-commerce-studio` | 2 | feat: codify UGC product scout 100-point scoring rubric | `feat/product-scout-score` | OPEN |

**Nota sobre `hermes-agent`:** el remoto de este repo es
`NousResearch/hermes-agent` (el proyecto público upstream). `gh pr list
--state open` sin filtro devuelve ~30 PRs recientes — son la cola de PRs de
la comunidad del proyecto público, ninguno de Cano. `gh pr list --state open
--author "@me"` confirma **0 PRs abiertos de Cano** en este repo. No se lista
arriba por no ser ruido relevante.

## 8. Hallazgos nuevos en F16 (no vistos en fases anteriores)

Ninguno con severidad — un solo punto informativo:
- `hermes-agent` tiene 4 entradas untracked no relacionadas a `.env`
  (`.agents/`, `.claude/`, `.nexus/`, `skills-lock.json`) que no aparecían
  mencionadas explícitamente en los reportes de F15. Verificadas limpias de
  secretos (mismo grep del punto 3) y no son de esta sesión — quedan
  reportadas aquí, no tocadas, per instrucción del checklist de F16.

Todo lo demás (permisos, grep de llaves, aislamiento de credenciales,
sandbox/Docker, token de Telegram) confirmó exactamente lo ya documentado en
fases anteriores, sin sorpresas.

## 9. Declaración de cierre

**Plan Prometeo F0-F16: completo.** F16 no encontró nada que bloquee el
cierre — el único hallazgo nuevo (untracked no relacionado a `.env` en
`hermes-agent`) es informativo, sin riesgo, y no accionable a ciegas. Todo lo
que sigue abierto son, sin excepción, pendientes explícitos de Cano:

- Los 16 pendientes de la tabla de F15 (§5 arriba) — credenciales, cuentas,
  decisiones de producto, o ediciones en repos de solo lectura.
- Los 9 PRs abiertos de §7, esperando revisión/merge de Cano.
- El recordatorio de `orion-config/claude-daemon.py` — rotar el token de
  Telegram en BotFather (repo archivado, sin urgencia operativa pero
  pendiente de higiene).

No se requiere ninguna iteración adicional del bucle de convergencia ni
ninguna acción más de este agente. El próximo movimiento en el plan queda
fuera de F0-F16: "Post-plan: interfaz de voz/chat para hablar con Prometeo"
(pendiente, sin fecha).
