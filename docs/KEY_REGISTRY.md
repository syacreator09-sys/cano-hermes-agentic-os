# Registro de llaves (`config/key_registry.yaml`)

Generado por `scripts/build_key_registry.py` a partir de los NOMBRES del vault (`~/.secrets/credenciales/credenciales/.env`). Ningún valor de llave aparece en este documento.

Vault: 283 líneas `NOMBRE=`, 273 nombres únicos (10 declarados dos veces por la fusión USB).

## StarHome / Hermes (15)

| nombre | proveedor | uso | riesgo | rotación pendiente |
|---|---|---|---|---|
| `BASEROW_ACCOUNTING_TOKEN` | Baserow Accounting | token de Baserow Accounting; consumida en cano-hermes-agentic-os/cano_hermes/finance/accounting.py:92 | medio | no |
| `BASEROW_CONTENT_TOKEN` | Baserow Content | token de Baserow Content; consumida en cano-hermes-agentic-os/cano_hermes/content/dedup.py:96 | medio | no |
| `ELEVENLABS_API_KEY` | Elevenlabs | clave de API de Elevenlabs; consumida en hermes-agent/.agents/skills/media-use/audio/scripts/lib/tts.mjs:28 (+10 más) | medio | no |
| `FFMPEG_PATH` | Ffmpeg | ruta de archivo de Ffmpeg; consumida en hermes-agent/plugins/platforms/discord/ffmpeg_utils.py:28 | bajo | no |
| `GEMINI_API_KEY` | Gemini | clave de API de Gemini; consumida en hermes-agent/.agents/skills/media-use/audio/scripts/lib/bgm.mjs:21 (+3 más) | medio | no |
| `GITHUB_TOKEN` | Github | token de Github; consumida en hermes-agent/optional-skills/devops/watchers/scripts/watch_github.py:118 (+5 más) | medio | sí |
| `GOOGLE_API_KEY` | Google | clave de API de Google; consumida en hermes-agent/.agents/skills/media-use/audio/scripts/lib/bgm.mjs:21 (+3 más) | medio | no |
| `GROQ_API_KEY` | GROQ | clave de API de GROQ; consumida en hermes-agent/scripts/discord-voice-doctor.py:221 | medio | no |
| `HEYGEN_API_KEY` | Heygen | clave de API de Heygen; consumida en hermes-agent/.agents/skills/media-use/audio/scripts/lib/heygen.mjs:50 (+6 más) | medio | sí |
| `MISTRAL_API_KEY` | Mistral | clave de API de Mistral; consumida en hermes-agent/scripts/discord-voice-doctor.py:255 (+1 más) | medio | sí |
| `OPENAI_API_KEY` | Openai | clave de API de Openai; consumida en cano-investment-intelligence/.upstreams/finrobot/finrobot_equity/core/src/modules/enhanced_text_generator.py:60 (+15 más) | medio | no |
| `OPENROUTER_API_KEY` | Openrouter | clave de API de Openrouter; consumida en cano-investment-intelligence/.upstreams/openbb_agents/99-advanced-examples/portfolio-commentary-with-search-feature/portfolio_commentary/main.py:230 (+24 más) | medio | no |
| `TELEGRAM_BOT_TOKEN` | Telegram BOT | token de Telegram BOT; consumida en hermes-agent/tests/hermes_cli/test_env_loader.py:311 | medio | no |
| `TWILIO_PHONE_NUMBER` | Twilio Phone Number | variable de configuración de Twilio Phone Number; consumida en hermes-agent/plugins/platforms/sms/adapter.py:470 (+1 más) | bajo | no |
| `XAI_API_KEY` | XAI | clave de API de XAI; consumida en hermes-agent/hermes_cli/tools_config.py:196 (+4 más) -- validacion en vivo movida a policy-skip 2026-08-07: GET /v1/models devuelve 403 permission-denied porque el team no tiene creditos/spending limit configurado, no por llave invalida; resolverlo implica facturar, fuera de alcance por politica de cero gasto. | medio | no |

## Otro proyecto (210)

| nombre | proveedor | uso | riesgo | rotación pendiente |
|---|---|---|---|---|
| `ADMIN_SECRET` | Admin | secreto de Admin -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `AISTUDIOS_API_KEY` | Aistudios | clave de API de Aistudios -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `AISTUDIOS_API_URL` | Aistudios | URL de API de Aistudios -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `AISTUDIOS_EMAIL` | Aistudios | email de Aistudios -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `ANDROID_FARM_PATH` | Android FARM | ruta de archivo de Android FARM -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `ANYMAIL_API_KEY` | Anymail | clave de API de Anymail -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `ANYTHINGLLM_API_KEY` | Anythingllm | clave de API de Anythingllm -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `ANYTHINGLLM_API_URL` | Anythingllm | URL de API de Anythingllm -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `APIFY_API_KEY` | Apify | clave de API de Apify -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `APIFY_KEY_1` | Apify | clave de Apify -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `APIFY_KEY_2` | Apify | clave de Apify -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `APIFY_KEY_3` | Apify | clave de Apify -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `APIFY_KEY_4` | Apify | clave de Apify -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `APIFY_KEY_5` | Apify | clave de Apify -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `APIFY_KEY_6` | Apify | clave de Apify -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `APIFY_KEY_7` | Apify | clave de Apify -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `API_BACKUP_EMAIL` | API Backup | email de API Backup -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `API_USERS` | API Users | variable de configuración de API Users -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `BASEROW_API_TOKEN` | Baserow | token de API de Baserow -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `BASEROW_API_URL` | Baserow | URL de API de Baserow -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `BASEROW_DB_PASS` | Baserow DB | contraseña de Baserow DB -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `BASEROW_MCP_URL` | Baserow MCP | URL de Baserow MCP -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `BASEROW_SECRET_KEY` | Baserow | clave secreta de Baserow -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `BASEROW_TOKEN` | Baserow | token de Baserow -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CAL_COM_API_KEY` | CAL COM | clave de API de CAL COM -- sin consumidor detectado, revisar con Cano | medio | no |
| `CAL_COM_EVENT_LUZYA_CHATBOT` | CAL COM Event Luzya Chatbot | variable de configuración de CAL COM Event Luzya Chatbot -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CAL_COM_EVENT_STRATEGIC` | CAL COM Event Strategic | variable de configuración de CAL COM Event Strategic -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CAL_COM_EVENT_TYPE_ID` | CAL COM Event TYPE | identificador de CAL COM Event TYPE -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CAL_COM_EVENT_TYPE_ID_ALT` | CAL COM Event TYPE ID ALT | variable de configuración de CAL COM Event TYPE ID ALT -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CAL_COM_URL_STRATEGIC` | CAL COM URL Strategic | variable de configuración de CAL COM URL Strategic -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CAL_COM_USERNAME` | CAL COM | usuario de CAL COM -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CAL_EVENT_TYPE_ID_CANO` | CAL Event TYPE ID CANO | variable de configuración de CAL Event TYPE ID CANO -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CF_ACCOUNT_ID` | CF Account | identificador de CF Account -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `CF_AI_TOKEN` | CF AI | token de CF AI -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CIVITAI_API_KEY` | Civitai | clave de API de Civitai -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account | identificador de Cloudflare Account -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `CLOUDFLARE_API_KEY` | Cloudflare | clave de API de Cloudflare -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CLOUDFLARE_AUTH_TOKEN` | Cloudflare AUTH | token de Cloudflare AUTH -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CLOUDFLARE_EMAIL` | Cloudflare | email de Cloudflare -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `CLOUDFLARE_TOKEN_BILLING` | Cloudflare Token Billing | variable de configuración de Cloudflare Token Billing -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CLOUDFLARE_TOKEN_DNS` | Cloudflare Token DNS | variable de configuración de Cloudflare Token DNS -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CLOUDFLARE_TOKEN_GTAV` | Cloudflare Token GTAV | variable de configuración de Cloudflare Token GTAV -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CLOUDFLARE_TOKEN_WORDPRESS` | Cloudflare Token Wordpress | variable de configuración de Cloudflare Token Wordpress -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CLOUDFLARE_TOKEN_WORKERS` | Cloudflare Token Workers | variable de configuración de Cloudflare Token Workers -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CLOUDINARY_API_KEY` | Cloudinary | clave de API de Cloudinary -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | sí |
| `CLOUDINARY_API_SECRET` | Cloudinary | secreto de API de Cloudinary -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | sí |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary Cloud NAME | variable de configuración de Cloudinary Cloud NAME -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | sí |
| `COHERE_API_KEY` | Cohere | clave de API de Cohere -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `COMFYUI_API_KEY` | Comfyui | clave de API de Comfyui -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `COMFYUI_API_KEY_2` | Comfyui | clave de API de Comfyui -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `COMFYUI_API_KEY_3` | Comfyui | clave de API de Comfyui -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `COMFYUI_API_KEY_4` | Comfyui | clave de API de Comfyui -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `COMFYUI_API_KEY_5` | Comfyui | clave de API de Comfyui -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `COOLIFY_HP290_TOKEN` | Coolify Hp290 | token de Coolify Hp290 -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CORS_ALLOW_ORIGINS` | CORS Allow Origins | variable de configuración de CORS Allow Origins -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `CORS_ORIGINS` | CORS Origins | variable de configuración de CORS Origins -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `CREATOMATE_API_KEY` | Creatomate | clave de API de Creatomate -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `CRON_SECRET` | CRON | secreto de CRON -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `DEEPL_API_KEY` | Deepl | clave de API de Deepl -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `EASYPANEL_API_KEY` | Easypanel | clave de API de Easypanel -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `EASYPANEL_URL` | Easypanel | URL de Easypanel -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `ELEVENLABS_API_KEY_2` | Elevenlabs | clave de API de Elevenlabs -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `ELEVENLABS_MODEL` | Elevenlabs | modelo de Elevenlabs -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `ELEVENLABS_VOICE_ID` | Elevenlabs Voice | identificador de Elevenlabs Voice -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `ELEVENLABS_VOICE_ID_ALFONSO` | Elevenlabs Voice ID Alfonso | variable de configuración de Elevenlabs Voice ID Alfonso -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `ENVIA_API_TOKEN` | Envia | token de API de Envia -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `ENVIRONMENT` | Environment | variable de configuración de Environment -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `EVOLUTION_API_KEY_GLOBAL` | Evolution API KEY Global | variable de configuración de Evolution API KEY Global -- sin consumidor detectado, revisar con Cano | medio | no |
| `EVOLUTION_API_URL` | Evolution | URL de API de Evolution -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EVOLUTION_BASE_URL` | Evolution BASE | URL de Evolution BASE -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EVOLUTION_INSTANCE_CANO` | Evolution Instance CANO | variable de configuración de Evolution Instance CANO -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EVOLUTION_LUZYA_INSTANCE` | Evolution Luzya Instance | variable de configuración de Evolution Luzya Instance -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EVOLUTION_LUZYA_NUMBER` | Evolution Luzya Number | variable de configuración de Evolution Luzya Number -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EVOLUTION_LUZYA_TOKEN` | Evolution Luzya | token de Evolution Luzya -- sin consumidor detectado, revisar con Cano | medio | no |
| `EVOLUTION_NISSAN_INSTANCE` | Evolution Nissan Instance | variable de configuración de Evolution Nissan Instance -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EVOLUTION_NISSAN_NUMBER` | Evolution Nissan Number | variable de configuración de Evolution Nissan Number -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EVOLUTION_NISSAN_TOKEN` | Evolution Nissan | token de Evolution Nissan -- sin consumidor detectado, revisar con Cano | medio | no |
| `EVOLUTION_S21_INSTANCE` | Evolution S21 Instance | variable de configuración de Evolution S21 Instance -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EVOLUTION_S21_NUMBER` | Evolution S21 Number | variable de configuración de Evolution S21 Number -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EVOLUTION_S21_TOKEN` | Evolution S21 | token de Evolution S21 -- sin consumidor detectado, revisar con Cano | medio | no |
| `EVOLUTION_WEBHOOK_URL` | Evolution Webhook | URL de Evolution Webhook -- sin consumidor detectado, revisar con Cano | bajo | no |
| `EXA_API_KEY` | EXA | clave de API de EXA -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `F5_TTS_REF_AUDIO_PATH` | F5 TTS REF Audio | ruta de archivo de F5 TTS REF Audio -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `FAL_API_KEY_2` | FAL | clave de API de FAL -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `FAL_KEY` | FAL | clave de FAL -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `FIRECRAWL_API_KEY` | Firecrawl | clave de API de Firecrawl -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `GBRAIN_DATABASE_URL` | Gbrain Database | URL de Gbrain Database -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `GITHUB_REPO` | Github REPO | variable de configuración de Github REPO -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `GITHUB_USER` | Github | usuario de Github -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `GMAIL_APP_PASS` | Gmail APP | contraseña de Gmail APP -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `GMAIL_EMAIL` | Gmail | email de Gmail -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `GOOGLE_DRIVE_FOLDER_RAG` | Google Drive Folder RAG | variable de configuración de Google Drive Folder RAG -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `GOOGLE_OAUTH_CREDENTIAL_NAME` | Google Oauth Credential NAME | variable de configuración de Google Oauth Credential NAME -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `HEYGEN_N8N_CRED_ID` | Heygen N8N CRED | identificador de Heygen N8N CRED -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `HF_TOKEN` | HF | token de HF -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `HF_TOKEN_FINEGRAINED` | HF Token Finegrained | variable de configuración de HF Token Finegrained -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `HOSTINGER_API_KEY` | Hostinger | clave de API de Hostinger -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `INSTAGRAM_TOKEN_CANO` | Instagram Token CANO | variable de configuración de Instagram Token CANO -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `JAMENDO_CLIENT_ID` | Jamendo Client | identificador de Jamendo Client -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `KIE_API_KEY` | KIE | clave de API de KIE -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `KIE_API_KEY_2` | KIE | clave de API de KIE -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `KIMI_API_KEY` | KIMI | clave de API de KIMI -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | sí |
| `KIMI_BASE_URL` | KIMI BASE | URL de KIMI BASE -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `LEAD_SCORE_MODEL_PATH` | LEAD Score Model | ruta de archivo de LEAD Score Model -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `LEGACY_ROOT` | Legacy ROOT | variable de configuración de Legacy ROOT -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `MANYCHAT_BEARER_TOKEN` | Manychat Bearer | token de Manychat Bearer -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `MAPBOX_TOKEN` | Mapbox | token de Mapbox -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `MODAL_CHATWOOT_URL` | Modal Chatwoot | URL de Modal Chatwoot -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `MODAL_EMBED_URL` | Modal Embed | URL de Modal Embed -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `MODAL_LLM_RAG_URL` | Modal LLM RAG | URL de Modal LLM RAG -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `MODAL_LLM_VOICE_URL` | Modal LLM Voice | URL de Modal LLM Voice -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `MODAL_ORCHESTRATOR_URL` | Modal Orchestrator | URL de Modal Orchestrator -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `MODAL_TOKEN_ID_2` | Modal Token | identificador de Modal Token -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `MODAL_TOKEN_SECRET_2` | Modal Token | secreto de Modal Token -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `MODAL_TRANSCRIPTION_URL` | Modal Transcription | URL de Modal Transcription -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `MODAL_VOICE_EVENTS_URL` | Modal Voice Events | URL de Modal Voice Events -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `MOONSHOT_API_KEY` | Moonshot | clave de API de Moonshot; consumida en cano-investment-intelligence/.upstreams/ai_hedge_fund/hedge_fund/llm/client.py:181 | medio | no |
| `MUSICGEN_MODEL` | Musicgen | modelo de Musicgen -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `N8N_API_KEY` | N8N | clave de API de N8N -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `N8N_HOST` | N8N HOST | variable de configuración de N8N HOST -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `N8N_MCP_TOKEN` | N8N MCP | token de N8N MCP -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `N8N_WEBHOOK_URL` | N8N Webhook | URL de N8N Webhook -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `NEXT_PUBLIC_API_URL` | NEXT Public | URL de API de NEXT Public -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | NEXT Public Mapbox | token de NEXT Public Mapbox -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `NOTION_CLIENTS_DB_ID` | Notion Clients DB | identificador de Notion Clients DB -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `NOTION_LEADS_DB_ID` | Notion Leads DB | identificador de Notion Leads DB -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `NOTION_PAGE_ID` | Notion PAGE | identificador de Notion PAGE -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `NOTION_RESULTS_DB_ID` | Notion Results DB | identificador de Notion Results DB -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `NOTION_TOKEN` | Notion | token de Notion -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `NOTION_WORKSPACE` | Notion Workspace | variable de configuración de Notion Workspace -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `NVIDIA_NIM_API_KEY` | Nvidia NIM | clave de API de Nvidia NIM -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | sí |
| `OUTPUT_BASE_PATH` | Output BASE | ruta de archivo de Output BASE -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `OUTPUT_DIR` | Output | directorio de Output -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `PDFCO_API_KEY` | Pdfco | clave de API de Pdfco -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `PERPLEXITY_API_KEY` | Perplexity | clave de API de Perplexity -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `PERPLEXITY_API_KEY_2` | Perplexity | clave de API de Perplexity -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `PEXELS_API_KEY` | Pexels | clave de API de Pexels -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `PIPER_VOICE` | Piper Voice | variable de configuración de Piper Voice -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `PIPER_VOICES_DIR` | Piper Voices | directorio de Piper Voices -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `PIXABAY_API_KEY` | Pixabay | clave de API de Pixabay -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `PROJECT_NAME` | Project NAME | variable de configuración de Project NAME -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `RAPIDAPI_KEY` | Rapidapi | clave de Rapidapi -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `RECALL_API_KEY` | Recall | clave de API de Recall -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `RECALL_WEBHOOK_SECRET` | Recall Webhook | secreto de Recall Webhook -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `REDIS_AGENTS_PASSWORD` | Redis Agents | contraseña de Redis Agents -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `REDIS_PASSWORD` | Redis | contraseña de Redis -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `REDIS_URL` | Redis | URL de Redis -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `REPLICATE_API_TOKEN` | Replicate | token de API de Replicate -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `RETELL_AGENT_ID_CANO` | Retell Agent ID CANO | variable de configuración de Retell Agent ID CANO -- sin consumidor detectado, revisar con Cano | bajo | no |
| `RETELL_AGENT_JURIDICO` | Retell Agent Juridico | variable de configuración de Retell Agent Juridico -- sin consumidor detectado, revisar con Cano | bajo | no |
| `RETELL_AGENT_LUZYA` | Retell Agent Luzya | variable de configuración de Retell Agent Luzya -- sin consumidor detectado, revisar con Cano | bajo | no |
| `RETELL_API_KEY` | Retell | clave de API de Retell -- sin consumidor detectado, revisar con Cano | medio | no |
| `RETELL_LLM_JURIDICO` | Retell LLM Juridico | variable de configuración de Retell LLM Juridico -- sin consumidor detectado, revisar con Cano | bajo | no |
| `RETELL_PHONE_JURIDICO` | Retell Phone Juridico | variable de configuración de Retell Phone Juridico -- sin consumidor detectado, revisar con Cano | bajo | no |
| `SCRAPECREATORS_API_KEY` | Scrapecreators | clave de API de Scrapecreators -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `SD_MODEL_PATH` | SD Model | ruta de archivo de SD Model -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `SENTIMENT_MODEL` | Sentiment | modelo de Sentiment -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `SHOPIFY_SHOP_URL` | Shopify SHOP | URL de Shopify SHOP -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `SHOPIFY_STORE` | Shopify Store | variable de configuración de Shopify Store -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `SKYDROPX_API_KEY` | Skydropx | clave de API de Skydropx -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `SKYDROPX_API_SECRET` | Skydropx | secreto de API de Skydropx -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `STRIPE_MVP_PRICE_ID` | Stripe MVP Price | identificador de Stripe MVP Price -- sin consumidor detectado, revisar con Cano | bajo | no |
| `STRIPE_PUBLISHABLE_KEY` | Stripe | clave pública de Stripe -- sin consumidor detectado, revisar con Cano | medio | no |
| `STRIPE_PUBLISHABLE_KEY_LIVE` | Stripe Publishable KEY LIVE | variable de configuración de Stripe Publishable KEY LIVE -- sin consumidor detectado, revisar con Cano | medio | no |
| `STRIPE_SECRET_KEY` | Stripe | clave secreta de Stripe -- sin consumidor detectado, revisar con Cano | alto | no |
| `STRIPE_SECRET_KEY_LIVE` | Stripe Secret KEY LIVE | variable de configuración de Stripe Secret KEY LIVE -- sin consumidor detectado, revisar con Cano | alto | no |
| `STRIPE_VIP_PRICE_ID` | Stripe VIP Price | identificador de Stripe VIP Price -- sin consumidor detectado, revisar con Cano | bajo | no |
| `SUNO_API_KEY` | SUNO | clave de API de SUNO -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `SUPABASE_DB_DIRECT_URL` | Supabase DB Direct | URL de Supabase DB Direct -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `SUPABASE_NISSAN_KEY` | Supabase Nissan | clave de Supabase Nissan -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `SUPABASE_NISSAN_URL` | Supabase Nissan | URL de Supabase Nissan -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `SUPABASE_ORION_ANON_KEY` | Supabase Orion ANON | clave de Supabase Orion ANON -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `SUPABASE_ORION_SERVICE_KEY` | Supabase Orion Service | clave de Supabase Orion Service -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `SUPABASE_ORION_TUNNEL_URL` | Supabase Orion Tunnel | URL de Supabase Orion Tunnel -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `SUPABASE_ORION_URL` | Supabase Orion | URL de Supabase Orion -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `SUPABASE_PAT` | Supabase PAT | variable de configuración de Supabase PAT -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `SUPABASE_WORLDVIBE_SERVICE_KEY` | Supabase Worldvibe Service | clave de Supabase Worldvibe Service -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `SUPABASE_WORLDVIBE_URL` | Supabase Worldvibe | URL de Supabase Worldvibe -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `TELEGRAM_BOT_TOKEN_PHOTOREEL` | Telegram BOT Token Photoreel | variable de configuración de Telegram BOT Token Photoreel -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `TELEGRAM_CHAT_ID` | Telegram CHAT | identificador de Telegram CHAT -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `TENANT_DEFAULT` | Tenant Default | variable de configuración de Tenant Default -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `TENANT_SCHEMA_PREFIX` | Tenant Schema Prefix | variable de configuración de Tenant Schema Prefix -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `THENEWSAPI_KEY` | Thenewsapi | clave de Thenewsapi -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `THENEWSAPI_TOKEN` | Thenewsapi | token de Thenewsapi -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `TIMEZONE` | Timezone | variable de configuración de Timezone -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `TTS_PROVIDER` | TTS Provider | variable de configuración de TTS Provider -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | variable de configuración de Twilio Account SID -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `TWILIO_API_KEY_SECRET` | Twilio API KEY | secreto de Twilio API KEY -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `TWILIO_API_KEY_SID` | Twilio API KEY SID | variable de configuración de Twilio API KEY SID -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `TWILIO_AUTH_TOKEN` | Twilio AUTH | token de Twilio AUTH -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `TWILIO_NUMBER_CANO` | Twilio Number CANO | variable de configuración de Twilio Number CANO -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `TWILIO_TEST_ACCOUNT_SID` | Twilio TEST Account SID | variable de configuración de Twilio TEST Account SID -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `TWILIO_TEST_AUTH_TOKEN` | Twilio TEST AUTH | token de Twilio TEST AUTH -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `UPLOADPOST_API_KEY` | Uploadpost | clave de API de Uploadpost -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `UPLOADPOST_TOKEN_2` | Uploadpost | token de Uploadpost -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `UPSTASH_API_KEY` | Upstash | clave de API de Upstash -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST | token de Upstash Redis REST -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST | URL de Upstash Redis REST -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `VIDEODB_API_KEY` | Videodb | clave de API de Videodb -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | medio | no |
| `VPS_DOMAIN` | VPS Domain | variable de configuración de VPS Domain -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `WEBHOOK_HMAC_SECRET` | Webhook HMAC | secreto de Webhook HMAC -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `WHATSAPP_PHONE_NUMBER` | Whatsapp Phone Number | variable de configuración de Whatsapp Phone Number -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `YOUTUBE_CLIENT_ID_ANIMALS` | Youtube Client ID Animals | variable de configuración de Youtube Client ID Animals -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `YOUTUBE_CLIENT_ID_CANO` | Youtube Client ID CANO | variable de configuración de Youtube Client ID CANO -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `YOUTUBE_CLIENT_ID_CASS` | Youtube Client ID CASS | variable de configuración de Youtube Client ID CASS -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `YOUTUBE_CLIENT_ID_MOTIVE` | Youtube Client ID Motive | variable de configuración de Youtube Client ID Motive -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | bajo | no |
| `YOUTUBE_CLIENT_SECRET_ANIMALS` | Youtube Client Secret Animals | variable de configuración de Youtube Client Secret Animals -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `YOUTUBE_CLIENT_SECRET_CANO` | Youtube Client Secret CANO | variable de configuración de Youtube Client Secret CANO -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `YOUTUBE_CLIENT_SECRET_CASS` | Youtube Client Secret CASS | variable de configuración de Youtube Client Secret CASS -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |
| `YOUTUBE_CLIENT_SECRET_MOTIVE` | Youtube Client Secret Motive | variable de configuración de Youtube Client Secret Motive -- sin consumidor detectado ni patrón reconocido, sin clasificar, revisar con Cano | alto | no |

## Infraestructura VPS (autohospedada) (48)

| nombre | proveedor | uso | riesgo | rotación pendiente |
|---|---|---|---|---|
| `BOOKSTACK_TOKEN_ID` | Bookstack Token | identificador de Bookstack Token -- sin consumidor detectado, revisar con Cano | medio | no |
| `BOOKSTACK_TOKEN_SECRET` | Bookstack Token | secreto de Bookstack Token -- sin consumidor detectado, revisar con Cano | alto | no |
| `BOOKSTACK_URL` | Bookstack | URL de Bookstack -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CHATWOOT_ACCOUNT_ID` | Chatwoot Account | identificador de Chatwoot Account -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CHATWOOT_AGENT_BOT_ID` | Chatwoot Agent BOT | identificador de Chatwoot Agent BOT -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CHATWOOT_AGENT_BOT_TOKEN` | Chatwoot Agent BOT | token de Chatwoot Agent BOT -- sin consumidor detectado, revisar con Cano | medio | no |
| `CHATWOOT_HMAC_TOKEN` | Chatwoot HMAC | token de Chatwoot HMAC -- sin consumidor detectado, revisar con Cano | medio | no |
| `CHATWOOT_INBOX_FACEBOOK` | Chatwoot Inbox Facebook | variable de configuración de Chatwoot Inbox Facebook -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CHATWOOT_INBOX_IG_CANO` | Chatwoot Inbox IG CANO | variable de configuración de Chatwoot Inbox IG CANO -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CHATWOOT_INBOX_INSTAGRAM` | Chatwoot Inbox Instagram | variable de configuración de Chatwoot Inbox Instagram -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CHATWOOT_INBOX_WA_CANO` | Chatwoot Inbox WA CANO | variable de configuración de Chatwoot Inbox WA CANO -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CHATWOOT_INBOX_WA_LUZYA` | Chatwoot Inbox WA Luzya | variable de configuración de Chatwoot Inbox WA Luzya -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CHATWOOT_INBOX_WEB` | Chatwoot Inbox WEB | variable de configuración de Chatwoot Inbox WEB -- sin consumidor detectado, revisar con Cano | bajo | no |
| `CHATWOOT_TOKEN` | Chatwoot | token de Chatwoot -- sin consumidor detectado, revisar con Cano | medio | no |
| `CHATWOOT_URL` | Chatwoot | URL de Chatwoot -- sin consumidor detectado, revisar con Cano | bajo | no |
| `DOCSPRING_API_SECRET` | Docspring | secreto de API de Docspring -- sin consumidor detectado, revisar con Cano | alto | no |
| `DOCSPRING_API_TOKEN` | Docspring | token de API de Docspring -- sin consumidor detectado, revisar con Cano | medio | no |
| `FORMBRICKS_DB_PASS` | Formbricks DB | contraseña de Formbricks DB -- sin consumidor detectado, revisar con Cano | alto | no |
| `FORMBRICKS_SECRET` | Formbricks | secreto de Formbricks -- sin consumidor detectado, revisar con Cano | alto | no |
| `JWT_ALGORITHM` | JWT | algoritmo de JWT -- sin consumidor detectado, revisar con Cano | bajo | no |
| `JWT_EXPIRE_MINUTES` | JWT Expire Minutes | variable de configuración de JWT Expire Minutes -- sin consumidor detectado, revisar con Cano | bajo | no |
| `JWT_SECRET` | JWT | secreto de JWT -- sin consumidor detectado, revisar con Cano | alto | no |
| `LISTMONK_ADMIN_PASS` | Listmonk Admin | contraseña de Listmonk Admin -- sin consumidor detectado, revisar con Cano | alto | no |
| `LISTMONK_ADMIN_USER` | Listmonk Admin | usuario de Listmonk Admin -- sin consumidor detectado, revisar con Cano | bajo | no |
| `LISTMONK_DB_PASS` | Listmonk DB | contraseña de Listmonk DB -- sin consumidor detectado, revisar con Cano | alto | no |
| `METABASE_DB_PASS` | Metabase DB | contraseña de Metabase DB -- sin consumidor detectado, revisar con Cano | alto | no |
| `MINIO_ACCESS_KEY` | Minio | clave de acceso de Minio -- sin consumidor detectado, revisar con Cano | medio | no |
| `MINIO_BUCKET` | Minio Bucket | variable de configuración de Minio Bucket -- sin consumidor detectado, revisar con Cano | bajo | no |
| `MINIO_ENDPOINT` | Minio Endpoint | variable de configuración de Minio Endpoint -- sin consumidor detectado, revisar con Cano | bajo | no |
| `MINIO_PASSWORD` | Minio | contraseña de Minio -- sin consumidor detectado, revisar con Cano | alto | no |
| `MINIO_PUBLIC_URL` | Minio Public | URL de Minio Public -- sin consumidor detectado, revisar con Cano | bajo | no |
| `MINIO_SECRET_KEY` | Minio | clave secreta de Minio -- sin consumidor detectado, revisar con Cano | alto | no |
| `MINIO_USER` | Minio | usuario de Minio -- sin consumidor detectado, revisar con Cano | bajo | no |
| `PLAUSIBLE_DB_PASS` | Plausible DB | contraseña de Plausible DB -- sin consumidor detectado, revisar con Cano | alto | no |
| `PLAUSIBLE_SECRET_KEY` | Plausible | clave secreta de Plausible -- sin consumidor detectado, revisar con Cano | alto | no |
| `PLAUSIBLE_SECRET_KEY_BASE` | Plausible Secret KEY BASE | variable de configuración de Plausible Secret KEY BASE -- sin consumidor detectado, revisar con Cano | alto | no |
| `VPS1_COOLIFY_API_TOKEN` | VPS1 Coolify | token de API de VPS1 Coolify -- sin consumidor detectado, revisar con Cano | medio | no |
| `VPS1_COOLIFY_URL` | VPS1 Coolify | URL de VPS1 Coolify -- sin consumidor detectado, revisar con Cano | bajo | no |
| `VPS1_EASYPANEL_KEY` | VPS1 Easypanel | clave de VPS1 Easypanel -- sin consumidor detectado, revisar con Cano | medio | no |
| `VPS1_EASYPANEL_URL` | VPS1 Easypanel | URL de VPS1 Easypanel -- sin consumidor detectado, revisar con Cano | bajo | no |
| `VPS1_IP` | VPS1 IP | variable de configuración de VPS1 IP -- sin consumidor detectado, revisar con Cano | bajo | no |
| `VPS1_SSH_PASS` | VPS1 SSH | contraseña de VPS1 SSH -- sin consumidor detectado, revisar con Cano | alto | no |
| `VPS1_SSH_USER` | VPS1 SSH | usuario de VPS1 SSH -- sin consumidor detectado, revisar con Cano | bajo | no |
| `VPS2_COOLIFY_API_TOKEN` | VPS2 Coolify | token de API de VPS2 Coolify -- sin consumidor detectado, revisar con Cano | medio | no |
| `VPS2_COOLIFY_URL` | VPS2 Coolify | URL de VPS2 Coolify -- sin consumidor detectado, revisar con Cano | bajo | no |
| `VPS2_IP` | VPS2 IP | variable de configuración de VPS2 IP -- sin consumidor detectado, revisar con Cano | bajo | no |
| `VPS2_SSH_PASS` | VPS2 SSH | contraseña de VPS2 SSH -- sin consumidor detectado, revisar con Cano | alto | no |
| `VPS2_SSH_USER` | VPS2 SSH | usuario de VPS2 SSH -- sin consumidor detectado, revisar con Cano | bajo | no |

## Totales

- Total de llaves: 273
- StarHome / Hermes: 15
- Otro proyecto: 210
- Infraestructura VPS (autohospedada): 48
- Sin consumidor detectado: 257

## Rotación pendiente (8)

- `CLOUDINARY_API_KEY` -- GET https://api.cloudinary.com/v1_1/{cloud_name}/usage con Basic auth devuelve 401 'cloud_name mismatch' -- confirmado en vivo 2026-08-07. El mensaje del proveedor indica que CLOUDINARY_CLOUD_NAME en el vault no corresponde a la cuenta de este api_key/api_secret (ese campo del vault hoy coincide caracter por caracter con CLOUDINARY_API_KEY, lo que sugiere un error de carga: alguien copio el api_key en el campo de cloud_name). No es un bug del validador -- el endpoint/auth son correctos. Hace falta que Cano corrija CLOUDINARY_CLOUD_NAME en el vault con el nombre real de la cuenta (visible en el dashboard de Cloudinary).
- `CLOUDINARY_API_SECRET` -- Mismo chequeo que CLOUDINARY_API_KEY (comparten validador, un solo request con las tres credenciales): 401 'cloud_name mismatch', causa raiz es CLOUDINARY_CLOUD_NAME incorrecto en el vault, no el secreto en si. Ver motivo de CLOUDINARY_API_KEY.
- `CLOUDINARY_CLOUD_NAME` -- Causa raiz del fallo de Cloudinary: este campo en el vault contiene el mismo valor que CLOUDINARY_API_KEY caracter por caracter (no un nombre de cuenta) -- confirmado programaticamente sin exponer valores. El proveedor responde 401 'cloud_name mismatch', consistente con un campo mal cargado. Cano debe reemplazarlo por el cloud_name real desde el dashboard de Cloudinary.
- `GITHUB_TOKEN` -- GET https://api.github.com/user con Bearer + Accept devuelve 401 'Bad credentials' de forma consistente -- probado tambien con esquema 'token' y con User-Agent explicito, mismo resultado. Endpoint/headers correctos segun docs.github.com/rest, el validador esta bien. Token revocado o expirado.
- `HEYGEN_API_KEY` -- GET https://api.heygen.com/v2/user/remaining_quota con x-api-key devuelve 401 Unauthorized -- confirmado en vivo 2026-08-07, endpoint/header correctos segun docs.heygen.com. El valor guardado en el vault no tiene forma de llave real de HeyGen (es un texto de marcador de posicion, nunca se cargo la llave real). No es un bug del validador: hace falta que Cano genere y cargue una llave real desde app.heygen.com.
- `KIMI_API_KEY` -- expuesta en transcript de sesión (F11, K9, K16 del plan Prometeo/HERMES-KICKOFF)
- `MISTRAL_API_KEY` -- GET https://api.mistral.ai/v1/models con Bearer devuelve 401 'Invalid API Key' de forma consistente -- confirmado en vivo 2026-08-07, mismo endpoint/header que documenta la API oficial de Mistral, el validador esta correcto. Llave revocada o caducada, no una llave que nunca se cargo.
- `NVIDIA_NIM_API_KEY` -- expuesta en transcript de sesión (F11, K9, K16 del plan Prometeo/HERMES-KICKOFF)
