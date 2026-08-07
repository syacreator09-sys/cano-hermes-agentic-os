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

## Actualización 2026-08-07 (misma sesión, Cano presente)

- ✅ **`wrangler login` conectado** (`syacreator09@gmail.com`).
- ✅ **Codex OAuth conectado** (ChatGPT) — pero **sin cuota disponible ahora**:
  `codex exec` responde "You've hit your usage limit... try again at 9:35 PM"
  o comprar créditos en chatgpt.com/codex/settings/usage. Reintentar después
  de esa hora, o revisar el plan.
- Ítems #2 y #3 de la tabla "Rápidos" arriba: resueltos en cuanto a conexión;
  #3 (wrangler) 100% operativo, #2 (codex) conectado pero bloqueado por cuota
  hasta 9:35 PM.

## Actualización 2026-08-07 (USB con credenciales, fusionado en vivo)

Cano trajo `credenciales.rar` por USB desde la OMEN (protegido con
contraseña, dada por fuera del vault normal, nunca impresa). Contenía 7
snapshots históricos de `.env` (abr-ago 2026) + tokens YouTube completos
de los 8 canales.

- ✅ **44 claves nuevas fusionadas al vault** (solo agregadas, nunca
  sobrescritas las que ya funcionaban): `RAPIDAPI_KEY`, `KIE_API_KEY` +
  `KIE_API_KEY_2`, `GBRAIN_DATABASE_URL`, `HEYGEN_API_KEY`,
  `SHOPIFY_SHOP_URL`/`SHOPIFY_STORE`, `SKYDROPX_*`, `ENVIA_API_TOKEN`,
  `YOUTUBE_CLIENT_ID/SECRET_CASS`, `MINIO_*`, `CF_AI_TOKEN`,
  `VPS1/VPS2_COOLIFY_API_TOKEN`, y más. Pendientes #6 (Supadata — NO
  estaba en este RAR, sigue pendiente), #9 (RapidAPI — **resuelto**), #7
  parcial (Kie sí, Higgsfield no estaba en este RAR).
- ✅ **8/8 canales de YouTube ahora en vivo** (antes 2/8), validado con
  `channels.list(mine=True)` real contra cada uno: cano-digital-ia (52
  subs/125 videos), cass-healt (33/108), sya-animals (58/109), sya-motive
  (265/186), unsolved-lens (15/17), cosmic-lens (13/17), wild-whiskers
  (10/15), sleepy-lofi (13/15). Pendientes #13/#14 de canales YouTube
  **resueltos por completo**.
- Backup del RAR extraído (7 versiones de `.env` + tokens) queda en
  `~/.secrets/backups-locales/usb-extract-20260807/` (permisos 600/700,
  fuera de cualquier repo git).
- Nota: `SUPADATA_API_KEY` y `HIGGSFIELD_API_KEY` NO estaban en ninguna
  de las 7 versiones de este RAR — siguen genuinamente pendientes de otra
  fuente.

## Actualización 2026-08-07 (paridad Factory V5 — gate real)

Retomé el paquete "paridad Factory V5" (`cano-ai-command-center`,
`.command-center/hermes-remote/CAPABILITY_HANDOFF_FACTORY_V5.md`, solo
lectura) y corrí su gate de paridad real (`scripts/factory_v5_preflight.py`,
replicado en `~/repos/factory-ia-channel-v5`, mismo diseño no-facturable de
command-center):

| Proveedor | Estado | Detalle |
|---|---|---|
| Apify | ✅ `configured_metadata_only` | token presente |
| Kie | ✅ `configured_execution_disabled` | key presente, flags de ejecución real apagados por diseño |
| ElevenLabs | ✅ `configured_executor_required` | key presente |
| **Remotion** | ✅ `available` | **Construido de cero, render real verificado** (PNG 1280x720 genuino) — no existía en este repo, solo en la OMEN |
| CUDA | N/A (por diseño) | sin GPU, esperado |
| Supadata | ❌ `not_configured` | sigue sin llave en ningún lugar (vault, USB de hoy, ningún .env) |

**4/5 gates en verde** (5/5 si cuentas CUDA N/A como esperado, no como falla).
Único gap real: Supadata, credencial que genuinamente no existe en ningún
lugar accesible — necesita alta de cuenta nueva con el proveedor.

**Nota de honestidad**: el Remotion nuevo es una composición mínima
(`editorial-thumbnail`) para pasar el gate con una base real y funcional —
NO son las 14 composiciones de producción reales de la OMEN
(EditorialExplainer, CampaignCarousel, Short, Long, etc.). Esas necesitan
transferencia de archivos reales desde la OMEN (mismo patrón que
`stage-handlers.yaml`), no se pueden fabricar sin el código fuente real.
