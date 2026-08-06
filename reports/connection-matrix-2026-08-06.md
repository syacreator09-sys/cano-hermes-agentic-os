# Matriz de conexiones — 2026-08-06

Generado por `scripts/connection_matrix.py` (plan Prometeo, fase F2).
Nunca contiene valores de llaves — solo presencia/ausencia y, para Apify, el resultado de un GET gratuito de perfil.

## Notas de contexto (✗ esperables, no son bugs)

- `NVIDIA_*`: llave conocida como invalida, rechaza inferencia con 403 (ver memoria del operador).
- `HIGGSFIELD_*`: cuenta suspendida.
- OAuth manuales de canales (Nous/Codex/xAI/Qwen): no viven en estos `.env` como credenciales de archivo — se ven con `hermes status`, actualmente deslogueados; no aplica a esta matriz.

## Sistemas leidos

| sistema | archivo | encontrado |
|---|---|---|
| StarHome | `/home/cano/repos/cano-hermes-agentic-os/.env` | si |
| factory-v5 | `/home/cano/repos/factory-ia-channel-v5/.env` | si |
| command-center (root) | `/home/cano/repos/cano-ai-command-center/.env` | si |
| command-center (content-studio) | `/home/cano/repos/cano-ai-command-center/01-offices/content-studio/.env` | si |
| hermes-agent | `/home/cano/repos/hermes-agent/.env` | si |

## Matriz por proveedor

proveedor|sistema|variable|estado|detalle
---|---|---|---|---
ANTHROPIC|StarHome|ANTHROPIC_API_KEY|—|presente, valor vacio
ANTHROPIC|factory-v5|ANTHROPIC_API_KEY|✗|variable ausente en este archivo
ANTHROPIC|command-center (root)|ANTHROPIC_API_KEY|—|comentada / pendiente
ANTHROPIC|command-center (content-studio)|ANTHROPIC_API_KEY|—|comentada / pendiente
ANTHROPIC|hermes-agent|ANTHROPIC_API_KEY|✗|variable ausente en este archivo
ANYMAIL|StarHome|ANYMAIL_API_KEY|✓|
ANYMAIL|factory-v5|ANYMAIL_API_KEY|✗|variable ausente en este archivo
ANYMAIL|command-center (root)|ANYMAIL_API_KEY|✗|variable ausente en este archivo
ANYMAIL|command-center (content-studio)|ANYMAIL_API_KEY|✗|variable ausente en este archivo
ANYMAIL|hermes-agent|ANYMAIL_API_KEY|✓|
APIFY|StarHome|APIFY_API_KEY|✓|
APIFY|factory-v5|APIFY_API_KEY|✗|variable ausente en este archivo
APIFY|command-center (root)|APIFY_API_KEY|✗|variable ausente en este archivo
APIFY|command-center (content-studio)|APIFY_API_KEY|✗|variable ausente en este archivo
APIFY|hermes-agent|APIFY_API_KEY|✓|
APIFY|StarHome|APIFY_API_TOKEN|✗|variable ausente en este archivo
APIFY|factory-v5|APIFY_API_TOKEN|✓|
APIFY|command-center (root)|APIFY_API_TOKEN|—|comentada / pendiente
APIFY|command-center (content-studio)|APIFY_API_TOKEN|✗|variable ausente en este archivo
APIFY|hermes-agent|APIFY_API_TOKEN|✗|variable ausente en este archivo
APIFY|StarHome|APIFY_KEY_1|✓|
APIFY|factory-v5|APIFY_KEY_1|✗|variable ausente en este archivo
APIFY|command-center (root)|APIFY_KEY_1|✗|variable ausente en este archivo
APIFY|command-center (content-studio)|APIFY_KEY_1|✗|variable ausente en este archivo
APIFY|hermes-agent|APIFY_KEY_1|✓|
APIFY|StarHome|APIFY_KEY_2|✓|
APIFY|factory-v5|APIFY_KEY_2|✗|variable ausente en este archivo
APIFY|command-center (root)|APIFY_KEY_2|✗|variable ausente en este archivo
APIFY|command-center (content-studio)|APIFY_KEY_2|✗|variable ausente en este archivo
APIFY|hermes-agent|APIFY_KEY_2|✓|
APIFY|StarHome|APIFY_KEY_3|✓|
APIFY|factory-v5|APIFY_KEY_3|✗|variable ausente en este archivo
APIFY|command-center (root)|APIFY_KEY_3|✗|variable ausente en este archivo
APIFY|command-center (content-studio)|APIFY_KEY_3|✗|variable ausente en este archivo
APIFY|hermes-agent|APIFY_KEY_3|✓|
APIFY|StarHome|APIFY_KEY_4|✓|
APIFY|factory-v5|APIFY_KEY_4|✗|variable ausente en este archivo
APIFY|command-center (root)|APIFY_KEY_4|✗|variable ausente en este archivo
APIFY|command-center (content-studio)|APIFY_KEY_4|✗|variable ausente en este archivo
APIFY|hermes-agent|APIFY_KEY_4|✓|
APIFY|StarHome|APIFY_KEY_5|✓|
APIFY|factory-v5|APIFY_KEY_5|✗|variable ausente en este archivo
APIFY|command-center (root)|APIFY_KEY_5|✗|variable ausente en este archivo
APIFY|command-center (content-studio)|APIFY_KEY_5|✗|variable ausente en este archivo
APIFY|hermes-agent|APIFY_KEY_5|✓|
APIFY|StarHome|APIFY_KEY_6|✓|
APIFY|factory-v5|APIFY_KEY_6|✗|variable ausente en este archivo
APIFY|command-center (root)|APIFY_KEY_6|✗|variable ausente en este archivo
APIFY|command-center (content-studio)|APIFY_KEY_6|✗|variable ausente en este archivo
APIFY|hermes-agent|APIFY_KEY_6|✓|
APIFY|StarHome|APIFY_KEY_7|✓|
APIFY|factory-v5|APIFY_KEY_7|✗|variable ausente en este archivo
APIFY|command-center (root)|APIFY_KEY_7|✗|variable ausente en este archivo
APIFY|command-center (content-studio)|APIFY_KEY_7|✗|variable ausente en este archivo
APIFY|hermes-agent|APIFY_KEY_7|✓|
ARCEEAI|StarHome|ARCEEAI_API_KEY|✗|variable ausente en este archivo
ARCEEAI|factory-v5|ARCEEAI_API_KEY|✗|variable ausente en este archivo
ARCEEAI|command-center (root)|ARCEEAI_API_KEY|✗|variable ausente en este archivo
ARCEEAI|command-center (content-studio)|ARCEEAI_API_KEY|✗|variable ausente en este archivo
ARCEEAI|hermes-agent|ARCEEAI_API_KEY|—|comentada / pendiente
BASEROW|StarHome|BASEROW_API_TOKEN|✓|
BASEROW|factory-v5|BASEROW_API_TOKEN|✗|variable ausente en este archivo
BASEROW|command-center (root)|BASEROW_API_TOKEN|✓|
BASEROW|command-center (content-studio)|BASEROW_API_TOKEN|✗|variable ausente en este archivo
BASEROW|hermes-agent|BASEROW_API_TOKEN|✓|
BASEROW|StarHome|BASEROW_DB_PASS|✓|
BASEROW|factory-v5|BASEROW_DB_PASS|✗|variable ausente en este archivo
BASEROW|command-center (root)|BASEROW_DB_PASS|✗|variable ausente en este archivo
BASEROW|command-center (content-studio)|BASEROW_DB_PASS|✗|variable ausente en este archivo
BASEROW|hermes-agent|BASEROW_DB_PASS|✓|
BASEROW|StarHome|BASEROW_SECRET_KEY|✓|
BASEROW|factory-v5|BASEROW_SECRET_KEY|✗|variable ausente en este archivo
BASEROW|command-center (root)|BASEROW_SECRET_KEY|✗|variable ausente en este archivo
BASEROW|command-center (content-studio)|BASEROW_SECRET_KEY|✗|variable ausente en este archivo
BASEROW|hermes-agent|BASEROW_SECRET_KEY|✓|
BROWSERBASE|StarHome|BROWSERBASE_API_KEY|✗|variable ausente en este archivo
BROWSERBASE|factory-v5|BROWSERBASE_API_KEY|✗|variable ausente en este archivo
BROWSERBASE|command-center (root)|BROWSERBASE_API_KEY|✗|variable ausente en este archivo
BROWSERBASE|command-center (content-studio)|BROWSERBASE_API_KEY|✗|variable ausente en este archivo
BROWSERBASE|hermes-agent|BROWSERBASE_API_KEY|—|comentada / pendiente
CAL|StarHome|CAL_COM_API_KEY|✓|
CAL|factory-v5|CAL_COM_API_KEY|✗|variable ausente en este archivo
CAL|command-center (root)|CAL_COM_API_KEY|✓|
CAL|command-center (content-studio)|CAL_COM_API_KEY|✗|variable ausente en este archivo
CAL|hermes-agent|CAL_COM_API_KEY|✓|
CAMOFOX|StarHome|CAMOFOX_SESSION_KEY|✗|variable ausente en este archivo
CAMOFOX|factory-v5|CAMOFOX_SESSION_KEY|✗|variable ausente en este archivo
CAMOFOX|command-center (root)|CAMOFOX_SESSION_KEY|✗|variable ausente en este archivo
CAMOFOX|command-center (content-studio)|CAMOFOX_SESSION_KEY|✗|variable ausente en este archivo
CAMOFOX|hermes-agent|CAMOFOX_SESSION_KEY|—|comentada / pendiente
CAMPAIGN|StarHome|CAMPAIGN_AUTH_TOKEN|✗|variable ausente en este archivo
CAMPAIGN|factory-v5|CAMPAIGN_AUTH_TOKEN|✗|variable ausente en este archivo
CAMPAIGN|command-center (root)|CAMPAIGN_AUTH_TOKEN|—|comentada / pendiente
CAMPAIGN|command-center (content-studio)|CAMPAIGN_AUTH_TOKEN|✗|variable ausente en este archivo
CAMPAIGN|hermes-agent|CAMPAIGN_AUTH_TOKEN|✗|variable ausente en este archivo
CHATWOOT|StarHome|CHATWOOT_AGENT_BOT_TOKEN|✓|
CHATWOOT|factory-v5|CHATWOOT_AGENT_BOT_TOKEN|✗|variable ausente en este archivo
CHATWOOT|command-center (root)|CHATWOOT_AGENT_BOT_TOKEN|✓|
CHATWOOT|command-center (content-studio)|CHATWOOT_AGENT_BOT_TOKEN|✗|variable ausente en este archivo
CHATWOOT|hermes-agent|CHATWOOT_AGENT_BOT_TOKEN|✓|
CHATWOOT|StarHome|CHATWOOT_HMAC_TOKEN|✓|
CHATWOOT|factory-v5|CHATWOOT_HMAC_TOKEN|✗|variable ausente en este archivo
CHATWOOT|command-center (root)|CHATWOOT_HMAC_TOKEN|✓|
CHATWOOT|command-center (content-studio)|CHATWOOT_HMAC_TOKEN|✗|variable ausente en este archivo
CHATWOOT|hermes-agent|CHATWOOT_HMAC_TOKEN|✓|
CHATWOOT|StarHome|CHATWOOT_TOKEN|✓|
CHATWOOT|factory-v5|CHATWOOT_TOKEN|✗|variable ausente en este archivo
CHATWOOT|command-center (root)|CHATWOOT_TOKEN|✓|
CHATWOOT|command-center (content-studio)|CHATWOOT_TOKEN|✗|variable ausente en este archivo
CHATWOOT|hermes-agent|CHATWOOT_TOKEN|✓|
CIVITAI|StarHome|CIVITAI_API_KEY|✓|
CIVITAI|factory-v5|CIVITAI_API_KEY|✗|variable ausente en este archivo
CIVITAI|command-center (root)|CIVITAI_API_KEY|✗|variable ausente en este archivo
CIVITAI|command-center (content-studio)|CIVITAI_API_KEY|✗|variable ausente en este archivo
CIVITAI|hermes-agent|CIVITAI_API_KEY|✓|
CLOUDFLARE|StarHome|CLOUDFLARE_API_KEY|✓|
CLOUDFLARE|factory-v5|CLOUDFLARE_API_KEY|✗|variable ausente en este archivo
CLOUDFLARE|command-center (root)|CLOUDFLARE_API_KEY|✗|variable ausente en este archivo
CLOUDFLARE|command-center (content-studio)|CLOUDFLARE_API_KEY|✗|variable ausente en este archivo
CLOUDFLARE|hermes-agent|CLOUDFLARE_API_KEY|✓|
CLOUDFLARE|StarHome|CLOUDFLARE_API_TOKEN|✗|variable ausente en este archivo
CLOUDFLARE|factory-v5|CLOUDFLARE_API_TOKEN|✗|variable ausente en este archivo
CLOUDFLARE|command-center (root)|CLOUDFLARE_API_TOKEN|✓|
CLOUDFLARE|command-center (content-studio)|CLOUDFLARE_API_TOKEN|✗|variable ausente en este archivo
CLOUDFLARE|hermes-agent|CLOUDFLARE_API_TOKEN|✗|variable ausente en este archivo
CLOUDFLARE|StarHome|CLOUDFLARE_AUTH_TOKEN|✓|
CLOUDFLARE|factory-v5|CLOUDFLARE_AUTH_TOKEN|✗|variable ausente en este archivo
CLOUDFLARE|command-center (root)|CLOUDFLARE_AUTH_TOKEN|✓|
CLOUDFLARE|command-center (content-studio)|CLOUDFLARE_AUTH_TOKEN|✓|
CLOUDFLARE|hermes-agent|CLOUDFLARE_AUTH_TOKEN|✓|
CLOUDFLARE|StarHome|CLOUDFLARE_TOKEN_9mw3|✓|
CLOUDFLARE|factory-v5|CLOUDFLARE_TOKEN_9mw3|✗|variable ausente en este archivo
CLOUDFLARE|command-center (root)|CLOUDFLARE_TOKEN_9mw3|✗|variable ausente en este archivo
CLOUDFLARE|command-center (content-studio)|CLOUDFLARE_TOKEN_9mw3|✗|variable ausente en este archivo
CLOUDFLARE|hermes-agent|CLOUDFLARE_TOKEN_9mw3|✓|
CLOUDFLARE|StarHome|CLOUDFLARE_TOKEN_BILLING|✓|
CLOUDFLARE|factory-v5|CLOUDFLARE_TOKEN_BILLING|✗|variable ausente en este archivo
CLOUDFLARE|command-center (root)|CLOUDFLARE_TOKEN_BILLING|✗|variable ausente en este archivo
CLOUDFLARE|command-center (content-studio)|CLOUDFLARE_TOKEN_BILLING|✗|variable ausente en este archivo
CLOUDFLARE|hermes-agent|CLOUDFLARE_TOKEN_BILLING|✓|
CLOUDFLARE|StarHome|CLOUDFLARE_TOKEN_DNS|✓|
CLOUDFLARE|factory-v5|CLOUDFLARE_TOKEN_DNS|✗|variable ausente en este archivo
CLOUDFLARE|command-center (root)|CLOUDFLARE_TOKEN_DNS|✗|variable ausente en este archivo
CLOUDFLARE|command-center (content-studio)|CLOUDFLARE_TOKEN_DNS|✗|variable ausente en este archivo
CLOUDFLARE|hermes-agent|CLOUDFLARE_TOKEN_DNS|✓|
CLOUDFLARE|StarHome|CLOUDFLARE_TOKEN_GTAV|✓|
CLOUDFLARE|factory-v5|CLOUDFLARE_TOKEN_GTAV|✗|variable ausente en este archivo
CLOUDFLARE|command-center (root)|CLOUDFLARE_TOKEN_GTAV|✗|variable ausente en este archivo
CLOUDFLARE|command-center (content-studio)|CLOUDFLARE_TOKEN_GTAV|✗|variable ausente en este archivo
CLOUDFLARE|hermes-agent|CLOUDFLARE_TOKEN_GTAV|✓|
CLOUDFLARE|StarHome|CLOUDFLARE_TOKEN_WORDPRESS|✓|
CLOUDFLARE|factory-v5|CLOUDFLARE_TOKEN_WORDPRESS|✗|variable ausente en este archivo
CLOUDFLARE|command-center (root)|CLOUDFLARE_TOKEN_WORDPRESS|✗|variable ausente en este archivo
CLOUDFLARE|command-center (content-studio)|CLOUDFLARE_TOKEN_WORDPRESS|✗|variable ausente en este archivo
CLOUDFLARE|hermes-agent|CLOUDFLARE_TOKEN_WORDPRESS|✓|
CLOUDFLARE|StarHome|CLOUDFLARE_TOKEN_WORKERS|✓|
CLOUDFLARE|factory-v5|CLOUDFLARE_TOKEN_WORKERS|✗|variable ausente en este archivo
CLOUDFLARE|command-center (root)|CLOUDFLARE_TOKEN_WORKERS|✗|variable ausente en este archivo
CLOUDFLARE|command-center (content-studio)|CLOUDFLARE_TOKEN_WORKERS|✗|variable ausente en este archivo
CLOUDFLARE|hermes-agent|CLOUDFLARE_TOKEN_WORKERS|✓|
CLOUDINARY|StarHome|CLOUDINARY_API_KEY|✓|
CLOUDINARY|factory-v5|CLOUDINARY_API_KEY|✗|variable ausente en este archivo
CLOUDINARY|command-center (root)|CLOUDINARY_API_KEY|✓|
CLOUDINARY|command-center (content-studio)|CLOUDINARY_API_KEY|✗|variable ausente en este archivo
CLOUDINARY|hermes-agent|CLOUDINARY_API_KEY|✓|
CLOUDINARY|StarHome|CLOUDINARY_API_SECRET|✓|
CLOUDINARY|factory-v5|CLOUDINARY_API_SECRET|✗|variable ausente en este archivo
CLOUDINARY|command-center (root)|CLOUDINARY_API_SECRET|✓|
CLOUDINARY|command-center (content-studio)|CLOUDINARY_API_SECRET|✗|variable ausente en este archivo
CLOUDINARY|hermes-agent|CLOUDINARY_API_SECRET|✓|
COHERE|StarHome|COHERE_API_KEY|✓|
COHERE|factory-v5|COHERE_API_KEY|✗|variable ausente en este archivo
COHERE|command-center (root)|COHERE_API_KEY|✗|variable ausente en este archivo
COHERE|command-center (content-studio)|COHERE_API_KEY|✗|variable ausente en este archivo
COHERE|hermes-agent|COHERE_API_KEY|✓|
COMFYUI|StarHome|COMFYUI_API_KEY|✓|
COMFYUI|factory-v5|COMFYUI_API_KEY|✗|variable ausente en este archivo
COMFYUI|command-center (root)|COMFYUI_API_KEY|✗|variable ausente en este archivo
COMFYUI|command-center (content-studio)|COMFYUI_API_KEY|✓|
COMFYUI|hermes-agent|COMFYUI_API_KEY|✓|
COMFYUI|StarHome|COMFYUI_API_KEY_2|✓|
COMFYUI|factory-v5|COMFYUI_API_KEY_2|✗|variable ausente en este archivo
COMFYUI|command-center (root)|COMFYUI_API_KEY_2|✗|variable ausente en este archivo
COMFYUI|command-center (content-studio)|COMFYUI_API_KEY_2|✓|
COMFYUI|hermes-agent|COMFYUI_API_KEY_2|✓|
COMFYUI|StarHome|COMFYUI_API_KEY_3|✓|
COMFYUI|factory-v5|COMFYUI_API_KEY_3|✗|variable ausente en este archivo
COMFYUI|command-center (root)|COMFYUI_API_KEY_3|✗|variable ausente en este archivo
COMFYUI|command-center (content-studio)|COMFYUI_API_KEY_3|✓|
COMFYUI|hermes-agent|COMFYUI_API_KEY_3|✓|
COMFYUI|StarHome|COMFYUI_API_KEY_4|✓|
COMFYUI|factory-v5|COMFYUI_API_KEY_4|✗|variable ausente en este archivo
COMFYUI|command-center (root)|COMFYUI_API_KEY_4|✗|variable ausente en este archivo
COMFYUI|command-center (content-studio)|COMFYUI_API_KEY_4|✓|
COMFYUI|hermes-agent|COMFYUI_API_KEY_4|✓|
COMFYUI|StarHome|COMFYUI_API_KEY_5|✓|
COMFYUI|factory-v5|COMFYUI_API_KEY_5|✗|variable ausente en este archivo
COMFYUI|command-center (root)|COMFYUI_API_KEY_5|✗|variable ausente en este archivo
COMFYUI|command-center (content-studio)|COMFYUI_API_KEY_5|✓|
COMFYUI|hermes-agent|COMFYUI_API_KEY_5|✓|
COOLIFY|StarHome|COOLIFY_HP290_TOKEN|✓|
COOLIFY|factory-v5|COOLIFY_HP290_TOKEN|✗|variable ausente en este archivo
COOLIFY|command-center (root)|COOLIFY_HP290_TOKEN|✗|variable ausente en este archivo
COOLIFY|command-center (content-studio)|COOLIFY_HP290_TOKEN|✗|variable ausente en este archivo
COOLIFY|hermes-agent|COOLIFY_HP290_TOKEN|✓|
CREATOMATE|StarHome|CREATOMATE_API_KEY|✓|
CREATOMATE|factory-v5|CREATOMATE_API_KEY|✗|variable ausente en este archivo
CREATOMATE|command-center (root)|CREATOMATE_API_KEY|✗|variable ausente en este archivo
CREATOMATE|command-center (content-studio)|CREATOMATE_API_KEY|✗|variable ausente en este archivo
CREATOMATE|hermes-agent|CREATOMATE_API_KEY|✓|
DASHSCOPE|StarHome|DASHSCOPE_API_KEY|—|presente, valor vacio
DASHSCOPE|factory-v5|DASHSCOPE_API_KEY|✗|variable ausente en este archivo
DASHSCOPE|command-center (root)|DASHSCOPE_API_KEY|✗|variable ausente en este archivo
DASHSCOPE|command-center (content-studio)|DASHSCOPE_API_KEY|✗|variable ausente en este archivo
DASHSCOPE|hermes-agent|DASHSCOPE_API_KEY|✗|variable ausente en este archivo
DEEPINFRA|StarHome|DEEPINFRA_API_KEY|✗|variable ausente en este archivo
DEEPINFRA|factory-v5|DEEPINFRA_API_KEY|✗|variable ausente en este archivo
DEEPINFRA|command-center (root)|DEEPINFRA_API_KEY|✗|variable ausente en este archivo
DEEPINFRA|command-center (content-studio)|DEEPINFRA_API_KEY|✗|variable ausente en este archivo
DEEPINFRA|hermes-agent|DEEPINFRA_API_KEY|—|comentada / pendiente
DEEPL|StarHome|DEEPL_API_KEY|✓|
DEEPL|factory-v5|DEEPL_API_KEY|✗|variable ausente en este archivo
DEEPL|command-center (root)|DEEPL_API_KEY|✗|variable ausente en este archivo
DEEPL|command-center (content-studio)|DEEPL_API_KEY|✓|
DEEPL|hermes-agent|DEEPL_API_KEY|✓|
DEEPSEEK|StarHome|DEEPSEEK_API_KEY|—|presente, valor vacio
DEEPSEEK|factory-v5|DEEPSEEK_API_KEY|✗|variable ausente en este archivo
DEEPSEEK|command-center (root)|DEEPSEEK_API_KEY|✗|variable ausente en este archivo
DEEPSEEK|command-center (content-studio)|DEEPSEEK_API_KEY|✗|variable ausente en este archivo
DEEPSEEK|hermes-agent|DEEPSEEK_API_KEY|✗|variable ausente en este archivo
EASYPANEL|StarHome|EASYPANEL_API_KEY|✓|
EASYPANEL|factory-v5|EASYPANEL_API_KEY|✗|variable ausente en este archivo
EASYPANEL|command-center (root)|EASYPANEL_API_KEY|✗|variable ausente en este archivo
EASYPANEL|command-center (content-studio)|EASYPANEL_API_KEY|✗|variable ausente en este archivo
EASYPANEL|hermes-agent|EASYPANEL_API_KEY|✓|
ELEVENLABS|StarHome|ELEVENLABS_API_KEY|✓|
ELEVENLABS|factory-v5|ELEVENLABS_API_KEY|✓|
ELEVENLABS|command-center (root)|ELEVENLABS_API_KEY|✓|
ELEVENLABS|command-center (content-studio)|ELEVENLABS_API_KEY|✓|
ELEVENLABS|hermes-agent|ELEVENLABS_API_KEY|✓|
EMAIL|StarHome|EMAIL_PASSWORD|✗|variable ausente en este archivo
EMAIL|factory-v5|EMAIL_PASSWORD|✗|variable ausente en este archivo
EMAIL|command-center (root)|EMAIL_PASSWORD|✗|variable ausente en este archivo
EMAIL|command-center (content-studio)|EMAIL_PASSWORD|✗|variable ausente en este archivo
EMAIL|hermes-agent|EMAIL_PASSWORD|—|comentada / pendiente
EVOLUTION|StarHome|EVOLUTION_API_KEY|✗|variable ausente en este archivo
EVOLUTION|factory-v5|EVOLUTION_API_KEY|✗|variable ausente en este archivo
EVOLUTION|command-center (root)|EVOLUTION_API_KEY|—|comentada / pendiente
EVOLUTION|command-center (content-studio)|EVOLUTION_API_KEY|✗|variable ausente en este archivo
EVOLUTION|hermes-agent|EVOLUTION_API_KEY|✗|variable ausente en este archivo
EVOLUTION|StarHome|EVOLUTION_API_KEY_GLOBAL|✓|
EVOLUTION|factory-v5|EVOLUTION_API_KEY_GLOBAL|✗|variable ausente en este archivo
EVOLUTION|command-center (root)|EVOLUTION_API_KEY_GLOBAL|✓|
EVOLUTION|command-center (content-studio)|EVOLUTION_API_KEY_GLOBAL|✗|variable ausente en este archivo
EVOLUTION|hermes-agent|EVOLUTION_API_KEY_GLOBAL|✓|
EVOLUTION|StarHome|EVOLUTION_LUZYA_TOKEN|✓|
EVOLUTION|factory-v5|EVOLUTION_LUZYA_TOKEN|✗|variable ausente en este archivo
EVOLUTION|command-center (root)|EVOLUTION_LUZYA_TOKEN|✓|
EVOLUTION|command-center (content-studio)|EVOLUTION_LUZYA_TOKEN|✗|variable ausente en este archivo
EVOLUTION|hermes-agent|EVOLUTION_LUZYA_TOKEN|✓|
EVOLUTION|StarHome|EVOLUTION_NISSAN_TOKEN|✓|
EVOLUTION|factory-v5|EVOLUTION_NISSAN_TOKEN|✗|variable ausente en este archivo
EVOLUTION|command-center (root)|EVOLUTION_NISSAN_TOKEN|✗|variable ausente en este archivo
EVOLUTION|command-center (content-studio)|EVOLUTION_NISSAN_TOKEN|✗|variable ausente en este archivo
EVOLUTION|hermes-agent|EVOLUTION_NISSAN_TOKEN|✓|
EVOLUTION|StarHome|EVOLUTION_S21_TOKEN|✓|
EVOLUTION|factory-v5|EVOLUTION_S21_TOKEN|✗|variable ausente en este archivo
EVOLUTION|command-center (root)|EVOLUTION_S21_TOKEN|✗|variable ausente en este archivo
EVOLUTION|command-center (content-studio)|EVOLUTION_S21_TOKEN|✗|variable ausente en este archivo
EVOLUTION|hermes-agent|EVOLUTION_S21_TOKEN|✓|
EXA|StarHome|EXA_API_KEY|✓|
EXA|factory-v5|EXA_API_KEY|✗|variable ausente en este archivo
EXA|command-center (root)|EXA_API_KEY|✗|variable ausente en este archivo
EXA|command-center (content-studio)|EXA_API_KEY|✗|variable ausente en este archivo
EXA|hermes-agent|EXA_API_KEY|✓|
FAL|StarHome|FAL_API_KEY|✗|variable ausente en este archivo
FAL|factory-v5|FAL_API_KEY|✗|variable ausente en este archivo
FAL|command-center (root)|FAL_API_KEY|✓|
FAL|command-center (content-studio)|FAL_API_KEY|✗|variable ausente en este archivo
FAL|hermes-agent|FAL_API_KEY|✗|variable ausente en este archivo
FAL|StarHome|FAL_API_KEY_2|✓|
FAL|factory-v5|FAL_API_KEY_2|✗|variable ausente en este archivo
FAL|command-center (root)|FAL_API_KEY_2|✗|variable ausente en este archivo
FAL|command-center (content-studio)|FAL_API_KEY_2|✗|variable ausente en este archivo
FAL|hermes-agent|FAL_API_KEY_2|✓|
FAL|StarHome|FAL_KEY|✓|
FAL|factory-v5|FAL_KEY|✗|variable ausente en este archivo
FAL|command-center (root)|FAL_KEY|✗|variable ausente en este archivo
FAL|command-center (content-studio)|FAL_KEY|✓|
FAL|hermes-agent|FAL_KEY|✓|
FIRECRAWL|StarHome|FIRECRAWL_API_KEY|✓|
FIRECRAWL|factory-v5|FIRECRAWL_API_KEY|✗|variable ausente en este archivo
FIRECRAWL|command-center (root)|FIRECRAWL_API_KEY|✗|variable ausente en este archivo
FIRECRAWL|command-center (content-studio)|FIRECRAWL_API_KEY|✗|variable ausente en este archivo
FIRECRAWL|hermes-agent|FIRECRAWL_API_KEY|✓|
FIREWORKS|StarHome|FIREWORKS_API_KEY|✗|variable ausente en este archivo
FIREWORKS|factory-v5|FIREWORKS_API_KEY|✗|variable ausente en este archivo
FIREWORKS|command-center (root)|FIREWORKS_API_KEY|✗|variable ausente en este archivo
FIREWORKS|command-center (content-studio)|FIREWORKS_API_KEY|✗|variable ausente en este archivo
FIREWORKS|hermes-agent|FIREWORKS_API_KEY|—|comentada / pendiente
FORMBRICKS|StarHome|FORMBRICKS_DB_PASS|✓|
FORMBRICKS|factory-v5|FORMBRICKS_DB_PASS|✗|variable ausente en este archivo
FORMBRICKS|command-center (root)|FORMBRICKS_DB_PASS|✗|variable ausente en este archivo
FORMBRICKS|command-center (content-studio)|FORMBRICKS_DB_PASS|✗|variable ausente en este archivo
FORMBRICKS|hermes-agent|FORMBRICKS_DB_PASS|✓|
FORMBRICKS|StarHome|FORMBRICKS_SECRET|✓|
FORMBRICKS|factory-v5|FORMBRICKS_SECRET|✗|variable ausente en este archivo
FORMBRICKS|command-center (root)|FORMBRICKS_SECRET|✗|variable ausente en este archivo
FORMBRICKS|command-center (content-studio)|FORMBRICKS_SECRET|✗|variable ausente en este archivo
FORMBRICKS|hermes-agent|FORMBRICKS_SECRET|✓|
GEMINI|StarHome|GEMINI_API_KEY|✓|
GEMINI|factory-v5|GEMINI_API_KEY|✗|variable ausente en este archivo
GEMINI|command-center (root)|GEMINI_API_KEY|✗|variable ausente en este archivo
GEMINI|command-center (content-studio)|GEMINI_API_KEY|✗|variable ausente en este archivo
GEMINI|hermes-agent|GEMINI_API_KEY|✓|
GITHUB|StarHome|GITHUB_APP_PRIVATE_KEY_PATH|✗|variable ausente en este archivo
GITHUB|factory-v5|GITHUB_APP_PRIVATE_KEY_PATH|✗|variable ausente en este archivo
GITHUB|command-center (root)|GITHUB_APP_PRIVATE_KEY_PATH|✗|variable ausente en este archivo
GITHUB|command-center (content-studio)|GITHUB_APP_PRIVATE_KEY_PATH|✗|variable ausente en este archivo
GITHUB|hermes-agent|GITHUB_APP_PRIVATE_KEY_PATH|—|comentada / pendiente
GITHUB|StarHome|GITHUB_TOKEN|✓|
GITHUB|factory-v5|GITHUB_TOKEN|✗|variable ausente en este archivo
GITHUB|command-center (root)|GITHUB_TOKEN|✗|variable ausente en este archivo
GITHUB|command-center (content-studio)|GITHUB_TOKEN|✗|variable ausente en este archivo
GITHUB|hermes-agent|GITHUB_TOKEN|✓|
GLM|StarHome|GLM_API_KEY|✗|variable ausente en este archivo
GLM|factory-v5|GLM_API_KEY|✗|variable ausente en este archivo
GLM|command-center (root)|GLM_API_KEY|✗|variable ausente en este archivo
GLM|command-center (content-studio)|GLM_API_KEY|✗|variable ausente en este archivo
GLM|hermes-agent|GLM_API_KEY|—|comentada / pendiente
GMAIL|StarHome|GMAIL_APP_PASS|✓|
GMAIL|factory-v5|GMAIL_APP_PASS|✗|variable ausente en este archivo
GMAIL|command-center (root)|GMAIL_APP_PASS|✓|
GMAIL|command-center (content-studio)|GMAIL_APP_PASS|✗|variable ausente en este archivo
GMAIL|hermes-agent|GMAIL_APP_PASS|✓|
GOOGLE|StarHome|GOOGLE_API_KEY|✗|variable ausente en este archivo
GOOGLE|factory-v5|GOOGLE_API_KEY|✗|variable ausente en este archivo
GOOGLE|command-center (root)|GOOGLE_API_KEY|✗|variable ausente en este archivo
GOOGLE|command-center (content-studio)|GOOGLE_API_KEY|✗|variable ausente en este archivo
GOOGLE|hermes-agent|GOOGLE_API_KEY|—|comentada / pendiente
GOOGLE|StarHome|GOOGLE_CLIENT_SECRET|✗|variable ausente en este archivo
GOOGLE|factory-v5|GOOGLE_CLIENT_SECRET|✗|variable ausente en este archivo
GOOGLE|command-center (root)|GOOGLE_CLIENT_SECRET|—|comentada / pendiente
GOOGLE|command-center (content-studio)|GOOGLE_CLIENT_SECRET|—|comentada / pendiente
GOOGLE|hermes-agent|GOOGLE_CLIENT_SECRET|✗|variable ausente en este archivo
GOOGLE|StarHome|GOOGLE_OAUTH_CREDENTIAL_NAME|✓|
GOOGLE|factory-v5|GOOGLE_OAUTH_CREDENTIAL_NAME|✗|variable ausente en este archivo
GOOGLE|command-center (root)|GOOGLE_OAUTH_CREDENTIAL_NAME|✗|variable ausente en este archivo
GOOGLE|command-center (content-studio)|GOOGLE_OAUTH_CREDENTIAL_NAME|✗|variable ausente en este archivo
GOOGLE|hermes-agent|GOOGLE_OAUTH_CREDENTIAL_NAME|✓|
GROQ|StarHome|GROQ_API_KEY|✗|variable ausente en este archivo
GROQ|factory-v5|GROQ_API_KEY|✗|variable ausente en este archivo
GROQ|command-center (root)|GROQ_API_KEY|—|presente, valor vacio
GROQ|command-center (content-studio)|GROQ_API_KEY|✗|variable ausente en este archivo
GROQ|hermes-agent|GROQ_API_KEY|—|comentada / pendiente
HEYGEN|StarHome|HEYGEN_API_KEY|✓|
HEYGEN|factory-v5|HEYGEN_API_KEY|✗|variable ausente en este archivo
HEYGEN|command-center (root)|HEYGEN_API_KEY|✓|
HEYGEN|command-center (content-studio)|HEYGEN_API_KEY|✗|variable ausente en este archivo
HEYGEN|hermes-agent|HEYGEN_API_KEY|✓|
HF|StarHome|HF_TOKEN|✓|
HF|factory-v5|HF_TOKEN|✗|variable ausente en este archivo
HF|command-center (root)|HF_TOKEN|✗|variable ausente en este archivo
HF|command-center (content-studio)|HF_TOKEN|✓|
HF|hermes-agent|HF_TOKEN|✓|
HF|StarHome|HF_TOKEN_FINEGRAINED|✓|
HF|factory-v5|HF_TOKEN_FINEGRAINED|✗|variable ausente en este archivo
HF|command-center (root)|HF_TOKEN_FINEGRAINED|✗|variable ausente en este archivo
HF|command-center (content-studio)|HF_TOKEN_FINEGRAINED|✗|variable ausente en este archivo
HF|hermes-agent|HF_TOKEN_FINEGRAINED|✓|
HIGGSFIELD|StarHome|HIGGSFIELD_API_KEY|✗|variable ausente en este archivo (esperado: cuenta Higgsfield suspendida)
HIGGSFIELD|factory-v5|HIGGSFIELD_API_KEY|—|presente, valor vacio (esperado: cuenta Higgsfield suspendida)
HIGGSFIELD|command-center (root)|HIGGSFIELD_API_KEY|—|comentada / pendiente (esperado: cuenta Higgsfield suspendida)
HIGGSFIELD|command-center (content-studio)|HIGGSFIELD_API_KEY|✗|variable ausente en este archivo (esperado: cuenta Higgsfield suspendida)
HIGGSFIELD|hermes-agent|HIGGSFIELD_API_KEY|✗|variable ausente en este archivo (esperado: cuenta Higgsfield suspendida)
HONCHO|StarHome|HONCHO_API_KEY|✗|variable ausente en este archivo
HONCHO|factory-v5|HONCHO_API_KEY|✗|variable ausente en este archivo
HONCHO|command-center (root)|HONCHO_API_KEY|✗|variable ausente en este archivo
HONCHO|command-center (content-studio)|HONCHO_API_KEY|✗|variable ausente en este archivo
HONCHO|hermes-agent|HONCHO_API_KEY|—|comentada / pendiente
HOSTINGER|StarHome|HOSTINGER_API_KEY|✓|
HOSTINGER|factory-v5|HOSTINGER_API_KEY|✗|variable ausente en este archivo
HOSTINGER|command-center (root)|HOSTINGER_API_KEY|✗|variable ausente en este archivo
HOSTINGER|command-center (content-studio)|HOSTINGER_API_KEY|✗|variable ausente en este archivo
HOSTINGER|hermes-agent|HOSTINGER_API_KEY|✓|
HUGGING|StarHome|HUGGING_FACE_HUB_TOKEN|✗|variable ausente en este archivo
HUGGING|factory-v5|HUGGING_FACE_HUB_TOKEN|✗|variable ausente en este archivo
HUGGING|command-center (root)|HUGGING_FACE_HUB_TOKEN|✗|variable ausente en este archivo
HUGGING|command-center (content-studio)|HUGGING_FACE_HUB_TOKEN|—|comentada / pendiente
HUGGING|hermes-agent|HUGGING_FACE_HUB_TOKEN|✗|variable ausente en este archivo
INSTAGRAM|StarHome|INSTAGRAM_TOKEN_CANO|✓|
INSTAGRAM|factory-v5|INSTAGRAM_TOKEN_CANO|✗|variable ausente en este archivo
INSTAGRAM|command-center (root)|INSTAGRAM_TOKEN_CANO|✗|variable ausente en este archivo
INSTAGRAM|command-center (content-studio)|INSTAGRAM_TOKEN_CANO|✗|variable ausente en este archivo
INSTAGRAM|hermes-agent|INSTAGRAM_TOKEN_CANO|✓|
KIE|StarHome|KIE_API_KEY|✓|
KIE|factory-v5|KIE_API_KEY|✓|
KIE|command-center (root)|KIE_API_KEY|✗|variable ausente en este archivo
KIE|command-center (content-studio)|KIE_API_KEY|✓|
KIE|hermes-agent|KIE_API_KEY|✓|
KIE|StarHome|KIE_API_KEY_2|✓|
KIE|factory-v5|KIE_API_KEY_2|✗|variable ausente en este archivo
KIE|command-center (root)|KIE_API_KEY_2|✗|variable ausente en este archivo
KIE|command-center (content-studio)|KIE_API_KEY_2|✗|variable ausente en este archivo
KIE|hermes-agent|KIE_API_KEY_2|✓|
KIE|StarHome|KIE_CALLBACK_SECRET|✗|variable ausente en este archivo
KIE|factory-v5|KIE_CALLBACK_SECRET|✓|
KIE|command-center (root)|KIE_CALLBACK_SECRET|✗|variable ausente en este archivo
KIE|command-center (content-studio)|KIE_CALLBACK_SECRET|✗|variable ausente en este archivo
KIE|hermes-agent|KIE_CALLBACK_SECRET|✗|variable ausente en este archivo
KIE|StarHome|KIE_WEBHOOK_HMAC_KEY|✗|variable ausente en este archivo
KIE|factory-v5|KIE_WEBHOOK_HMAC_KEY|✓|
KIE|command-center (root)|KIE_WEBHOOK_HMAC_KEY|✗|variable ausente en este archivo
KIE|command-center (content-studio)|KIE_WEBHOOK_HMAC_KEY|✗|variable ausente en este archivo
KIE|hermes-agent|KIE_WEBHOOK_HMAC_KEY|✗|variable ausente en este archivo
KIMI|StarHome|KIMI_API_KEY|✓|
KIMI|factory-v5|KIMI_API_KEY|✗|variable ausente en este archivo
KIMI|command-center (root)|KIMI_API_KEY|✓|
KIMI|command-center (content-studio)|KIMI_API_KEY|✗|variable ausente en este archivo
KIMI|hermes-agent|KIMI_API_KEY|✓|
KIMI|StarHome|KIMI_CN_API_KEY|✗|variable ausente en este archivo
KIMI|factory-v5|KIMI_CN_API_KEY|✗|variable ausente en este archivo
KIMI|command-center (root)|KIMI_CN_API_KEY|✗|variable ausente en este archivo
KIMI|command-center (content-studio)|KIMI_CN_API_KEY|✗|variable ausente en este archivo
KIMI|hermes-agent|KIMI_CN_API_KEY|—|comentada / pendiente
LISTMONK|StarHome|LISTMONK_ADMIN_PASS|✓|
LISTMONK|factory-v5|LISTMONK_ADMIN_PASS|✗|variable ausente en este archivo
LISTMONK|command-center (root)|LISTMONK_ADMIN_PASS|✓|
LISTMONK|command-center (content-studio)|LISTMONK_ADMIN_PASS|✗|variable ausente en este archivo
LISTMONK|hermes-agent|LISTMONK_ADMIN_PASS|✓|
LISTMONK|StarHome|LISTMONK_DB_PASS|✓|
LISTMONK|factory-v5|LISTMONK_DB_PASS|✗|variable ausente en este archivo
LISTMONK|command-center (root)|LISTMONK_DB_PASS|✗|variable ausente en este archivo
LISTMONK|command-center (content-studio)|LISTMONK_DB_PASS|✗|variable ausente en este archivo
LISTMONK|hermes-agent|LISTMONK_DB_PASS|✓|
MANYCHAT|StarHome|MANYCHAT_BEARER_TOKEN|✓|
MANYCHAT|factory-v5|MANYCHAT_BEARER_TOKEN|✗|variable ausente en este archivo
MANYCHAT|command-center (root)|MANYCHAT_BEARER_TOKEN|✗|variable ausente en este archivo
MANYCHAT|command-center (content-studio)|MANYCHAT_BEARER_TOKEN|✗|variable ausente en este archivo
MANYCHAT|hermes-agent|MANYCHAT_BEARER_TOKEN|✓|
MAPBOX|StarHome|MAPBOX_TOKEN|✓|
MAPBOX|factory-v5|MAPBOX_TOKEN|✗|variable ausente en este archivo
MAPBOX|command-center (root)|MAPBOX_TOKEN|✗|variable ausente en este archivo
MAPBOX|command-center (content-studio)|MAPBOX_TOKEN|✗|variable ausente en este archivo
MAPBOX|hermes-agent|MAPBOX_TOKEN|✓|
METABASE|StarHome|METABASE_DB_PASS|✓|
METABASE|factory-v5|METABASE_DB_PASS|✗|variable ausente en este archivo
METABASE|command-center (root)|METABASE_DB_PASS|✗|variable ausente en este archivo
METABASE|command-center (content-studio)|METABASE_DB_PASS|✗|variable ausente en este archivo
METABASE|hermes-agent|METABASE_DB_PASS|✓|
MINIMAX|StarHome|MINIMAX_API_KEY|✗|variable ausente en este archivo
MINIMAX|factory-v5|MINIMAX_API_KEY|✗|variable ausente en este archivo
MINIMAX|command-center (root)|MINIMAX_API_KEY|✗|variable ausente en este archivo
MINIMAX|command-center (content-studio)|MINIMAX_API_KEY|✗|variable ausente en este archivo
MINIMAX|hermes-agent|MINIMAX_API_KEY|—|comentada / pendiente
MINIMAX|StarHome|MINIMAX_CN_API_KEY|✗|variable ausente en este archivo
MINIMAX|factory-v5|MINIMAX_CN_API_KEY|✗|variable ausente en este archivo
MINIMAX|command-center (root)|MINIMAX_CN_API_KEY|✗|variable ausente en este archivo
MINIMAX|command-center (content-studio)|MINIMAX_CN_API_KEY|✗|variable ausente en este archivo
MINIMAX|hermes-agent|MINIMAX_CN_API_KEY|—|comentada / pendiente
MINIO|StarHome|MINIO_PASSWORD|✓|
MINIO|factory-v5|MINIO_PASSWORD|✗|variable ausente en este archivo
MINIO|command-center (root)|MINIO_PASSWORD|✗|variable ausente en este archivo
MINIO|command-center (content-studio)|MINIO_PASSWORD|✗|variable ausente en este archivo
MINIO|hermes-agent|MINIO_PASSWORD|✓|
MISTRAL|StarHome|MISTRAL_API_KEY|✓|
MISTRAL|factory-v5|MISTRAL_API_KEY|✗|variable ausente en este archivo
MISTRAL|command-center (root)|MISTRAL_API_KEY|✗|variable ausente en este archivo
MISTRAL|command-center (content-studio)|MISTRAL_API_KEY|✗|variable ausente en este archivo
MISTRAL|hermes-agent|MISTRAL_API_KEY|✓|
MODAL|StarHome|MODAL_PRIMARY_TOKEN_ID|✗|variable ausente en este archivo
MODAL|factory-v5|MODAL_PRIMARY_TOKEN_ID|✗|variable ausente en este archivo
MODAL|command-center (root)|MODAL_PRIMARY_TOKEN_ID|—|comentada / pendiente
MODAL|command-center (content-studio)|MODAL_PRIMARY_TOKEN_ID|✗|variable ausente en este archivo
MODAL|hermes-agent|MODAL_PRIMARY_TOKEN_ID|✗|variable ausente en este archivo
MODAL|StarHome|MODAL_TOKEN_ID|✗|variable ausente en este archivo
MODAL|factory-v5|MODAL_TOKEN_ID|✓|
MODAL|command-center (root)|MODAL_TOKEN_ID|—|comentada / pendiente
MODAL|command-center (content-studio)|MODAL_TOKEN_ID|✗|variable ausente en este archivo
MODAL|hermes-agent|MODAL_TOKEN_ID|✗|variable ausente en este archivo
MODAL|StarHome|MODAL_TOKEN_ID_2|✓|
MODAL|factory-v5|MODAL_TOKEN_ID_2|✗|variable ausente en este archivo
MODAL|command-center (root)|MODAL_TOKEN_ID_2|✗|variable ausente en este archivo
MODAL|command-center (content-studio)|MODAL_TOKEN_ID_2|✗|variable ausente en este archivo
MODAL|hermes-agent|MODAL_TOKEN_ID_2|✓|
MODAL|StarHome|MODAL_TOKEN_SECRET|✗|variable ausente en este archivo
MODAL|factory-v5|MODAL_TOKEN_SECRET|✓|
MODAL|command-center (root)|MODAL_TOKEN_SECRET|✗|variable ausente en este archivo
MODAL|command-center (content-studio)|MODAL_TOKEN_SECRET|✗|variable ausente en este archivo
MODAL|hermes-agent|MODAL_TOKEN_SECRET|✗|variable ausente en este archivo
MODAL|StarHome|MODAL_TOKEN_SECRET_2|✓|
MODAL|factory-v5|MODAL_TOKEN_SECRET_2|✗|variable ausente en este archivo
MODAL|command-center (root)|MODAL_TOKEN_SECRET_2|✗|variable ausente en este archivo
MODAL|command-center (content-studio)|MODAL_TOKEN_SECRET_2|✗|variable ausente en este archivo
MODAL|hermes-agent|MODAL_TOKEN_SECRET_2|✓|
MOONSHOT|StarHome|MOONSHOT_API_KEY|✓|
MOONSHOT|factory-v5|MOONSHOT_API_KEY|✗|variable ausente en este archivo
MOONSHOT|command-center (root)|MOONSHOT_API_KEY|✗|variable ausente en este archivo
MOONSHOT|command-center (content-studio)|MOONSHOT_API_KEY|✗|variable ausente en este archivo
MOONSHOT|hermes-agent|MOONSHOT_API_KEY|✓|
N8N|StarHome|N8N_API_KEY|✓|
N8N|factory-v5|N8N_API_KEY|✗|variable ausente en este archivo
N8N|command-center (root)|N8N_API_KEY|✗|variable ausente en este archivo
N8N|command-center (content-studio)|N8N_API_KEY|✗|variable ausente en este archivo
N8N|hermes-agent|N8N_API_KEY|✓|
N8N|StarHome|N8N_MCP_TOKEN|✓|
N8N|factory-v5|N8N_MCP_TOKEN|✗|variable ausente en este archivo
N8N|command-center (root)|N8N_MCP_TOKEN|✗|variable ausente en este archivo
N8N|command-center (content-studio)|N8N_MCP_TOKEN|✗|variable ausente en este archivo
N8N|hermes-agent|N8N_MCP_TOKEN|✓|
NEXT|StarHome|NEXT_PUBLIC_MAPBOX_TOKEN|✓|
NEXT|factory-v5|NEXT_PUBLIC_MAPBOX_TOKEN|✗|variable ausente en este archivo
NEXT|command-center (root)|NEXT_PUBLIC_MAPBOX_TOKEN|✗|variable ausente en este archivo
NEXT|command-center (content-studio)|NEXT_PUBLIC_MAPBOX_TOKEN|✗|variable ausente en este archivo
NEXT|hermes-agent|NEXT_PUBLIC_MAPBOX_TOKEN|✓|
NOTION|StarHome|NOTION_API_KEY|✗|variable ausente en este archivo
NOTION|factory-v5|NOTION_API_KEY|✗|variable ausente en este archivo
NOTION|command-center (root)|NOTION_API_KEY|—|comentada / pendiente
NOTION|command-center (content-studio)|NOTION_API_KEY|✗|variable ausente en este archivo
NOTION|hermes-agent|NOTION_API_KEY|✗|variable ausente en este archivo
NOTION|StarHome|NOTION_TOKEN|✓|
NOTION|factory-v5|NOTION_TOKEN|✗|variable ausente en este archivo
NOTION|command-center (root)|NOTION_TOKEN|✓|
NOTION|command-center (content-studio)|NOTION_TOKEN|✗|variable ausente en este archivo
NOTION|hermes-agent|NOTION_TOKEN|✓|
NOVITA|StarHome|NOVITA_API_KEY|✗|variable ausente en este archivo
NOVITA|factory-v5|NOVITA_API_KEY|✗|variable ausente en este archivo
NOVITA|command-center (root)|NOVITA_API_KEY|✗|variable ausente en este archivo
NOVITA|command-center (content-studio)|NOVITA_API_KEY|✗|variable ausente en este archivo
NOVITA|hermes-agent|NOVITA_API_KEY|—|comentada / pendiente
NVIDIA|StarHome|NVIDIA_API_KEY|✗|variable ausente en este archivo (esperado: llave NVIDIA rechaza inferencia 403, ver memoria)
NVIDIA|factory-v5|NVIDIA_API_KEY|✗|variable ausente en este archivo (esperado: llave NVIDIA rechaza inferencia 403, ver memoria)
NVIDIA|command-center (root)|NVIDIA_API_KEY|✗|variable ausente en este archivo (esperado: llave NVIDIA rechaza inferencia 403, ver memoria)
NVIDIA|command-center (content-studio)|NVIDIA_API_KEY|✗|variable ausente en este archivo (esperado: llave NVIDIA rechaza inferencia 403, ver memoria)
NVIDIA|hermes-agent|NVIDIA_API_KEY|✓|
NVIDIA|StarHome|NVIDIA_NIM_API_KEY|✓|
NVIDIA|factory-v5|NVIDIA_NIM_API_KEY|✗|variable ausente en este archivo (esperado: llave NVIDIA rechaza inferencia 403, ver memoria)
NVIDIA|command-center (root)|NVIDIA_NIM_API_KEY|✓|
NVIDIA|command-center (content-studio)|NVIDIA_NIM_API_KEY|✗|variable ausente en este archivo (esperado: llave NVIDIA rechaza inferencia 403, ver memoria)
NVIDIA|hermes-agent|NVIDIA_NIM_API_KEY|✓|
OLLAMA|StarHome|OLLAMA_API_KEY|✗|variable ausente en este archivo
OLLAMA|factory-v5|OLLAMA_API_KEY|✗|variable ausente en este archivo
OLLAMA|command-center (root)|OLLAMA_API_KEY|✗|variable ausente en este archivo
OLLAMA|command-center (content-studio)|OLLAMA_API_KEY|✗|variable ausente en este archivo
OLLAMA|hermes-agent|OLLAMA_API_KEY|—|comentada / pendiente
OPENAI|StarHome|OPENAI_API_KEY|✓|
OPENAI|factory-v5|OPENAI_API_KEY|✗|variable ausente en este archivo
OPENAI|command-center (root)|OPENAI_API_KEY|✓|
OPENAI|command-center (content-studio)|OPENAI_API_KEY|✗|variable ausente en este archivo
OPENAI|hermes-agent|OPENAI_API_KEY|✓|
OPENCODE|StarHome|OPENCODE_GO_API_KEY|✗|variable ausente en este archivo
OPENCODE|factory-v5|OPENCODE_GO_API_KEY|✗|variable ausente en este archivo
OPENCODE|command-center (root)|OPENCODE_GO_API_KEY|✗|variable ausente en este archivo
OPENCODE|command-center (content-studio)|OPENCODE_GO_API_KEY|✗|variable ausente en este archivo
OPENCODE|hermes-agent|OPENCODE_GO_API_KEY|—|comentada / pendiente
OPENCODE|StarHome|OPENCODE_ZEN_API_KEY|✗|variable ausente en este archivo
OPENCODE|factory-v5|OPENCODE_ZEN_API_KEY|✗|variable ausente en este archivo
OPENCODE|command-center (root)|OPENCODE_ZEN_API_KEY|✗|variable ausente en este archivo
OPENCODE|command-center (content-studio)|OPENCODE_ZEN_API_KEY|✗|variable ausente en este archivo
OPENCODE|hermes-agent|OPENCODE_ZEN_API_KEY|—|comentada / pendiente
OPENROUTER|StarHome|OPENROUTER_API_KEY|✓|
OPENROUTER|factory-v5|OPENROUTER_API_KEY|✗|variable ausente en este archivo
OPENROUTER|command-center (root)|OPENROUTER_API_KEY|✗|variable ausente en este archivo
OPENROUTER|command-center (content-studio)|OPENROUTER_API_KEY|✗|variable ausente en este archivo
OPENROUTER|hermes-agent|OPENROUTER_API_KEY|✓|
PARALLEL|StarHome|PARALLEL_API_KEY|✗|variable ausente en este archivo
PARALLEL|factory-v5|PARALLEL_API_KEY|✗|variable ausente en este archivo
PARALLEL|command-center (root)|PARALLEL_API_KEY|✗|variable ausente en este archivo
PARALLEL|command-center (content-studio)|PARALLEL_API_KEY|✗|variable ausente en este archivo
PARALLEL|hermes-agent|PARALLEL_API_KEY|—|comentada / pendiente
PERPLEXITY|StarHome|PERPLEXITY_API_KEY|✓|
PERPLEXITY|factory-v5|PERPLEXITY_API_KEY|✗|variable ausente en este archivo
PERPLEXITY|command-center (root)|PERPLEXITY_API_KEY|✓|
PERPLEXITY|command-center (content-studio)|PERPLEXITY_API_KEY|✓|
PERPLEXITY|hermes-agent|PERPLEXITY_API_KEY|✓|
PERPLEXITY|StarHome|PERPLEXITY_API_KEY_2|✓|
PERPLEXITY|factory-v5|PERPLEXITY_API_KEY_2|✗|variable ausente en este archivo
PERPLEXITY|command-center (root)|PERPLEXITY_API_KEY_2|✗|variable ausente en este archivo
PERPLEXITY|command-center (content-studio)|PERPLEXITY_API_KEY_2|✗|variable ausente en este archivo
PERPLEXITY|hermes-agent|PERPLEXITY_API_KEY_2|✓|
PEXELS|StarHome|PEXELS_API_KEY|✓|
PEXELS|factory-v5|PEXELS_API_KEY|✓|
PEXELS|command-center (root)|PEXELS_API_KEY|✓|
PEXELS|command-center (content-studio)|PEXELS_API_KEY|✓|
PEXELS|hermes-agent|PEXELS_API_KEY|✓|
PIXABAY|StarHome|PIXABAY_API_KEY|✓|
PIXABAY|factory-v5|PIXABAY_API_KEY|✓|
PIXABAY|command-center (root)|PIXABAY_API_KEY|✓|
PIXABAY|command-center (content-studio)|PIXABAY_API_KEY|✓|
PIXABAY|hermes-agent|PIXABAY_API_KEY|✓|
PLAUSIBLE|StarHome|PLAUSIBLE_DB_PASS|✓|
PLAUSIBLE|factory-v5|PLAUSIBLE_DB_PASS|✗|variable ausente en este archivo
PLAUSIBLE|command-center (root)|PLAUSIBLE_DB_PASS|✗|variable ausente en este archivo
PLAUSIBLE|command-center (content-studio)|PLAUSIBLE_DB_PASS|✗|variable ausente en este archivo
PLAUSIBLE|hermes-agent|PLAUSIBLE_DB_PASS|✓|
PLAUSIBLE|StarHome|PLAUSIBLE_SECRET_KEY|✓|
PLAUSIBLE|factory-v5|PLAUSIBLE_SECRET_KEY|✗|variable ausente en este archivo
PLAUSIBLE|command-center (root)|PLAUSIBLE_SECRET_KEY|✗|variable ausente en este archivo
PLAUSIBLE|command-center (content-studio)|PLAUSIBLE_SECRET_KEY|✗|variable ausente en este archivo
PLAUSIBLE|hermes-agent|PLAUSIBLE_SECRET_KEY|✓|
PLAUSIBLE|StarHome|PLAUSIBLE_SECRET_KEY_BASE|✓|
PLAUSIBLE|factory-v5|PLAUSIBLE_SECRET_KEY_BASE|✗|variable ausente en este archivo
PLAUSIBLE|command-center (root)|PLAUSIBLE_SECRET_KEY_BASE|✗|variable ausente en este archivo
PLAUSIBLE|command-center (content-studio)|PLAUSIBLE_SECRET_KEY_BASE|✗|variable ausente en este archivo
PLAUSIBLE|hermes-agent|PLAUSIBLE_SECRET_KEY_BASE|✓|
RAPIDAPI|StarHome|RAPIDAPI_KEY|✗|variable ausente en este archivo
RAPIDAPI|factory-v5|RAPIDAPI_KEY|✗|variable ausente en este archivo
RAPIDAPI|command-center (root)|RAPIDAPI_KEY|—|comentada / pendiente
RAPIDAPI|command-center (content-studio)|RAPIDAPI_KEY|✗|variable ausente en este archivo
RAPIDAPI|hermes-agent|RAPIDAPI_KEY|✗|variable ausente en este archivo
RECALL|StarHome|RECALL_API_KEY|✗|variable ausente en este archivo
RECALL|factory-v5|RECALL_API_KEY|✗|variable ausente en este archivo
RECALL|command-center (root)|RECALL_API_KEY|—|presente, valor vacio
RECALL|command-center (content-studio)|RECALL_API_KEY|✗|variable ausente en este archivo
RECALL|hermes-agent|RECALL_API_KEY|✗|variable ausente en este archivo
RECALL|StarHome|RECALL_WEBHOOK_SECRET|✓|
RECALL|factory-v5|RECALL_WEBHOOK_SECRET|✗|variable ausente en este archivo
RECALL|command-center (root)|RECALL_WEBHOOK_SECRET|✓|
RECALL|command-center (content-studio)|RECALL_WEBHOOK_SECRET|✗|variable ausente en este archivo
RECALL|hermes-agent|RECALL_WEBHOOK_SECRET|✓|
REDIS|StarHome|REDIS_AGENTS_PASSWORD|✓|
REDIS|factory-v5|REDIS_AGENTS_PASSWORD|✗|variable ausente en este archivo
REDIS|command-center (root)|REDIS_AGENTS_PASSWORD|✗|variable ausente en este archivo
REDIS|command-center (content-studio)|REDIS_AGENTS_PASSWORD|✗|variable ausente en este archivo
REDIS|hermes-agent|REDIS_AGENTS_PASSWORD|✓|
REDIS|StarHome|REDIS_PASSWORD|✓|
REDIS|factory-v5|REDIS_PASSWORD|✗|variable ausente en este archivo
REDIS|command-center (root)|REDIS_PASSWORD|✗|variable ausente en este archivo
REDIS|command-center (content-studio)|REDIS_PASSWORD|✗|variable ausente en este archivo
REDIS|hermes-agent|REDIS_PASSWORD|✓|
REPLICATE|StarHome|REPLICATE_API_TOKEN|✓|
REPLICATE|factory-v5|REPLICATE_API_TOKEN|✗|variable ausente en este archivo
REPLICATE|command-center (root)|REPLICATE_API_TOKEN|✗|variable ausente en este archivo
REPLICATE|command-center (content-studio)|REPLICATE_API_TOKEN|✗|variable ausente en este archivo
REPLICATE|hermes-agent|REPLICATE_API_TOKEN|✓|
RETELL|StarHome|RETELL_API_KEY|✓|
RETELL|factory-v5|RETELL_API_KEY|✗|variable ausente en este archivo
RETELL|command-center (root)|RETELL_API_KEY|✓|
RETELL|command-center (content-studio)|RETELL_API_KEY|✗|variable ausente en este archivo
RETELL|hermes-agent|RETELL_API_KEY|✓|
SCRAPECREATORS|StarHome|SCRAPECREATORS_API_KEY|✓|
SCRAPECREATORS|factory-v5|SCRAPECREATORS_API_KEY|✗|variable ausente en este archivo
SCRAPECREATORS|command-center (root)|SCRAPECREATORS_API_KEY|✗|variable ausente en este archivo
SCRAPECREATORS|command-center (content-studio)|SCRAPECREATORS_API_KEY|✗|variable ausente en este archivo
SCRAPECREATORS|hermes-agent|SCRAPECREATORS_API_KEY|✓|
SECRET|StarHome|SECRET_KEY|✗|variable ausente en este archivo
SECRET|factory-v5|SECRET_KEY|✓|
SECRET|command-center (root)|SECRET_KEY|✗|variable ausente en este archivo
SECRET|command-center (content-studio)|SECRET_KEY|✗|variable ausente en este archivo
SECRET|hermes-agent|SECRET_KEY|✗|variable ausente en este archivo
SLACK|StarHome|SLACK_APP_TOKEN|✗|variable ausente en este archivo
SLACK|factory-v5|SLACK_APP_TOKEN|✗|variable ausente en este archivo
SLACK|command-center (root)|SLACK_APP_TOKEN|✗|variable ausente en este archivo
SLACK|command-center (content-studio)|SLACK_APP_TOKEN|✗|variable ausente en este archivo
SLACK|hermes-agent|SLACK_APP_TOKEN|—|comentada / pendiente
SLACK|StarHome|SLACK_BOT_TOKEN|✗|variable ausente en este archivo
SLACK|factory-v5|SLACK_BOT_TOKEN|✗|variable ausente en este archivo
SLACK|command-center (root)|SLACK_BOT_TOKEN|✗|variable ausente en este archivo
SLACK|command-center (content-studio)|SLACK_BOT_TOKEN|✗|variable ausente en este archivo
SLACK|hermes-agent|SLACK_BOT_TOKEN|—|comentada / pendiente
STRIPE|StarHome|STRIPE_PUBLISHABLE_KEY|✓|
STRIPE|factory-v5|STRIPE_PUBLISHABLE_KEY|✗|variable ausente en este archivo
STRIPE|command-center (root)|STRIPE_PUBLISHABLE_KEY|✗|variable ausente en este archivo
STRIPE|command-center (content-studio)|STRIPE_PUBLISHABLE_KEY|✗|variable ausente en este archivo
STRIPE|hermes-agent|STRIPE_PUBLISHABLE_KEY|✓|
STRIPE|StarHome|STRIPE_PUBLISHABLE_KEY_LIVE|✓|
STRIPE|factory-v5|STRIPE_PUBLISHABLE_KEY_LIVE|✗|variable ausente en este archivo
STRIPE|command-center (root)|STRIPE_PUBLISHABLE_KEY_LIVE|✗|variable ausente en este archivo
STRIPE|command-center (content-studio)|STRIPE_PUBLISHABLE_KEY_LIVE|✗|variable ausente en este archivo
STRIPE|hermes-agent|STRIPE_PUBLISHABLE_KEY_LIVE|✓|
STRIPE|StarHome|STRIPE_SECRET_KEY|✓|
STRIPE|factory-v5|STRIPE_SECRET_KEY|✗|variable ausente en este archivo
STRIPE|command-center (root)|STRIPE_SECRET_KEY|✓|
STRIPE|command-center (content-studio)|STRIPE_SECRET_KEY|✗|variable ausente en este archivo
STRIPE|hermes-agent|STRIPE_SECRET_KEY|✓|
STRIPE|StarHome|STRIPE_SECRET_KEY_LIVE|✓|
STRIPE|factory-v5|STRIPE_SECRET_KEY_LIVE|✗|variable ausente en este archivo
STRIPE|command-center (root)|STRIPE_SECRET_KEY_LIVE|✗|variable ausente en este archivo
STRIPE|command-center (content-studio)|STRIPE_SECRET_KEY_LIVE|✗|variable ausente en este archivo
STRIPE|hermes-agent|STRIPE_SECRET_KEY_LIVE|✓|
STRIPE|StarHome|STRIPE_WEBHOOK_SECRET|✗|variable ausente en este archivo
STRIPE|factory-v5|STRIPE_WEBHOOK_SECRET|✗|variable ausente en este archivo
STRIPE|command-center (root)|STRIPE_WEBHOOK_SECRET|—|comentada / pendiente
STRIPE|command-center (content-studio)|STRIPE_WEBHOOK_SECRET|✗|variable ausente en este archivo
STRIPE|hermes-agent|STRIPE_WEBHOOK_SECRET|✗|variable ausente en este archivo
SUDO|StarHome|SUDO_PASSWORD|✗|variable ausente en este archivo
SUDO|factory-v5|SUDO_PASSWORD|✗|variable ausente en este archivo
SUDO|command-center (root)|SUDO_PASSWORD|✗|variable ausente en este archivo
SUDO|command-center (content-studio)|SUDO_PASSWORD|✗|variable ausente en este archivo
SUDO|hermes-agent|SUDO_PASSWORD|—|comentada / pendiente
SUNO|StarHome|SUNO_API_KEY|✓|
SUNO|factory-v5|SUNO_API_KEY|✗|variable ausente en este archivo
SUNO|command-center (root)|SUNO_API_KEY|✗|variable ausente en este archivo
SUNO|command-center (content-studio)|SUNO_API_KEY|✗|variable ausente en este archivo
SUNO|hermes-agent|SUNO_API_KEY|✓|
SUPABASE|StarHome|SUPABASE_KEY|✗|variable ausente en este archivo
SUPABASE|factory-v5|SUPABASE_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (root)|SUPABASE_KEY|—|presente, valor vacio
SUPABASE|command-center (content-studio)|SUPABASE_KEY|✗|variable ausente en este archivo
SUPABASE|hermes-agent|SUPABASE_KEY|✗|variable ausente en este archivo
SUPABASE|StarHome|SUPABASE_NISSAN_KEY|✓|
SUPABASE|factory-v5|SUPABASE_NISSAN_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (root)|SUPABASE_NISSAN_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (content-studio)|SUPABASE_NISSAN_KEY|✗|variable ausente en este archivo
SUPABASE|hermes-agent|SUPABASE_NISSAN_KEY|✓|
SUPABASE|StarHome|SUPABASE_ORION_ANON_KEY|✓|
SUPABASE|factory-v5|SUPABASE_ORION_ANON_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (root)|SUPABASE_ORION_ANON_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (content-studio)|SUPABASE_ORION_ANON_KEY|✗|variable ausente en este archivo
SUPABASE|hermes-agent|SUPABASE_ORION_ANON_KEY|✓|
SUPABASE|StarHome|SUPABASE_ORION_KEY|✗|variable ausente en este archivo
SUPABASE|factory-v5|SUPABASE_ORION_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (root)|SUPABASE_ORION_KEY|—|comentada / pendiente
SUPABASE|command-center (content-studio)|SUPABASE_ORION_KEY|✗|variable ausente en este archivo
SUPABASE|hermes-agent|SUPABASE_ORION_KEY|✗|variable ausente en este archivo
SUPABASE|StarHome|SUPABASE_ORION_SERVICE_KEY|✓|
SUPABASE|factory-v5|SUPABASE_ORION_SERVICE_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (root)|SUPABASE_ORION_SERVICE_KEY|✓|
SUPABASE|command-center (content-studio)|SUPABASE_ORION_SERVICE_KEY|✗|variable ausente en este archivo
SUPABASE|hermes-agent|SUPABASE_ORION_SERVICE_KEY|✓|
SUPABASE|StarHome|SUPABASE_SERVICE_KEY|✗|variable ausente en este archivo
SUPABASE|factory-v5|SUPABASE_SERVICE_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (root)|SUPABASE_SERVICE_KEY|—|comentada / pendiente
SUPABASE|command-center (content-studio)|SUPABASE_SERVICE_KEY|✗|variable ausente en este archivo
SUPABASE|hermes-agent|SUPABASE_SERVICE_KEY|✗|variable ausente en este archivo
SUPABASE|StarHome|SUPABASE_WORLDVIBE_SERVICE_KEY|✓|
SUPABASE|factory-v5|SUPABASE_WORLDVIBE_SERVICE_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (root)|SUPABASE_WORLDVIBE_SERVICE_KEY|✗|variable ausente en este archivo
SUPABASE|command-center (content-studio)|SUPABASE_WORLDVIBE_SERVICE_KEY|✗|variable ausente en este archivo
SUPABASE|hermes-agent|SUPABASE_WORLDVIBE_SERVICE_KEY|✓|
SUPADATA|StarHome|SUPADATA_API_KEY|✗|variable ausente en este archivo
SUPADATA|factory-v5|SUPADATA_API_KEY|✗|variable ausente en este archivo
SUPADATA|command-center (root)|SUPADATA_API_KEY|—|comentada / pendiente
SUPADATA|command-center (content-studio)|SUPADATA_API_KEY|✗|variable ausente en este archivo
SUPADATA|hermes-agent|SUPADATA_API_KEY|✗|variable ausente en este archivo
TEAMS|StarHome|TEAMS_CLIENT_SECRET|✗|variable ausente en este archivo
TEAMS|factory-v5|TEAMS_CLIENT_SECRET|✗|variable ausente en este archivo
TEAMS|command-center (root)|TEAMS_CLIENT_SECRET|✗|variable ausente en este archivo
TEAMS|command-center (content-studio)|TEAMS_CLIENT_SECRET|✗|variable ausente en este archivo
TEAMS|hermes-agent|TEAMS_CLIENT_SECRET|—|comentada / pendiente
TELEGRAM|StarHome|TELEGRAM_BOT_TOKEN|✓|
TELEGRAM|factory-v5|TELEGRAM_BOT_TOKEN|✗|variable ausente en este archivo
TELEGRAM|command-center (root)|TELEGRAM_BOT_TOKEN|✓|
TELEGRAM|command-center (content-studio)|TELEGRAM_BOT_TOKEN|✓|
TELEGRAM|hermes-agent|TELEGRAM_BOT_TOKEN|✓|
TELEGRAM|StarHome|TELEGRAM_BOT_TOKEN_PHOTOREEL|✓|
TELEGRAM|factory-v5|TELEGRAM_BOT_TOKEN_PHOTOREEL|✗|variable ausente en este archivo
TELEGRAM|command-center (root)|TELEGRAM_BOT_TOKEN_PHOTOREEL|✗|variable ausente en este archivo
TELEGRAM|command-center (content-studio)|TELEGRAM_BOT_TOKEN_PHOTOREEL|✗|variable ausente en este archivo
TELEGRAM|hermes-agent|TELEGRAM_BOT_TOKEN_PHOTOREEL|✓|
TELEGRAM|StarHome|TELEGRAM_JURIDICO_TOKEN|✗|variable ausente en este archivo
TELEGRAM|factory-v5|TELEGRAM_JURIDICO_TOKEN|✗|variable ausente en este archivo
TELEGRAM|command-center (root)|TELEGRAM_JURIDICO_TOKEN|—|comentada / pendiente
TELEGRAM|command-center (content-studio)|TELEGRAM_JURIDICO_TOKEN|✗|variable ausente en este archivo
TELEGRAM|hermes-agent|TELEGRAM_JURIDICO_TOKEN|✗|variable ausente en este archivo
TELEGRAM|StarHome|TELEGRAM_TOKEN_ALERTS|✗|variable ausente en este archivo
TELEGRAM|factory-v5|TELEGRAM_TOKEN_ALERTS|✗|variable ausente en este archivo
TELEGRAM|command-center (root)|TELEGRAM_TOKEN_ALERTS|—|comentada / pendiente
TELEGRAM|command-center (content-studio)|TELEGRAM_TOKEN_ALERTS|✗|variable ausente en este archivo
TELEGRAM|hermes-agent|TELEGRAM_TOKEN_ALERTS|✗|variable ausente en este archivo
TELEGRAM|StarHome|TELEGRAM_WEBHOOK_SECRET|✗|variable ausente en este archivo
TELEGRAM|factory-v5|TELEGRAM_WEBHOOK_SECRET|✗|variable ausente en este archivo
TELEGRAM|command-center (root)|TELEGRAM_WEBHOOK_SECRET|✗|variable ausente en este archivo
TELEGRAM|command-center (content-studio)|TELEGRAM_WEBHOOK_SECRET|✗|variable ausente en este archivo
TELEGRAM|hermes-agent|TELEGRAM_WEBHOOK_SECRET|—|comentada / pendiente
TERMINAL|StarHome|TERMINAL_SSH_KEY|✗|variable ausente en este archivo
TERMINAL|factory-v5|TERMINAL_SSH_KEY|✗|variable ausente en este archivo
TERMINAL|command-center (root)|TERMINAL_SSH_KEY|✗|variable ausente en este archivo
TERMINAL|command-center (content-studio)|TERMINAL_SSH_KEY|✗|variable ausente en este archivo
TERMINAL|hermes-agent|TERMINAL_SSH_KEY|—|comentada / pendiente
THENEWSAPI|StarHome|THENEWSAPI_KEY|✓|
THENEWSAPI|factory-v5|THENEWSAPI_KEY|✗|variable ausente en este archivo
THENEWSAPI|command-center (root)|THENEWSAPI_KEY|✗|variable ausente en este archivo
THENEWSAPI|command-center (content-studio)|THENEWSAPI_KEY|✓|
THENEWSAPI|hermes-agent|THENEWSAPI_KEY|✓|
THENEWSAPI|StarHome|THENEWSAPI_TOKEN|✗|variable ausente en este archivo
THENEWSAPI|factory-v5|THENEWSAPI_TOKEN|✗|variable ausente en este archivo
THENEWSAPI|command-center (root)|THENEWSAPI_TOKEN|✗|variable ausente en este archivo
THENEWSAPI|command-center (content-studio)|THENEWSAPI_TOKEN|✓|
THENEWSAPI|hermes-agent|THENEWSAPI_TOKEN|✗|variable ausente en este archivo
TOKEN|StarHome|TOKEN_ENCRYPTION_KEY|✗|variable ausente en este archivo
TOKEN|factory-v5|TOKEN_ENCRYPTION_KEY|✓|
TOKEN|command-center (root)|TOKEN_ENCRYPTION_KEY|✗|variable ausente en este archivo
TOKEN|command-center (content-studio)|TOKEN_ENCRYPTION_KEY|✗|variable ausente en este archivo
TOKEN|hermes-agent|TOKEN_ENCRYPTION_KEY|✗|variable ausente en este archivo
TWILIO|StarHome|TWILIO_API_KEY_SECRET|✓|
TWILIO|factory-v5|TWILIO_API_KEY_SECRET|✗|variable ausente en este archivo
TWILIO|command-center (root)|TWILIO_API_KEY_SECRET|✗|variable ausente en este archivo
TWILIO|command-center (content-studio)|TWILIO_API_KEY_SECRET|✗|variable ausente en este archivo
TWILIO|hermes-agent|TWILIO_API_KEY_SECRET|✓|
TWILIO|StarHome|TWILIO_API_KEY_SID|✓|
TWILIO|factory-v5|TWILIO_API_KEY_SID|✗|variable ausente en este archivo
TWILIO|command-center (root)|TWILIO_API_KEY_SID|✗|variable ausente en este archivo
TWILIO|command-center (content-studio)|TWILIO_API_KEY_SID|✗|variable ausente en este archivo
TWILIO|hermes-agent|TWILIO_API_KEY_SID|✓|
TWILIO|StarHome|TWILIO_AUTH_TOKEN|✓|
TWILIO|factory-v5|TWILIO_AUTH_TOKEN|✗|variable ausente en este archivo
TWILIO|command-center (root)|TWILIO_AUTH_TOKEN|✓|
TWILIO|command-center (content-studio)|TWILIO_AUTH_TOKEN|✗|variable ausente en este archivo
TWILIO|hermes-agent|TWILIO_AUTH_TOKEN|✓|
TWILIO|StarHome|TWILIO_TEST_AUTH_TOKEN|✓|
TWILIO|factory-v5|TWILIO_TEST_AUTH_TOKEN|✗|variable ausente en este archivo
TWILIO|command-center (root)|TWILIO_TEST_AUTH_TOKEN|✗|variable ausente en este archivo
TWILIO|command-center (content-studio)|TWILIO_TEST_AUTH_TOKEN|✗|variable ausente en este archivo
TWILIO|hermes-agent|TWILIO_TEST_AUTH_TOKEN|✓|
UPLOAD|StarHome|UPLOAD_POST_API_KEY|✗|variable ausente en este archivo
UPLOAD|factory-v5|UPLOAD_POST_API_KEY|✓|
UPLOAD|command-center (root)|UPLOAD_POST_API_KEY|—|comentada / pendiente
UPLOAD|command-center (content-studio)|UPLOAD_POST_API_KEY|✗|variable ausente en este archivo
UPLOAD|hermes-agent|UPLOAD_POST_API_KEY|✗|variable ausente en este archivo
UPLOADPOST|StarHome|UPLOADPOST_API_KEY|✓|
UPLOADPOST|factory-v5|UPLOADPOST_API_KEY|✗|variable ausente en este archivo
UPLOADPOST|command-center (root)|UPLOADPOST_API_KEY|✓|
UPLOADPOST|command-center (content-studio)|UPLOADPOST_API_KEY|✓|
UPLOADPOST|hermes-agent|UPLOADPOST_API_KEY|✓|
UPLOADPOST|StarHome|UPLOADPOST_TOKEN_2|✓|
UPLOADPOST|factory-v5|UPLOADPOST_TOKEN_2|✗|variable ausente en este archivo
UPLOADPOST|command-center (root)|UPLOADPOST_TOKEN_2|✗|variable ausente en este archivo
UPLOADPOST|command-center (content-studio)|UPLOADPOST_TOKEN_2|✗|variable ausente en este archivo
UPLOADPOST|hermes-agent|UPLOADPOST_TOKEN_2|✓|
UPSTAGE|StarHome|UPSTAGE_API_KEY|✗|variable ausente en este archivo
UPSTAGE|factory-v5|UPSTAGE_API_KEY|✗|variable ausente en este archivo
UPSTAGE|command-center (root)|UPSTAGE_API_KEY|✗|variable ausente en este archivo
UPSTAGE|command-center (content-studio)|UPSTAGE_API_KEY|✗|variable ausente en este archivo
UPSTAGE|hermes-agent|UPSTAGE_API_KEY|—|comentada / pendiente
UPSTASH|StarHome|UPSTASH_API_KEY|✓|
UPSTASH|factory-v5|UPSTASH_API_KEY|✗|variable ausente en este archivo
UPSTASH|command-center (root)|UPSTASH_API_KEY|✗|variable ausente en este archivo
UPSTASH|command-center (content-studio)|UPSTASH_API_KEY|✗|variable ausente en este archivo
UPSTASH|hermes-agent|UPSTASH_API_KEY|✓|
UPSTASH|StarHome|UPSTASH_REDIS_REST_TOKEN|✓|
UPSTASH|factory-v5|UPSTASH_REDIS_REST_TOKEN|✗|variable ausente en este archivo
UPSTASH|command-center (root)|UPSTASH_REDIS_REST_TOKEN|✓|
UPSTASH|command-center (content-studio)|UPSTASH_REDIS_REST_TOKEN|✗|variable ausente en este archivo
UPSTASH|hermes-agent|UPSTASH_REDIS_REST_TOKEN|✓|
VIDEODB|StarHome|VIDEODB_API_KEY|✓|
VIDEODB|factory-v5|VIDEODB_API_KEY|✗|variable ausente en este archivo
VIDEODB|command-center (root)|VIDEODB_API_KEY|✗|variable ausente en este archivo
VIDEODB|command-center (content-studio)|VIDEODB_API_KEY|✗|variable ausente en este archivo
VIDEODB|hermes-agent|VIDEODB_API_KEY|✓|
VOICE|StarHome|VOICE_TOOLS_OPENAI_KEY|✗|variable ausente en este archivo
VOICE|factory-v5|VOICE_TOOLS_OPENAI_KEY|✗|variable ausente en este archivo
VOICE|command-center (root)|VOICE_TOOLS_OPENAI_KEY|✗|variable ausente en este archivo
VOICE|command-center (content-studio)|VOICE_TOOLS_OPENAI_KEY|✗|variable ausente en este archivo
VOICE|hermes-agent|VOICE_TOOLS_OPENAI_KEY|—|comentada / pendiente
VPS1|StarHome|VPS1_EASYPANEL_KEY|✓|
VPS1|factory-v5|VPS1_EASYPANEL_KEY|✗|variable ausente en este archivo
VPS1|command-center (root)|VPS1_EASYPANEL_KEY|✗|variable ausente en este archivo
VPS1|command-center (content-studio)|VPS1_EASYPANEL_KEY|✗|variable ausente en este archivo
VPS1|hermes-agent|VPS1_EASYPANEL_KEY|✓|
VPS1|StarHome|VPS1_SSH_PASS|✓|
VPS1|factory-v5|VPS1_SSH_PASS|✗|variable ausente en este archivo
VPS1|command-center (root)|VPS1_SSH_PASS|✗|variable ausente en este archivo
VPS1|command-center (content-studio)|VPS1_SSH_PASS|✗|variable ausente en este archivo
VPS1|hermes-agent|VPS1_SSH_PASS|✓|
VPS2|StarHome|VPS2_PASS|✗|variable ausente en este archivo
VPS2|factory-v5|VPS2_PASS|✗|variable ausente en este archivo
VPS2|command-center (root)|VPS2_PASS|—|comentada / pendiente
VPS2|command-center (content-studio)|VPS2_PASS|✗|variable ausente en este archivo
VPS2|hermes-agent|VPS2_PASS|✗|variable ausente en este archivo
VPS2|StarHome|VPS2_SSH_PASS|✓|
VPS2|factory-v5|VPS2_SSH_PASS|✗|variable ausente en este archivo
VPS2|command-center (root)|VPS2_SSH_PASS|✓|
VPS2|command-center (content-studio)|VPS2_SSH_PASS|✗|variable ausente en este archivo
VPS2|hermes-agent|VPS2_SSH_PASS|✓|
WEBHOOK|StarHome|WEBHOOK_HMAC_SECRET|✓|
WEBHOOK|factory-v5|WEBHOOK_HMAC_SECRET|✗|variable ausente en este archivo
WEBHOOK|command-center (root)|WEBHOOK_HMAC_SECRET|✓|
WEBHOOK|command-center (content-studio)|WEBHOOK_HMAC_SECRET|✗|variable ausente en este archivo
WEBHOOK|hermes-agent|WEBHOOK_HMAC_SECRET|✓|
XAI|StarHome|XAI_API_KEY|✓|
XAI|factory-v5|XAI_API_KEY|✗|variable ausente en este archivo
XAI|command-center (root)|XAI_API_KEY|✗|variable ausente en este archivo
XAI|command-center (content-studio)|XAI_API_KEY|✓|
XAI|hermes-agent|XAI_API_KEY|✓|
XIAOMI|StarHome|XIAOMI_API_KEY|✗|variable ausente en este archivo
XIAOMI|factory-v5|XIAOMI_API_KEY|✗|variable ausente en este archivo
XIAOMI|command-center (root)|XIAOMI_API_KEY|✗|variable ausente en este archivo
XIAOMI|command-center (content-studio)|XIAOMI_API_KEY|✗|variable ausente en este archivo
XIAOMI|hermes-agent|XIAOMI_API_KEY|—|comentada / pendiente
YOUTUBE|StarHome|YOUTUBE_CLIENT_SECRET|✗|variable ausente en este archivo
YOUTUBE|factory-v5|YOUTUBE_CLIENT_SECRET|—|presente, valor vacio
YOUTUBE|command-center (root)|YOUTUBE_CLIENT_SECRET|✗|variable ausente en este archivo
YOUTUBE|command-center (content-studio)|YOUTUBE_CLIENT_SECRET|✗|variable ausente en este archivo
YOUTUBE|hermes-agent|YOUTUBE_CLIENT_SECRET|✗|variable ausente en este archivo
YOUTUBE|StarHome|YOUTUBE_CLIENT_SECRET_ANIMALS|✓|
YOUTUBE|factory-v5|YOUTUBE_CLIENT_SECRET_ANIMALS|✗|variable ausente en este archivo
YOUTUBE|command-center (root)|YOUTUBE_CLIENT_SECRET_ANIMALS|✗|variable ausente en este archivo
YOUTUBE|command-center (content-studio)|YOUTUBE_CLIENT_SECRET_ANIMALS|✓|
YOUTUBE|hermes-agent|YOUTUBE_CLIENT_SECRET_ANIMALS|✓|
YOUTUBE|StarHome|YOUTUBE_CLIENT_SECRET_CANO|✓|
YOUTUBE|factory-v5|YOUTUBE_CLIENT_SECRET_CANO|✗|variable ausente en este archivo
YOUTUBE|command-center (root)|YOUTUBE_CLIENT_SECRET_CANO|✗|variable ausente en este archivo
YOUTUBE|command-center (content-studio)|YOUTUBE_CLIENT_SECRET_CANO|✓|
YOUTUBE|hermes-agent|YOUTUBE_CLIENT_SECRET_CANO|✓|
YOUTUBE|StarHome|YOUTUBE_CLIENT_SECRET_MOTIVE|✓|
YOUTUBE|factory-v5|YOUTUBE_CLIENT_SECRET_MOTIVE|✗|variable ausente en este archivo
YOUTUBE|command-center (root)|YOUTUBE_CLIENT_SECRET_MOTIVE|✗|variable ausente en este archivo
YOUTUBE|command-center (content-studio)|YOUTUBE_CLIENT_SECRET_MOTIVE|✓|
YOUTUBE|hermes-agent|YOUTUBE_CLIENT_SECRET_MOTIVE|✓|

## Validacion de red — Apify

- Vault usado: `/home/cano/.secrets/credenciales/credenciales/.env`
- Llave probada: `APIFY_API_KEY` (valor nunca impreso)
- Endpoint: `GET https://api.apify.com/v2/users/me?token=<key>` (gratuito, no consume creditos)
- Resultado: **✓** — perfil de usuario obtenido (200)

Presencia de candidatas en el vault (sin valores):

variable|estado
---|---
APIFY_API_KEY|✓
APIFY_KEY_1|✓
APIFY_KEY_2|✓
APIFY_KEY_3|✓
APIFY_KEY_4|✓
APIFY_KEY_5|✓
APIFY_KEY_6|✓
APIFY_KEY_7|✓

## Validacion de red — RapidAPI

- Variable: `RAPIDAPI_KEY`
- Resultado: **✗** — no encontrada en vault bajo ningun nombre (confirmado en F1); sin intento de red

## Resumen — totales por sistema

sistema|✓|✗|—
---|---|---|---
StarHome|119|58|3
factory-v5|12|166|2
command-center (root)|33|126|21
command-center (content-studio)|22|155|3
hermes-agent|120|32|28

**Total general**: ✓ 306  ✗ 537  — 57

