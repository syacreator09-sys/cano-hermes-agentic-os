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
