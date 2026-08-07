# Pendientes de Cano — tabla vigente (2026-08-07)

Reemplaza `reports/kickoff-pendientes-cano-2026-08-06.md` (queda como
histórico). Fusiona los 17 pendientes de HERMES-KICKOFF (K0-K19) con los
gaps nuevos encontrados hoy al revisar el paquete de paridad Factory V5
(`cano-ai-command-center`, rama `feat/factory-v5-upload-campaign-10-day`,
solo lectura). Resuelto hoy en vivo con Cano presente: los 2 jobs
`PENDING_NATIVE_TOOL` de CASS (Shopify+Meta, ver
`storage/pending_native_tool/*.result.json`) y el montaje de los 11 repos
anidados de factory-v5 (symlinks desde `~/repos/`, `.gitignore` actualizado).

## Rápidos — 1 comando o 1 clic

| # | Qué | Acción exacta | Estado |
|---|---|---|---|
| 1 | `libportaudio2` | `sudo apt-get install -y libportaudio2` (correrlo tú vía `!` en el chat, o en tu propia terminal) | Ofrecido hoy, pendiente de que lo corras tú (sudo interactivo) |
| 2 | OAuth Codex | `codex` CLI, login interactivo | Pendiente |
| 3 | `wrangler login` | en `~/repos/cano-investment-intelligence` | Pendiente |
| 4 | NVIDIA Public API Endpoints | build.nvidia.com → habilitar en tu cuenta | Pendiente |
| 5 | Rotar `KIMI_API_KEY`/`NVIDIA_NIM_API_KEY` | dashboards de cada proveedor — expuestas 3 veces en logs de sesión (F11, K9, K16) | Pendiente, recomendado |

## Credenciales a transferir out-of-band (nunca por chat/git)

| # | Qué | Para qué desbloquea | Nota |
|---|---|---|---|
| 6 | `SUPADATA_API_KEY` | Research/transcripts reales en `hermes-research` y factory-v5 | Según la auditoría de hoy, **ya está activa en el entorno de origen (OMEN)** — solo falta copiarla aquí |
| 7 | Bloque `KIE_*` (~28 vars) | Video corto Kie/Grok-imagine-video-1-5-preview | Catálogo completo en `ENV_TEMPLATE_HERMES.env.example` de command-center (solo lectura) |
| 8 | `HIGGSFIELD_API_KEY` | UGC premium (avatares, video) | Cuenta plan plus, 12.58 créditos activos en el OMEN según la auditoría |
| 9 | `RAPIDAPI_KEY` | `rapidapi-tiktok` MCP en el gateway hermes | Sigue sin existir en ningún vault (confirmado 5+ veces) |
| 10 | `CONTARMARKET_*`, `FLYBY_API_KEY`, `KEEPA_API_KEY`, `AMAZON_SP_API_*` | Research real de `amazon-fba-product-hunter` (suite ya verde con fixtures) | Priorizado por Cano en su momento |
| 11 | `~/.gbrain/config.json` de la OMEN | Memoria gbrain (Nexus ya tiene el punto de extensión listo, K11) | Aplicar también `gbrain-rls-advisory.sql` en Supabase antes de conectar ningún agente |
| 12 | Assets solo-locales de la OMEN: `ugc-forge/`, skills globales `.claude/skills` (231, subconjunto según `INSTALL_MANIFEST_HERMES.md`), medios reutilizables (609 assets) | Paridad completa de herramientas | Transferir por zip/rsync, **nunca por git** |

## Requieren tu navegador/cuenta directamente

| # | Qué | Detalle |
|---|---|---|
| 13 | Re-autorizar 3 canales YouTube | `unsolved-lens`, `wild-whiskers`, `sleepy-lofi` — comandos exactos en `reports/f12-oauth-channels-2026-08-06.md` |
| 14 | Dar de alta `client_secret` nuevo para 3 canales YouTube | `sya-animals`, `sya-motive`, `cosmic-lens` — Google Cloud Console |
| 15 | Higgsfield: revisar drift de modelo | `.env.local` de factory-v5 tenía `KIE_VIDEO_MODEL=wan/2-5-image-to-video` — **prohibido por contrato**, el único modelo permitido es `grok-imagine-video-1-5-preview` (35 créditos máx). Corregir si sigue así al copiar el `.env` real |
| 16 | Higgsfield suspendida (si sigue así) | Reactivar cuenta con el proveedor — priorizado por Cano |

## Solo revisión/decisión — sin acción técnica automática

| # | Qué | Detalle |
|---|---|---|
| 17 | Rama `feat/factory-v5-upload-campaign-10-day` de command-center | 4478 archivos / +2.35M líneas vs `main` de ese repo — probablemente vendored/nested repos, no solo cambios propios. Decidir si vale la pena mergear a `main` de command-center (fuera del alcance de este agente, solo lectura ahí) |
| 18 | `test_chatwoot_hmac_skip_when_no_token` (agents-platform, command-center) | Posible bug real de validación HMAC — solo reportable, command-center es solo lectura |
| 19 | `runtime/stage-handlers.yaml` de factory-v5 | Sigue faltando — bloquea exactamente 7/203 tests (reconfirmado hoy: 196/203, mismo baseline). Copiar desde la OMEN |
| 20 | Rotar token Telegram de `orion-config` | BotFather — repo archivado, no se usa activamente |
| 21 | **La trampa de los pipelines YAML** (hallazgo nuevo de la auditoría) | `apps/api/app/services/pipeline_runtime.py` de factory-v5 crea filas `JobStage` pero NO invoca ningún provider/renderer real — todo lo que produjo contenido real corrió vía `scripts/produce_*.py` directos. Si en el futuro se construye algo nuevo sobre factory-v5, replicar los scripts, no los YAML — anotado para que no se repita el error de asumir que los pipelines declarativos ejecutan |

## Política ya fijada (no requiere acción, solo recordatorio)

| # | Qué |
|---|---|
| 22 | 3 skills HyperFrames High Risk (`media-use`, `motion-graphics`, `talking-head-recut`) — Cano ya confirmó ALTO, revisión manual permanente |

## Resuelto hoy (2026-08-07, con Cano presente)

- ✅ 2 jobs `PENDING_NATIVE_TOOL` de CASS (Shopify: 0 órdenes, 10+ productos ASPIDPRO reales; Meta: página confirmada, sin métricas orgánicas por límite del MCP conectado).
- ✅ 11 repos anidados de factory-v5 montados en sus rutas reales vía symlink (`engines/ugc/`, `.vendor/cano-tutorials/*`, `.vendor/santmun-quarantine/*`, `tools/external/video-docs-builder`) + `.gitignore` actualizado. `moneyprinter-turbo` ya estaba vendored directo, sin acción.
- ✅ Ofrecido `libportaudio2` — Cano decide si lo corre él mismo vía `!`.
