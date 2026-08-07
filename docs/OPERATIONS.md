# Operations — runbook operativo del servidor Hermes

> Semilla de K0 (plan HERMES-KICKOFF). Cubre lo mínimo para operar el
> servidor sin supervisión: arranque, salud, canales de mensajería y
> troubleshooting básico. K13 lo completa con dashboards y contabilidad.

## Arranque y salud

| Sistema | Comando |
|---|---|
| StarHome OS (gobierno, `:8787`) | `cd ~/repos/cano-hermes-agentic-os && . .venv/bin/activate && make api` |
| Hermes Agent (operación) | `hermes` · `hermes dashboard` · `hermes serve` |
| Gateway hermes (Telegram/SMS/MCP, systemd user unit) | `systemctl --user status hermes-gateway.service` |
| StarHome Nexus (memoria) | `nexus doctor` |

Salud rápida:

```bash
curl -s localhost:8787/api/health | jq .
hermes status
nexus doctor
```

Suite de tests (debe estar verde antes de cualquier merge a `main`):

```bash
cd ~/repos/cano-hermes-agentic-os && . .venv/bin/activate
python -m unittest discover -s tests
python -m pytest -q
```

### Base de datos (sqlite)

`storage/hermes.db` corre en modo `WAL` con `busy_timeout=5000` (fijado en
`cano_hermes/storage/sqlite.py`, método `connect()`) — necesario porque
varios componentes (API, workers, cron) pueden abrir conexiones concurrentes.
Verificar:

```bash
sqlite3 storage/hermes.db "PRAGMA journal_mode;"   # → wal
```

### Reaper de tareas huérfanas

El `lifespan` de `cano_hermes/api/app.py` llama `engine().reap_orphaned()`
al arrancar: cualquier `TaskRecord` que haya quedado en `RUNNING` (proceso
muerto por crash o restart, nunca más va a transicionar por sí solo) pasa a
`FAILED` con un evento `{"reason": "orphaned-on-restart"}`. Cubierto por
`tests/test_reaper.py`. No requiere intervención manual — es automático en
cada arranque de la API.

## Canales de mensajería

### Telegram — activo, canal home configurado

El gateway hermes (`~/.hermes/config.yaml` + `~/.hermes/.env`) mantiene la
conexión Telegram por polling. El **canal home** (a dónde se entregan cron
jobs, notificaciones cross-platform y mensajes cuando no hay un chat activo)
se resuelve vía la env var `TELEGRAM_HOME_CHANNEL` (mapa completo en
`cron/scheduler.py::_HOME_TARGET_ENV_VARS` del repo `hermes-agent`), leída
desde `~/.hermes/.env`.

Ese valor se puede fijar de dos formas:
- **`/sethome`** — comando de chat, requiere que alguien lo escriba en
  Telegram (no programático).
- **`TELEGRAM_HOME_CHANNEL` en `~/.hermes/.env`** — vía programática, usada
  aquí. Se llenó con el mismo `TELEGRAM_CHAT_ID` que ya vive en el vault de
  credenciales y que se usó para mandar un aviso directo por Bot API. El
  valor nunca se imprime en logs de esta sesión ni se commitea (`.env` no
  está trackeado).

**Nota sobre `hermes config set`**: no usar `hermes config set
TELEGRAM_HOME_CHANNEL ...` para esta variable — el comando no la reconoce
como "env-shaped" y la escribe como clave top-level en `config.yaml` en vez
de `.env` (con advertencia de que "puede no ser leída"). El camino correcto
y el que usa el propio flujo interactivo de `hermes setup` es
`save_env_value("TELEGRAM_HOME_CHANNEL", ...)`, que escribe en `~/.hermes/.env`.

**`channel_directory.json` con `telegram: []` es normal.** Ese archivo lo
construye `gateway/channel_directory.py::build_channel_directory()` a partir
del hook `list_channels()` de cada adapter — pensado para plataformas tipo
servidor/guild (Discord, Slack) donde se puede *listar* canales. Telegram no
expone una API para enumerar todos los chats DM pasados, así que el
directorio queda vacío aunque la entrega funcione perfectamente por la vía
directa (`TELEGRAM_HOME_CHANNEL` + Bot API). No es una señal de fallo.

**Verificación real** (no asumir — confirmar en el log): crear un cron job
efímero `--no-agent` con un script que haga `echo` de algo no-silencioso,
dispararlo con `hermes cron run <job_id>`, y confirmar en
`~/.hermes/logs/gateway.log` la línea:

```
cron.scheduler: Job '<job_id>': delivered to telegram:<chat_id>
```

Si en cambio aparece `agent returned [SILENT] — skipping delivery`, el job
corrió pero decidió no reportar (comportamiento esperado de jobs tipo
heartbeat cuando no hay novedad) — no es un fallo de entrega. Si aparece `no
delivery target resolved for deliver=telegram`, el canal home no está
configurado.

Reiniciar el gateway (`systemctl --user restart hermes-gateway.service`)
después de cambiar `~/.hermes/.env` o `~/.hermes/config.yaml` — el proceso
del gateway (`hermes_cli.main gateway run`) no tiene un watcher de
auto-reload de esas variables (a diferencia de la config de `mcp_servers:`,
que sí se recarga con `/reload-mcp`, pero eso es un comando **interactivo**
de la REPL de `hermes`, no algo invocable en un proceso systemd headless —
por eso un restart completo es la vía correcta para el gateway).

### SMS — deshabilitado, estado `fatal`

El adapter SMS del gateway se niega a arrancar:

```
[sms] Refusing to start: SMS_WEBHOOK_URL is required for Twilio signature
validation. Set it to the public URL configured in your Twilio console
(e.g. https://example.com/webhooks/twilio). For local development without
validation, set SMS_INSECURE_NO_SIGNATURE=true (NOT recommended for
production).
```

**Decisión (K0):** deshabilitado por ahora, no es prioridad. Falta
`SMS_WEBHOOK_URL` (endpoint público para que Twilio pueda validar la firma
de cada webhook) y no hay urgencia de negocio para exponer un endpoint
público solo para esto. Retomar si/cuando haya un caso de uso real para SMS;
mientras tanto el gateway sigue operando normalmente con 1 plataforma activa
(Telegram) — el fallo de SMS no bloquea nada más.

## MCP registrados en el gateway

`~/.hermes/config.yaml` → `mcp_servers:` tiene `n8n-mcp` y `notion-mcp` con
`enabled: true`. El proceso del gateway solo carga `mcp_servers:` al
arrancar (sin watcher de auto-reload como el de la CLI interactiva), así que
cualquier cambio a esa sección requiere `systemctl --user restart
hermes-gateway.service`. Verificar carga real (no solo config) en
`~/.hermes/logs/agent.log`:

```bash
grep "MCP server" ~/.hermes/logs/agent.log | tail -5
grep "MCP: registered" ~/.hermes/logs/agent.log | tail -1
```

Debe verse algo como `MCP: registered 51 tool(s) from 2 server(s)` (24 de
`notion-mcp`, 27 de `n8n-mcp`).

**Sweep K15 (2026-08-06) — confirmado vivo tras todos los restarts de
K0/K10/K13/K14:** `hermes mcp list` en vivo muestra ambos `✓ enabled`.
`~/.hermes/logs/agent.log` confirma el restart más reciente (18:34:22,
posterior a K14) registrando `MCP: registered 51 tool(s) from 2 server(s)`
— 24 de `notion-mcp`, 27 de `n8n-mcp` (subió de 9 a 27 entre K0 y K14
porque `n8n-mcp` expone más tools de escritura cuando su credencial tiene
más scope, no por ningún cambio de este repo). `rapidapi-tiktok` sigue
bloqueado — `RAPIDAPI_KEY` sigue ausente de
`~/.secrets/credenciales/credenciales/.env` (confirmado de nuevo hoy,
`grep -c RAPIDAPI_KEY` → 0). Nada que activar ni reparar en este sweep.

Nota operativa: los argumentos de arranque de
estos servidores MCP (incluidas sus API keys, pasadas por `--env` en
`args:`) quedan visibles en claro vía `ps`/`systemctl status` mientras el
proceso vive — es inherente a cómo `npx` recibe credenciales por línea de
comando, no un bug de esta sesión. Evitar pegar la salida de `systemctl
status hermes-gateway.service` (proceso completo con hijos) en chats o
tickets; usar en su lugar `systemctl --user is-active hermes-gateway.service`
o filtrar por `PID`/nombre de proceso solamente.

## Browser automation (agent-browser) — K10

`hermes-agent` trae el toolset `browser` (12 tools: `browser_navigate`,
`browser_snapshot`, `browser_click`, `browser_type`, `browser_scroll`,
`browser_back`, `browser_press`, `browser_get_images`, `browser_vision`,
`browser_console`, `browser_cdp`, `browser_dialog` — `toolsets.py:199` en el
repo `hermes-agent`), pero necesita el backend `agent-browser` (CLI npm)
instalado en la máquina para funcionar. `computer_use` (control de escritorio
vía `cua-driver`) es un toolset **separado** y queda fuera de alcance
explícito de K10 — esta máquina no tiene GPU y 4 núcleos no dan para eso.

### Instalación (hecha, K10)

```bash
npm i -g agent-browser        # instala el CLI (paquete npm)
agent-browser install --with-deps   # descarga Chrome + libs del sistema
```

- `agent-browser install --with-deps` intenta `sudo apt-get install` un set de
  libs GTK/X11 — en esta máquina falló por falta de contraseña sudo no
  interactiva (`sudo: se requiere una contraseña`). **No bloqueante**: `ldd`
  sobre el binario de Chrome descargado no reporta ninguna lib faltante, así
  que las libs ya estaban presentes en el sistema (Ubuntu 24.04 desktop, no
  server headless minimalista). Confirmado con `agent-browser doctor`.
- Chrome for Testing queda en `~/.agent-browser/browsers/chrome-<version>/`
  (no en `~/.cache`), gestionado por el propio `agent-browser`, no por
  Playwright.
- **Sandbox de Chromium**: Ubuntu 24.04 tiene
  `apparmor_restrict_unprivileged_userns=1`
  (`/proc/sys/kernel/apparmor_restrict_unprivileged_userns`), lo que rompe el
  sandbox por defecto de Chrome (`No usable sandbox!`, exit sin
  `DevToolsActivePort`). `hermes-agent` ya lo detecta solo
  (`tools/browser_tool.py::_needs_chromium_sandbox_bypass`, issue #15765) e
  inyecta `AGENT_BROWSER_ARGS=--no-sandbox,--disable-dev-shm-usage`
  automáticamente — **no requiere ninguna acción manual**. Verificado con el
  smoke test real (ver más abajo).
- Verificación: `which agent-browser` → `~/.npm-global/bin/agent-browser` (o
  el prefix npm global que corresponda). `agent-browser doctor` debe mostrar
  `pass  Google Chrome for Testing ...` y, tras un `open` real, `Launch test`
  en verde.

### Alcance del toolset `browser` — solo research y UGC

Política de seguridad: `browser` **no** está habilitado globalmente. Navegar
la web real (sesiones, formularios, clicks) es superficie de riesgo que no
debe estar disponible por defecto en cualquier oficina/perfil.

Mecanismo real confirmado en el código de `hermes-agent` (no asumido):
`hermes-agent` resuelve qué toolsets están activos por **plataforma**
(`platform_toolsets` en `config.yaml`, `hermes_cli/tools_config.py::
_get_platform_tools`) y luego resta `agent.disabled_toolsets`
(`hermes_cli/tools_config.py`, comentario en `hermes_cli/setup.py:3251-3263`).
Cada **perfil** (`hermes profile create <nombre>`) es un `HERMES_HOME`
completamente aislado con su propio `config.yaml` — por eso "restringir por
perfil" = restringir por `HERMES_HOME`, no una sub-clave dentro de un único
config compartido.

Aplicado:

- `~/.hermes/config.yaml` (perfil default): `agent.disabled_toolsets:
  [browser]` — apaga `browser` para cualquier sesión que no pase
  `--toolsets` explícito (interactiva, cron, gateway).
- `~/.hermes/profiles/hermes-research/config.yaml` y
  `~/.hermes/profiles/hermes-ugc/config.yaml` (creados con `hermes profile
  create <nombre> --no-skills`, uno por oficina — mismo nombre que
  `offices/hermes-research/office.yaml` y `offices/hermes-ugc/office.yaml`
  en este repo): `platform_toolsets.cli: [hermes-cli, browser]` — reactivan
  `browser` explícitamente, sin depender de que el default global no cambie
  algún día.
- Verificado invocando directamente el resolver puro de `hermes-agent`
  (`hermes_cli.tools_config._get_platform_tools`) sobre los tres
  `config.yaml`: `browser` efectivamente **False** en el perfil default,
  **True** en `hermes-research` y `hermes-ugc`.
- **Gap conocido, no resuelto en K10**: StarHome (`HermesAgentExecutor` en
  `cano_hermes/runtimes/hermes_agent.py`) todavía no invoca `hermes -p
  hermes-research` / `-p hermes-ugc` según la oficina del task — hoy corre
  siempre bajo el perfil default y solo hereda `browser` cuando el
  `AgentManifest.tools` de la tarea lo lista explícito (`--toolsets`
  explícito en la línea de comando, que gana sobre cualquier
  `platform_toolsets`). Los dos perfiles nuevos quedan listos y correctos
  para cuando se cablee esa selección de perfil por oficina (candidato
  natural para K12, que ya toca gobernanza de acciones sensibles). Ver
  también el comentario en `cano_hermes/orchestration/
  execution_service.py::AGENT_RUNTIME_TO_EXECUTOR` — el runtime `browser`
  de un `AgentManifest` hoy mapea al executor `openclaw` (stand-in), no a
  `hermes-agent`; darle un executor dedicado también quedó fuera de este K10
  por alcance (no estaba en las 5 tareas encargadas) y es otro candidato para
  el mismo follow-up.

### Política de riesgo: `browser_with_session`

Regla (documentada aquí; el motor de auto-aprobación completo es K12):
**cualquier tarea que use el toolset `browser` y toque un dominio con
sesión/login (no un GET público simple como el smoke test a
`example.com`) se clasifica como riesgo `MEDIUM` como mínimo y nunca es
auto-aprobable.** Un GET anónimo a una página pública (documentación,
`example.com`, un artículo) no dispara esta regla; login, cookies de sesión,
un dominio real de Cano con cuenta (Shopify, Meta, YouTube, TikTok Shop) sí.

Anotado en `cano_hermes/governance/policy.py`: `browser_with_session` se
agregó a `SENSITIVE_ACTIONS`. Cualquier acción en ese set fuerza
`requires_approval=True` en `PermissionEngine.evaluate_action` sin importar
el `RiskLevel` calculado — es el mecanismo correcto para "nunca
auto-aprobable" con el código que ya existe hoy (`RiskLevel.MEDIUM` por sí
solo *no* fuerza aprobación en la lógica actual; `SENSITIVE_ACTIONS` sí,
independientemente del risk level). Lo que **no** existe todavía — y es
explícitamente alcance de K12, no de K10 — es el clasificador que mire una
tarea de browser, detecte que el dominio objetivo requiere sesión, y emita
la acción `browser_with_session` en vez de la genérica `production_write`
que usa hoy `ExecutionService.run()`. Por ahora esto es el contrato/anotación
para que K12 no tenga que inventar el nombre de la acción ni tocar este
archivo de nuevo.

### Camoufox (Firefox anti-detect) — opción futura, no instalada

[Camoufox](https://camoufox.com) es un Firefox parcheado a nivel C++ para
evadir fingerprinting/detección de automatización (a diferencia de
parches JS en runtime, que son detectables). Es una alternativa de backend
para navegación que necesite evadir detección de bot (a diferencia de
Chrome/Chromium vía `agent-browser`, que no la evade). **No es prioridad
ahora** — el backend actual (`agent-browser` + Chrome) cubre el caso de uso
de K10 (research/UGC con navegación autorizada, no scraping adversarial).
Queda anotado como opción futura si alguna oficina necesita navegar sitios
con detección de bot agresiva.

### Smoke test real (K10)

```bash
hermes --oneshot "Navega a https://example.com usando el toolset browser y \
dime exactamente el texto del <title> de la pagina. Responde solo con el \
titulo." --toolsets browser --usage-file <ruta.json>
```

Resultado real (2026-08-06, perfil default, modelo `kimi-k2.6` / provider
`kimi-coding`, tier 0 gratis): respuesta `Example Domain` — navegación real
confirmada (no mockeada), `agent-browser doctor` en verde tras el run,
`estimated_cost_usd: 0.0`. Sin restricciones violadas: el único dominio real
tocado fue `example.com` (GET público, sin sesión).

## Voz (STT local, TTS, wake word) — K13

`hermes-agent` trae voz completa ya construida (6 proveedores STT, TTS con
`edge-tts` — ya usado en Prometeo F10 —, wake word "Hey Hermes" con
openWakeWord, `voice_mode` push-to-talk/VAD) pero las deps de STT/wake no
estaban instaladas. El gateway **ya auto-transcribe** notas de voz entrantes
de Telegram/Discord/etc. una vez esas deps están presentes — es
comportamiento existente (`gateway/run.py::_enrich_message_with_transcription`),
no código nuevo.

### Instalación de deps (hecha, K13)

```bash
cd ~/repos/hermes-agent
UV_PROJECT_ENVIRONMENT="$(pwd)/venv" uv sync --extra voice --extra wake --locked
```

**Nota importante para quien repita esto**: el entorno real de `hermes-agent`
en esta máquina vive en `venv/` (no `.venv/`), fijado vía
`UV_PROJECT_ENVIRONMENT` — así lo hace `setup-hermes.sh`/`scripts/install.sh`
internamente. Correr `uv sync --extra voice` **sin** ese env var apunta a un
`.venv` nuevo y, peor, si se corre apuntando al `venv/` real pero **sin**
repetir todos los extras que ya estaban instalados, `uv sync` es un *sync*
(no un *add*): desinstala todo lo que no esté en los extras pedidos. Pasó en
esta sesión — un primer intento con solo `--extra voice --extra wake` se
comió `messaging`, `google`, `mcp`, `edge-tts`, `wecom`, `fal`, `bedrock`
(59 paquetes desinstalados, gateway habría fallado en el próximo restart).
Se restauró con:

```bash
UV_PROJECT_ENVIRONMENT="$(pwd)/venv" uv sync --extra all --extra messaging \
  --extra edge-tts --extra wecom --extra fal --extra bedrock \
  --extra voice --extra wake --locked
```

Confirmado tras la reinstalación: imports directos en el venv real
(`venv/bin/python -c "import sounddevice, numpy, faster_whisper,
openwakeword, edge_tts, telegram, mcp, google.auth, fastapi, discord,
slack_bolt, boto3, fal_client, defusedxml, onnxruntime"`) — todos OK. Antes
de la instalación, `sounddevice`, `numpy`, `faster_whisper`, `openwakeword`
fallaban con `ModuleNotFoundError`.

### STT — modelo `small` en `int8`

`~/.hermes/config.yaml` tenía la sección `stt` vacía (default implícito:
`provider: local`, `model: base`, `language: en` global). Se fijó
explícito:

```yaml
stt:
  enabled: true
  provider: local
  language: es       # ver nota abajo
  local:
    model: small
    compute_type: int8
```

- `hermes-agent` sí permite elegir tamaño/cuantización por config
  (`stt.local.model`: tiny|base|small|medium|large-v3|turbo;
  `stt.local.compute_type`, leído en
  `tools/transcription_tools.py::_transcribe_local` vía
  `local_cfg.get("compute_type", "auto")`) — no hubo que tocar código.
  `small`/`int8` es el balance razonable para 4 núcleos sin GPU pedido por
  K13; `auto` en CPU típicamente ya resuelve a `int8` vía ctranslate2, pero
  se fijó explícito para que quede documentado y no dependa de heurística.
- **Bug de config encontrado y corregido**: el default upstream de
  `stt.language` es `"en"` (hardening anti-mis-detección para clips
  cortos/con acento — ver comentario en `config_defaults.py:1511-1516`).
  Cano opera en español; con el default sin tocar, cualquier nota de voz
  real en español se habría forzado a transcribir como si fuera inglés. Se
  fijó `language: es` explícito en vez de dejar el default o usar
  auto-detect puro (menos fiable en audios cortos, según el mismo
  comentario upstream).
- Modelo `small` confirmado descargado y cacheado localmente (gratis, sin
  llamada a API): `~/.cache/huggingface/hub/models--Systran--faster-whisper-small`.

### Wake word "Hey Hermes" — mecanismo confirmado, mic bloqueado por lib de sistema

Modelo bundled real (no un nombre stock de openWakeWord):
`hermes-agent/tools/wakewords/hey_hermes.{onnx,tflite}`, resuelto por
`tools/wake_word.py::_bundled_wakeword_path` /
`_BUNDLED_MODEL_ALIASES = {"", "hey_hermes", "hey hermes", "hermes"}`.
Se activa con el slash command `/wake [on|off|status]` (interactivo, REPL de
`hermes`) — no hay RPC `wake.start` expuesto, es una función Python interna
(`tools.wake_word.start_listening`).

Diagnóstico real corrido (`tools.wake_word.check_wake_word_requirements()`,
la misma función detrás de `/wake status`):

```json
{
  "available": false,
  "provider": "openwakeword",
  "deps_available": true,
  "audio_available": false,
  "access_key_set": true,
  "stt_available": true,
  "tts_available": true,
  "phrase": "hey hermes",
  "hint": "Microphone capture needs sounddevice + numpy and a working audio device."
}
```

`deps_available: true` — el modelo ONNX, `openwakeword`, `onnxruntime` y
`sherpa-onnx` cargan bien. Lo único que falta es `libportaudio2` (paquete de
sistema, no de pip) — `sounddevice` no encuentra la lib nativa
(`OSError: PortAudio library not found`). Mismo patrón que el bloqueo de
`agent-browser install --with-deps` en K10: `sudo apt-get install -y
libportaudio2` falla en esta sesión por falta de contraseña sudo no
interactiva. **Es un paquete trivial y sin riesgo** (librería de audio, no
toca red ni credenciales) — queda pendiente para cuando Cano corra ese único
comando manualmente. Confirmado que **no** hay forma limpia de rodearlo sin
root: se probó extraer el `.deb` sin sudo (`apt-get download` +
`dpkg-deb -x`) y apuntar `LD_LIBRARY_PATH` a la lib extraída, pero
`ctypes.util.find_library` en Linux lee el cache de `ldconfig`, no
`LD_LIBRARY_PATH` — la única vía real es la instalación de sistema.

**Importante — esto solo bloquea captura de micrófono en vivo** (wake word
continuo, `voice_mode` push-to-talk/VAD). **No bloquea STT de archivo**:
`faster-whisper` decodifica archivos vía el paquete `av` (ffmpeg embebido),
sin pasar por `sounddevice` en ningún punto — confirmado por grep sin
resultados de `sounddevice` en `tools/transcription_tools.py`. Es decir: la
transcripción automática de notas de voz de Telegram (que llegan como
archivo `.ogg`, no como stream de mic) funciona igual sin `libportaudio2`.

Por la restricción de K13 de no dejar wake-word continuo corriendo de fondo
(consume CPU en escucha permanente), **no se activó** `/wake on` ni
`wake_word.enabled: true` en `config.yaml` (default `false`, sin tocar) —
queda confirmado que el mecanismo funciona (salvo el mic físico, bloqueado
por el paquete de sistema pendiente) pero opt-in, no corriendo.

### Verificación E2E real (STT de archivo)

Audio de prueba generado con `edge-tts` (gratis, local, ya usado en
Prometeo F10):

```bash
venv/bin/python -m edge_tts --voice es-MX-DaliaNeural \
  --text "hola hermes, dime la hora" --write-media test_voice.mp3
```

Transcripción corrida con el **mismo entrypoint de producción** que usa el
gateway para notas de voz reales (`gateway/run.py:21375` llama
`transcribe_audio()` vía `asyncio.to_thread`) — no un script aislado:

```python
from tools.transcription_tools import transcribe_audio
transcribe_audio("test_voice.mp3")
# → {'success': True, 'transcript': 'Hola Hermes, dime la hora.', 'provider': 'local'}
```

Resultado real: `Hola Hermes, dime la hora.` — coincide (salvo
capitalización/puntuación, esperable) con el texto pedido en el audio de
prueba. Usó el modelo `small`/`int8` recién configurado (confirmado por el
cache de HuggingFace poblado con `faster-whisper-small`), `stt.language: es`
tomado de `~/.hermes/config.yaml`, ~4s de transcripción en CPU de 4 núcleos.

**Gateway reiniciado** (`systemctl --user restart hermes-gateway.service`)
tras instalar deps y fijar config, para que el proceso levante con el venv
actualizado y la config de `stt` — el proceso del gateway no tiene
auto-reload de deps ni de `config.yaml` (mismo patrón que Telegram/MCP,
documentado arriba). Verificado activo y estable post-restart
(`systemctl --user status hermes-gateway.service` → `active (running)`,
sin platform nuevo caído más allá del SMS ya conocido/deshabilitado).

**Estado de la verificación con Telegram real**: **no probado con audio
entrante real** — no hay forma limpia de simular una nota de voz real
llegando al bot (`@CANO_DIGITAL_OPENCLAW_BOT`) sin control del cliente
Telegram de otro lado. Confirmado **por código**, no por corrida real: el
flujo `plugins/platforms/telegram/adapter.py` (línea ~9134) descarga la nota
de voz (`msg.voice.get_file()` → `download_as_bytearray()`) a un archivo
`.ogg` local, y `gateway/run.py::_enrich_message_with_transcription` llama
exactamente el mismo `transcribe_audio()` ya verificado arriba. Dado que el
entrypoint es idéntico y el archivo de prueba (mp3, no ogg) transcribió
bien, la expectativa razonable es que una nota `.ogg` real de Telegram
funcione igual — pero es una inferencia, no una observación directa.

## Patrón `PENDING_NATIVE_TOOL` — MCP de Claude.ai (K15)

Los MCP conectados a esta cuenta de Claude.ai (Shopify, Meta/Facebook,
Gamma, Adobe, Canva, Vercel, Upload-post, etc.) son **invocables solo
desde una sesión Claude interactiva** — viven en la capa MCP del cliente
Claude.ai, no en `~/.hermes/config.yaml` como `n8n-mcp`/`notion-mcp`
(sección anterior). StarHome (proceso `api/app.py`, `:8787`) y el gateway
hermes-agent (`hermes serve`) son procesos de fondo sin sesión Claude
adjunta — no tienen forma de llamar `mcp__claude_ai_Shopify__*` ni
ninguno de sus pares en tiempo real. No hay wiring hacia el backend de
StarHome para estos conectores y no lo habrá mientras sigan atados a una
sesión de cliente (confirmado en K11/K15, no es un hueco de
implementación pendiente).

Esto no es un caso nuevo: es exactamente el problema que Factory V5 ya
resolvió para ImageGen nativa de ChatGPT/Codex (`codex_native_imagegen`,
documentado en `~/repos/cano-ai-command-center/01-offices/factory-ia-
channel-v5/docs/cano/NATIVE-IMAGEGEN-BRIDGE.md`, repo de solo lectura —
leído para este diseño, no modificado). El patrón que Factory V5 usa,
adaptado aquí como diseño para una fase futura que lo implemente (esta
fase **documenta el patrón, no lo cablea**):

1. **Un job StarHome que necesita un MCP de Claude.ai** (p. ej. "leer
   ventas de la tienda Shopify CASS" para el dashboard de K19, o
   "publicar un draft en Canva") se marca `status: PENDING_NATIVE_TOOL`
   en vez de `FAILED` o quedarse `RUNNING` indefinidamente — mismo
   principio que los estados `PENDING_NATIVE_TOOL` / `CLAIMED` /
   `GENERATED` / `VALIDATED` del bridge de ImageGen: la solicitud es un
   artefacto en disco (o una fila de tabla), no una llamada síncrona que
   se cuelga esperando un tool que el proceso de fondo no tiene.
2. El job carga: qué MCP/tool exacto se necesita (`mcp__claude_ai_
   Shopify__get-shop-info`, por ejemplo), los parámetros ya resueltos, y
   dónde debe escribirse el resultado (mismo espíritu que
   `outputs/jobs/<job_id>/native-image-requests/<slide_id>.json` del
   bridge de ImageGen, pero para esta capa sería algo como
   `storage/pending_native_tool/<job_id>.json`).
3. **Una sesión Claude futura resuelve el job**: lee la solicitud
   pendiente (vía un comando explícito, no automático — "resuelve los
   jobs PENDING_NATIVE_TOOL de StarHome"), invoca el MCP real con sesión
   propia autenticada, y escribe el resultado firmado de vuelta (mismo
   principio que el resultado con `asset_hash`/`request_hash` del bridge
   de ImageGen — el resultado debe ser verificable contra lo que se
   pidió, no un texto libre).
4. StarHome valida el resultado (forma/hash/campos esperados) y
   transiciona el job — igual que Factory V5 nunca declara `COMPLETE`
   solo por tener una solicitud o un archivo, StarHome nunca debe
   declarar el paso DONE solo por la existencia de un resultado sin
   validar su forma.
5. **Nunca autónomo en el sentido de gasto/publicación**: igual que el
   bridge de ImageGen ("publicar sigue requiriendo flujo manual y
   aprobación humana"), cualquier job `PENDING_NATIVE_TOOL` que implique
   escribir/gastar/publicar (crear un descuento en Shopify, publicar un
   post) pasa por el mismo `ApprovalService`/`governance/auto_approval.py`
   (K12) que cualquier otra acción de ese riesgo — el patrón resuelve
   *cómo* se invoca la herramienta, no *si* se aprueba.

**Caso de uso concreto (K15, cableado en K19):** la vista
`GET /api/dashboard/business/cass` (K19) necesita ventas/productos de la
tienda Shopify "CASS Beauty Clinic" (`fss1nv-s1.myshopify.com`, MCP
`claude_ai_Shopify` ya conectado a esta cuenta) y métricas básicas de la
página Meta "CASS Medicina Estética" — ambas se resuelven con este
patrón, ahora implementado (no solo diseñado): `cano_hermes.integrations.
native_tool_bridge.request_job` (K19) escribe/lee los pasos 1, 2 y 4
arriba como archivos reales en `storage/pending_native_tool/<job_id>.
request.json` / `<job_id>.result.json` (gitignored, creados en runtime).
`business/cass.py`'s `shopify_status()`/`meta_status()` llaman a ese
bridge con los tools/params ya resueltos (`get-shop-info`/`list-orders`/
`search_products` para Shopify; `ads_get_user_pages`/
`ads_get_pages_for_business` para Meta, la superficie de lectura más
cercana que el MCP Facebook conectado expone hoy) y jamás hacen una
llamada HTTP ellos mismos (`tests/test_k19_business_cass.py::
ShopifyMetaNeverWriteTests` lo confirma por escaneo de código fuente, no
solo por observación de una corrida). El paso 3 (una sesión Claude
resolviendo el job de verdad) sigue sin ejecutarse — es, por diseño,
autónomo del proceso de fondo; queda para cuando Cano pida resolver los
jobs `PENDING_NATIVE_TOOL` pendientes hoy (`cass-shopify-status`,
`cass-meta-status`).

## Troubleshooting básico

- **`curl localhost:8787/api/health` no responde** → la API StarHome no está
  corriendo; `cd ~/repos/cano-hermes-agentic-os && . .venv/bin/activate &&
  make api`. Confirmar el endpoint es `/api/health`, no `/health`.
- **Gateway caído** → `systemctl --user status hermes-gateway.service`;
  logs en `~/.hermes/logs/gateway.log` (ciclo de vida del proceso) y
  `~/.hermes/logs/agent.log` (turnos del agente, MCP, tools).
- **Cron no entrega** → revisar `hermes cron list` (marca `⚠ Delivery
  failed: no delivery target resolved` si el canal home no está
  configurado) y la sección Telegram arriba.
- **Suite roja** → nunca mergear a `main` con tests rotos; diagnosticar y
  arreglar antes de cualquier commit de este ciclo.
