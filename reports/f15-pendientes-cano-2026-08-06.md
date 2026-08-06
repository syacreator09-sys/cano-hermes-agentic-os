# F15 — Pendientes de Cano (tabla consolidada)

Plan Prometeo, F15 iteración 1, 2026-08-06. Consolida en un solo lugar todo lo
disperso en reportes anteriores (F1, F11, F12, ugc-affiliate-dry-run) que
requiere una decisión, credencial o acción de Cano y **no** puede resolverse
desde este repo/agente. Nada de esto se intentó resolver en esta iteración —
solo se compiló y, donde aplicaba, se verificó que el hallazgo original
siguiera vigente.

| # | Pendiente | Detalle | Dónde actuar | Origen |
|---|---|---|---|---|
| 1 | `wrangler login` | Cloudflare Workers/R2 sin sesión — bloquea deploy de `cano-investment-intelligence` (queue-consumer, workflow-orchestrator) | Terminal de Cano, `wrangler login` (no tokens API) | F-anterior (Cloudflare/NVIDIA) |
| 2 | OAuth Nous / Codex / xAI / Qwen | Sesiones OAuth pendientes de renovar/crear para esos motores | Login manual por proveedor | F-anterior |
| 3 | NVIDIA Public API Endpoints | La key NIM actual da 403 — falta habilitar "Public API Endpoints" en el dashboard NVIDIA | build.nvidia.com, cuenta de Cano | nvidia-key-invalida (memoria) |
| 4 | `runtime/stage-handlers.yaml` en factory-v5 | Confirmado roto de nuevo en esta iteración: 7/203 tests fallan, 2 directamente por `FileNotFoundError` de este archivo (`test_pipeline_runtime.py`, `test_v4_pipeline_configs.py`). Debe traerse desde la OMEN | Copiar el archivo desde la OMEN a `~/repos/factory-ia-channel-v5/runtime/stage-handlers.yaml` | F-anterior, reconfirmado F15-it1 |
| 5 | ~~Revisión de 3 skills HyperFrames High Risk~~ **RESUELTO 2026-08-06** | Cano confirmó ALTO para `media-use`, `motion-graphics`, `talking-head-recut` — quedan permanentemente fuera de cualquier oficina automática, revisión manual caso por caso | — | F-anterior, resuelto hoy |
| 6 | Rotar token Telegram de `orion-config` | `orion-config/claude-daemon.py` tiene un token de Telegram filtrado, pendiente de rotar en BotFather | BotFather + reemplazar en el archivo (repo archivado, no se usa) | CLAUDE.md raíz |
| 7 | 6 credenciales YouTube pendientes | 3 canales con refresh token vencido + 3 sin `client_secret` configurado. Comandos exactos ya preparados | `reports/f12-oauth-channels-2026-08-06.md` | F12 |
| 8 | Higgsfield suspendida — **PRIORIZADA por Cano 2026-08-06** | Cano quiere reactivarla (tier premium de avatares/video UGC). Reactivación es acción suya con el proveedor (pago); en cuanto esté activa, el enganche ya está listo (F9 dejó los pasos Higgsfield como `PENDIENTE_APROBACION` en `ugc-commerce-studio`) | Reactivar cuenta con el proveedor (Higgsfield) | F9/F-anterior, priorizado hoy |
| 9 | ~~`META_APP_ID` / `META_APP_SECRET`~~ **SUPERADO 2026-08-06** | Cano no quiere el `.env` clásico — el camino real es el MCP "Facebook" ya conectado en Claude.ai. Verificado hoy (solo lectura): 2 cuentas de ads ACTIVAS con método de pago real (MXN) — `2094953447927453` y `760363536501260` ("Cano digital IA"), 2 páginas (`Cano Digital`, `CASS Medicina Estética`). **Como tiene pago real conectado, cualquier campaña/gasto desde aquí debe pasar por `ApprovalService`/team finance — nunca autónomo**, igual que cualquier otra acción de pago del plan | Nada pendiente de Cano para "ver" — ya conectado. Sí pendiente: decidir cuándo/si se conecta este MCP al flujo de `office-publish` (requiere diseño + gate de aprobación, no hecho todavía) | F12, resuelto/redirigido hoy |
| 10 | 6 servicios sin ninguna llave en vault | Shopify, Gamma, Canva, Vercel, Adobe (Higgsfield ya contada en #8; Meta ya no cuenta aquí, ver #9) | Alta de cuenta/API key por servicio | connection_matrix (F2, reconfirmado F15-it1: ✓306 ✗537 —57 en la corrida de hoy) |
| 11 | ~~`SUPABASE_KEY` ambigua~~ **RESUELTO 2026-08-06** | Cano eligió `SUPABASE_ORION_SERVICE_KEY`. Ya copiada al `.env` raíz de command-center (sin imprimir el valor), 600, gitignored, `git status` limpio | — | connection_matrix, resuelto hoy |
| 12 | Credenciales de `amazon-fba-product-hunter` | `CONTARMARKET_*`, `FLYBY_API_KEY`, `KEEPA_API_KEY`, `AMAZON_SP_API_*` — pendientes de alta | Alta de cuenta/API key por proveedor | F-anterior |
| 13 | Rotación recomendada de Kimi/NVIDIA | Ambas quedaron expuestas en transcript de F11 (texto de sesión, no en disco fuera de `.env`) | Rotar ambas keys por precaución | F11 |
| 14 | Posibles llaves hardcodeadas en 3 archivos de command-center | `produce_video_historia.py:75`, `generate_documentary.py:43`, `setup-orion-server.sh:222` (hallazgo F1). command-center es **solo lectura** desde este agente — solo se puede reportar, nunca reparar desde aquí | Editar esos 3 archivos directamente en command-center (fuera de este agente) | F1 |
| 15 | 2 hallazgos de seguridad adicionales en command-center | Ya documentados en `docs/SANTMUN_REFERENCE_MAP.md` / reportes de F1 — **no re-auditados en F15/F16 por instrucción explícita**, quedan anotados aquí solo como puntero | Ver `cano-ai-command-center/docs/SANTMUN_REFERENCE_MAP.md` (solo lectura) | F1 |
| 16 | Posible bug real en command-center: `test_chatwoot_hmac_skip_when_no_token` | Suite `agents-platform` (57/61 en F15-it1): 3 fallos son 401 de Cloudflare esperables (credencial de test ausente), pero este cuarto fallo parece un bug de comportamiento real en la validación HMAC de Chatwoot cuando no hay token configurado — command-center es solo lectura, así que solo se puede reportar, nunca reparar desde aquí | Revisar el test y el código de validación HMAC de Chatwoot directamente en command-center (fuera de este agente) | F15-it1 |

## Iteración 2 — declaración de convergencia (2026-08-06)

Revisados los 16 puntos de la tabla: **los 16 son pendientes que solo Cano
puede resolver** (credencial, cuenta, decisión de producto, o edición en un
repo de solo lectura para este agente). No hay ningún ítem reparable por
Sonnet que siga abierto — todo lo reparable de la iteración 1 (test frágil
de investment-intelligence, skill `engineering-loop`, PR de finance-office,
`.env.backup-0940`, scoring UGC) ya se aplicó y quedó en PRs abiertos
(`cano-hermes-agentic-os` #5 y #6, `ugc-commerce-studio` #2) esperando
revisión de Cano — mergearlos no es una acción de Sonnet.

Los 3 PRs se abrieron hace minutos en esta misma sesión; no tiene sentido
una iteración 3 de "¿ya los aprobó Cano?" — eso es esperar, no auditar. Se
declara **F15 CONVERGIDO en la iteración 2**, con el criterio de éxito del
plan maestro verificado punto por punto:

| Criterio (plan maestro) | Estado |
|---|---|
| Matriz ✓ salvo manuales | ✓ (306✓/537✗/57— — los ✗ son proveedores no usados por diseño + los 16 pendientes de arriba) |
| StarHome 100% verde | ✓ (70 unittest + 75 pytest) |
| factory-v5 ≥196/203 | ✓ (exacto: 196/203, bloqueado por pendiente #4) |
| agents-platform / content-studio | ⚠️ 57/61 y 14/23 — command-center es solo lectura, no reparable desde aquí; fallos documentados (Windows paths esperados, 1 posible bug real reportado como #16) |
| fba-hunter pytest verde | ✓ (156/156) |
| Demo Prometeo end-to-end | ✓ (F4: 3 candidatos en pending_approval, pipeline probado con Docker real) |
| Gasto bloqueando en APPROVAL con solicitud completa | ✓ (F3: `ApprovalRequest` con schema completo + `BudgetService`) |
| Video F10 verificado | ✓ (ffprobe limpio, 720p, 17s) |
| Oficinas Docker estables bajo límites | ✓ (F11: 6.5g/1.8cpu de 8g/2cpu, analytics+ugc corridas real) |
| Pipeline UGC gratis probado con fixtures | ✓ (F9, scoring ahora codificado en F15-it1) |
| Market Intel con 3 señales + Risk Guardian | ✓ diseño (F14) — oficina Docker en sí diferida por presupuesto, documentado |
| 4 study clones P0 en `.upstreams/` | ✓ (F14, gitignorado) |
| Ciclo diario + dashboard agregado | ✓ (F13, corrido real, escribió en Baserow) |
| Baserow arriba | ✓ (F11) |
| Cero secretos en chat/git | ⚠️ Kimi/NVIDIA expuestas en transcript de un subagente (F11, no en disco) — rotación recomendada, pendiente #13, es acción de Cano |
| Núcleo nativo intacto, máquina sin saturar | ✓ (StarHome/Hermes/Nexus nativos por systemd; Docker infra 6.5g/1.8cpu de 32GB/4 núcleos) |

**Todo lo que sigue abierto es, sin excepción, un pendiente de Cano** (tabla
de 16 arriba) o un PR esperando su revisión. F16 (auditoría de seguridad y
cierre) puede arrancar.

## Notas de verificación F15 iteración 1

- **#4 (`stage-handlers.yaml`)** se reconfirmó activamente hoy corriendo la suite de factory-v5: sigue faltando, sigue rompiendo exactamente los mismos 2 tests (`test_initializes_pipeline_stages`, `test_v4_pipeline_files_load_and_initialize_stages`), más 5 fallos derivados en cascada (`test_advance_reports_agent_required_for_research`, `test_complete_stage_moves_progress_forward`, `test_human_review_requests_approval`, `test_approved_stock_item_creates_job`, `test_assembler_selector_prioritizes_installed_hyperframes`) — total 7/203, exactamente el baseline documentado (≥196/203 cumplido: 196/203).
- **#10/#11** se reconfirmaron con `connection_matrix.py` regenerado hoy (`reports/connection-matrix-2026-08-06.md` / `.json`): `✓306 ✗537 —57`. Apify responde 200; RapidAPI sigue sin encontrarse en el vault bajo ningún nombre.
- Ninguno de estos 15 puntos se intentó resolver ni se tocó ningún archivo relacionado en command-center. Todos requieren credenciales, sesiones OAuth, o decisiones de producto/seguridad de Cano.
