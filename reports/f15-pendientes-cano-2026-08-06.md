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
| 5 | Revisión de 3 skills HyperFrames High Risk | `media-use`, `motion-graphics`, `talking-head-recut` — clasificación ALTO es 100% juicio humano de Cano, no derivable de manifiestos | Revisión manual de Cano | F-anterior |
| 6 | Rotar token Telegram de `orion-config` | `orion-config/claude-daemon.py` tiene un token de Telegram filtrado, pendiente de rotar en BotFather | BotFather + reemplazar en el archivo (repo archivado, no se usa) | CLAUDE.md raíz |
| 7 | 6 credenciales YouTube pendientes | 3 canales con refresh token vencido + 3 sin `client_secret` configurado. Comandos exactos ya preparados | `reports/f12-oauth-channels-2026-08-06.md` | F12 |
| 8 | Higgsfield suspendida | Cuenta/servicio suspendido, bloquea el tier premium de UGC/video | Reactivar cuenta con el proveedor | F9/F-anterior |
| 9 | `META_APP_ID` / `META_APP_SECRET` | Ausentes por completo (ni vacías ni comentadas) en `.env` de command-center — bloquea integración Meta/Facebook | Obtener credenciales de Meta for Developers | F12 (`reports/f12-oauth-channels-2026-08-06.md:189`) |
| 10 | 7 servicios sin ninguna llave en vault | Shopify, Meta, Gamma, Canva, Vercel, Adobe (Higgsfield ya contada aparte en #8) | Alta de cuenta/API key por servicio | connection_matrix (F2, reconfirmado F15-it1: ✓306 ✗537 —57 en la corrida de hoy) |
| 11 | `SUPABASE_KEY` ambigua en `.env` raíz de command-center | Presente pero con valor vacío en el `.env` raíz; ausente en StarHome, factory-v5, hermes-agent y `content-studio` | Decidir si Supabase es necesario y completar la key donde corresponda | connection_matrix (reconfirmado F15-it1) |
| 12 | Credenciales de `amazon-fba-product-hunter` | `CONTARMARKET_*`, `FLYBY_API_KEY`, `KEEPA_API_KEY`, `AMAZON_SP_API_*` — pendientes de alta | Alta de cuenta/API key por proveedor | F-anterior |
| 13 | Rotación recomendada de Kimi/NVIDIA | Ambas quedaron expuestas en transcript de F11 (texto de sesión, no en disco fuera de `.env`) | Rotar ambas keys por precaución | F11 |
| 14 | Posibles llaves hardcodeadas en 3 archivos de command-center | `produce_video_historia.py:75`, `generate_documentary.py:43`, `setup-orion-server.sh:222` (hallazgo F1). command-center es **solo lectura** desde este agente — solo se puede reportar, nunca reparar desde aquí | Editar esos 3 archivos directamente en command-center (fuera de este agente) | F1 |
| 15 | 2 hallazgos de seguridad adicionales en command-center | Ya documentados en `docs/SANTMUN_REFERENCE_MAP.md` / reportes de F1 — **no re-auditados en F15/F16 por instrucción explícita**, quedan anotados aquí solo como puntero | Ver `cano-ai-command-center/docs/SANTMUN_REFERENCE_MAP.md` (solo lectura) | F1 |

## Notas de verificación F15 iteración 1

- **#4 (`stage-handlers.yaml`)** se reconfirmó activamente hoy corriendo la suite de factory-v5: sigue faltando, sigue rompiendo exactamente los mismos 2 tests (`test_initializes_pipeline_stages`, `test_v4_pipeline_files_load_and_initialize_stages`), más 5 fallos derivados en cascada (`test_advance_reports_agent_required_for_research`, `test_complete_stage_moves_progress_forward`, `test_human_review_requests_approval`, `test_approved_stock_item_creates_job`, `test_assembler_selector_prioritizes_installed_hyperframes`) — total 7/203, exactamente el baseline documentado (≥196/203 cumplido: 196/203).
- **#10/#11** se reconfirmaron con `connection_matrix.py` regenerado hoy (`reports/connection-matrix-2026-08-06.md` / `.json`): `✓306 ✗537 —57`. Apify responde 200; RapidAPI sigue sin encontrarse en el vault bajo ningún nombre.
- Ninguno de estos 15 puntos se intentó resolver ni se tocó ningún archivo relacionado en command-center. Todos requieren credenciales, sesiones OAuth, o decisiones de producto/seguridad de Cano.
