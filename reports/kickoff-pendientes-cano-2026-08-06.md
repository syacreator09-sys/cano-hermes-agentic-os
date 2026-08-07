# HERMES-KICKOFF — Pendientes de Cano (tabla consolidada)

Plan HERMES-KICKOFF, K16 iteración 1, 2026-08-06. Consolida en un solo lugar
todos los gates que fueron apareciendo a lo largo de K0-K19 (dispersos en
`reports/k8-demo-e2e-2026-08-06.md`, `reports/k11-memoria-unificada-2026-08-06.md`,
`reports/f12-oauth-channels-2026-08-06.md`, `docs/OPERATIONS.md`,
`docs/K9_OFFICES_V2_REPORT.md`), más lo verificado hoy en la auditoría K16-it1.
Formato heredado de `reports/f15-pendientes-cano-2026-08-06.md` (plan Prometeo).
Nada de esto se intentó resolver desde este agente — solo se compiló y,
donde aplicaba, se reconfirmó que el hallazgo original sigue vigente.

| # | Pendiente | Detalle | Dónde actuar | Origen |
|---|---|---|---|---|
| 1 | Rotar `KIMI_API_KEY` y `NVIDIA_NIM_API_KEY` | 2 exposiciones en texto plano en transcript de sesión (F11 del plan Prometeo, y de nuevo en K9 al validar `docker compose config` sin `--no-interpolate`). Nunca en disco fuera de `.env`, pero sí en `~/.claude/projects/*.jsonl` por la regla del `CLAUDE.md` raíz. K16-it1 usó siempre `--no-interpolate` y no repitió la fuga. | Rotar ambas keys por precaución, proveedores Kimi/NVIDIA | F11 + K9, consolidado K16-it1 |
| 2 | OAuth Codex | Sesión OAuth de Codex CLI pendiente de que Cano la cree — bloquea el perfil `codex` de ejecución (decidido en el plan: "Codex SÍ se incluye, OAuth pendiente de Cano") | Login manual `codex` CLI | Plan HERMES-KICKOFF (decisión inicial) |
| 3 | NVIDIA Public API Endpoints | La key NIM da 403 — falta habilitar "Public API Endpoints" en el dashboard NVIDIA. Bloquea tier 0 gratis para motor por defecto de oficinas | build.nvidia.com, cuenta de Cano | Memoria (`nvidia-key-invalida`), reconfirmado F15/K16 |
| 4 | `libportaudio2` (paquete de sistema) | Voz (K13) tiene todo listo — ONNX, `openwakeword`, `onnxruntime`, `sherpa-onnx`, `sounddevice` — salvo esta lib nativa de audio. `sudo apt-get install -y libportaudio2` falla sin contraseña sudo interactiva. Paquete trivial, sin riesgo (no toca red ni credenciales) | Terminal de Cano, un solo comando `sudo apt-get install -y libportaudio2` | K13 |
| 5 | `SUPADATA_API_KEY` | Sigue ausente de todo vault — bloquea transcripts reales de `hermes-research` y del proveedor Supadata en factory-v5. `not_configured` reportado correctamente, no es bug | Alta de cuenta/API key con el proveedor Supadata | F15-it1, reconfirmado K9 |
| 6 | Credenciales de `amazon-fba-product-hunter` | `CONTARMARKET_*`, `FLYBY_API_KEY`, `KEEPA_API_KEY`, `AMAZON_SP_API_*` — pendientes de alta. Suite sigue verde con fixtures (156/156) sin ellas | Alta de cuenta/API key por proveedor | F15-it1, priorizado por Cano |
| 7 | `RAPIDAPI_KEY` | Sigue ausente de `~/.secrets/credenciales/credenciales/.env` (confirmado de nuevo hoy) — bloquea `rapidapi-tiktok` en el gateway hermes | Alta de cuenta/API key RapidAPI | K15/OPERATIONS.md, reconfirmado K16-it1 |
| 8 | gbrain (Supabase + RLS) | Credenciales Supabase de `gbrain-knowledge` viven solo en `~/.gbrain/config.json` de la OMEN, no replicadas aquí. Además 10 tablas con RLS deshabilitado — el fix (`gbrain-rls-advisory.sql`) ya existe en command-center pero sin aplicar (repo solo-lectura desde este agente) | 1) Aplicar el advisory SQL contra Supabase `gbrain-knowledge` (Cano o vía command-center directamente); 2) copiar `~/.gbrain/config.json` de la OMEN a esta máquina | K11 |
| 9 | YouTube — 6/8 canales con acción pendiente | 3 canales (`unsolved-lens`, `wild-whiskers`, `sleepy-lofi`) tienen `client_secret` pero falta `youtube_token.json` — requieren re-autorización por navegador (comandos exactos ya preparados). 3 canales (`sya-animals`, `sya-motive`, `cosmic-lens`) no tienen `client_secret` utilizable — requieren provisión nueva en Google Cloud Console. Solo 2/8 (`cano-digital-ia`, `cass-healt`) están LIVE y no necesitan acción | `reports/f12-oauth-channels-2026-08-06.md` (comandos exactos incluidos) | F12 |
| 10 | `PENDING_NATIVE_TOOL` — Shopify/Meta (K19) | 2 jobs pendientes en disco: `cass-shopify-status.request.json` y `cass-meta-status.request.json` (`storage/pending_native_tool/`). Diseño intencional: StarHome no tiene sesión MCP propia, deja el job en disco hasta que Cano (o una sesión de Claude.ai con esos MCP conectados) los resuelva con el comando explícito "resuelve los jobs PENDING_NATIVE_TOOL de StarHome" | Comando explícito de Cano en una sesión con Shopify/Meta MCP conectados | K15/K19, confirmado presentes hoy en K16-it1 |
| 11 | Rotar token Telegram de `orion-config` | `orion-config/claude-daemon.py` tiene un token de Telegram filtrado, pendiente de rotar en BotFather (repo archivado, no se usa) | BotFather + reemplazar en el archivo | `CLAUDE.md` raíz |
| 12 | `runtime/stage-handlers.yaml` de factory-v5 | Sigue faltando — bloquea exactamente 7/203 tests (2 directos por `FileNotFoundError`, 5 en cascada). Reconfirmado hoy corriendo la suite completa: 196/203, mismo baseline exacto de F15 | Copiar el archivo desde la OMEN a `~/repos/factory-ia-channel-v5/runtime/stage-handlers.yaml` | F-anterior, reconfirmado K16-it1 |
| 13 | Higgsfield suspendida | Cano priorizó reactivarla (tier premium avatares/video UGC). Reactivación es acción suya con el proveedor (pago); el enganche en `ugc-commerce-studio` ya está listo en modo `PENDIENTE_APROBACION` | Reactivar cuenta con Higgsfield | F9, priorizado por Cano |
| 14 | `wrangler login` | Cloudflare Workers/R2 sin sesión — bloquea deploy de `cano-investment-intelligence` (queue-consumer, workflow-orchestrator). Suite del repo sigue 100% verde (138 pytest + 7/7 `npm verify:node`) sin necesitar el deploy real | Terminal de Cano, `wrangler login` (no tokens API) | F-anterior, sigue vigente |
| 15 | Rama nueva en `cano-ai-command-center`: `feat/factory-v5-upload-campaign-10-day` | **Solo-lectura, no ejecutado.** `main` de command-center sigue igual (`76c4676`, sin commits nuevos desde la última auditoría "KAI autonomous design"), pero hay una rama remota nueva empujada hoy con 4478 archivos cambiados (+2.35M/-2.2K líneas) — incluye scripts de bootstrap para réplica en Mac/Windows, `hermes-remote` capability parity package, y el checkout de YouTube-tokens que F12 usó como fuente. Volumen sugiere que puede incluir material vendored/dependencias, no solo cambios propios — requiere revisión humana antes de decidir si se integra algo | Revisar la rama en command-center directamente (fuera de este agente, solo lectura) | Detectado hoy en K16-it1 |
| 16 | `test_chatwoot_hmac_skip_when_no_token` en `agents-platform` (command-center) | Posible bug real de validación HMAC de Chatwoot cuando no hay token — command-center es solo lectura, solo se puede reportar | Revisar test y código HMAC directamente en command-center | F15-it1, no re-auditado hoy (fuera del alcance explícito de K16) |
| 17 | 3 skills HyperFrames High Risk | `media-use`, `motion-graphics`, `talking-head-recut` — Cano ya confirmó ALTO, quedan fuera de cualquier oficina automática permanentemente, revisión manual caso por caso. **No es una acción pendiente, es una política ya fijada** — se deja en la tabla como recordatorio operativo | — (política ya aplicada) | F-anterior, resuelto F15 |

## Notas de esta iteración (K16-it1)

- El punto #15 es el único hallazgo nuevo de hoy que no estaba en ninguna
  tabla anterior — se detectó al hacer `git fetch --all` en
  `cano-ai-command-center` como pide el mandato K16.
- Todos los demás puntos son reconfirmaciones: se verificó activamente que
  cada uno sigue vigente (corriendo la suite relevante, `grep` sobre vault,
  o revisando el archivo/directorio en disco), no se copiaron de memoria sin
  comprobar.
- Ninguno de los 17 puntos se intentó resolver ni se tocó ningún archivo de
  `cano-ai-command-center`. Todos requieren credencial, sesión OAuth,
  contraseña sudo interactiva, decisión de producto/gasto de Cano, o revisión
  humana de una rama nueva.
