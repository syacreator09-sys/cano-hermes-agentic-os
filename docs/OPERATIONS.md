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
`notion-mcp`, 27 de `n8n-mcp`). Nota operativa: los argumentos de arranque de
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
