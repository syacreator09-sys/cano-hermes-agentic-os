# K9 — Oficinas Docker v2 interconectadas (plan HERMES-KICKOFF)

Fecha: 2026-08-06. Ejecutado sin supervisión sobre `main` (K0-K8 ya mergeados,
193 unittest + 196 pytest de piso).

## 1. Mapeo final office.yaml ↔ oficina Docker

| office.yaml | isolation declarada | Oficina Docker | Kanban profile (OFFICE_PROFILE) | Nota |
|---|---|---|---|---|
| `hermes-ugc` | docker | `office-ugc` | `hermes-ugc` | 1:1 ya existía por nombre y misión |
| `hermes-distribucion` | docker | `office-publish` | `hermes-distribucion` | 1:1 por misión ("preparar drafts de subida... dispatch SIEMPRE gate") |
| `hermes-produccion` | **folder → docker** (reclasificado en K9) | `office-content` | `hermes-produccion` | Render (ffmpeg/Remotion/MoneyPrinter) es lo más pesado de las 6 oficinas; se benefició de sandbox real. Reclasificación documentada en el propio `office.yaml` |
| `hermes-monitor` | none (sin cambio) | `office-analytics` | `hermes-monitor` | `office-analytics` ya envolvía exactamente `connection_matrix.py`, la tarea de `hermes-monitor`; docker es superset seguro de `none` |
| `hermes-market-intel` | docker (nuevo) | `office-market-intel` | `hermes-market-intel` | Oficina 5ª, construida en K9 desde el diseño F14 |
| `hermes-guiones` | folder (sin cambio) | — ninguna, worker nativo | `hermes-guiones` | Guionismo puro LLM, no necesita el mount de factory-v5 ni sandbox |
| `hermes-research` | folder (sin cambio) | — ninguna, worker nativo | `hermes-research` | Ya confirmado por K6 como perfil real, sin oficina Docker |

`cano_hermes/orchestration/conductor.py`'s `TEAM_TO_KANBAN_PROFILE` no se tocó:
`"content"` sigue como placeholder `team-content` a propósito (4 oficinas
tocan contenido, ninguna es el 1:1 obvio para el *dominio* `content` de
StarHome — el mapeo real vive a nivel oficina↔perfil kanban, no
dominio↔perfil, y ya está resuelto en `PROFILE_TO_OFFICE` de
`office_launcher.py`).

## 2. Red compartida + aislamiento preservado

- `infrastructure/create-shared-network.sh` crea `starhome-net` (bridge,
  `external: true` en ambos compose files) una sola vez.
- **Hallazgo real**: F11 nunca implementó aislamiento de red por servicio
  (sin `network_mode`, sin `networks:` por servicio) — su aislamiento
  siempre fue solo por credenciales (`environment:` allowlist explícito).
  Antes de K9, las 4 oficinas ya compartían la red default del proyecto
  `offices` entre sí; solo Baserow (proyecto `baserow` separado) estaba
  aislado de ellas. `starhome-net` conecta ambos proyectos sin romper nada
  que existiera antes.
- Verificado en vivo: `office-analytics` resuelve `starhome-baserow` por
  DNS y le hace un `GET /_health` real (200 OK) sobre `starhome-net`.
- `office-publish` sigue sin una sola credencial de publicación real
  (verificado con `docker compose config --no-interpolate`: solo
  `KIMI_API_KEY`/`KIMI_BASE_URL`/`NVIDIA_API_KEY` aparecen). `office-market-intel`
  sin variables `ALPACA_*`/`IBKR_*`/`BINANCE_*` ni equivalentes.

## 3. Oficinas como workers kanban reales (no one-shot)

`infrastructure/offices/common/entrypoint.sh` ahora soporta
`WORKER_MODE=kanban` (default) y `WORKER_MODE=oneshot` (legado F11, para
debug manual). En modo kanban cada contenedor hace polling de
`hermes kanban --board starhome list --assignee <profile> --status ready`,
reclama (`claim`), corre `task.sh` + `hermes --oneshot`, y cierra el ciclo
con `complete`/`block`.

**Acceso al board**: se probó en vivo que
`HERMES_HOME=<dir con solo kanban/boards/starhome> hermes kanban --board
starhome list --json` funciona con nada más presente — así que cada
oficina monta *solo* `~/.hermes/kanban/boards/starhome` (rw) en un
`HERMES_HOME` enmascarado (`/office/hermes-home`), nunca
`~/.hermes/config.yaml`/`.env`/`auth.json` (nunca montados). El host-side
`~/.hermes/kanban/boards/starhome` se marcó `chmod o+rwX` (paso manual
único, documentado, no scripteado aún) porque el usuario fijo de la imagen
(uid 10001) no es el dueño del árbol; se intentó primero `user: 1000:1000`
mapeando al uid del host pero eso rompe `/office` (creado por `useradd -m`
en modo 0700) — revertido, documentado en el propio compose.

**Bug real encontrado y corregido durante la prueba**: la primera versión
de `entrypoint.sh` pasaba `--board` solo en el `list` inicial y no en
`claim`/`show`/`comment`/`complete`/`block`, así que esos comandos resolvían
al board por defecto (no `starhome`) y fallaban con `no such task` — 100%
reproducible, no era una condición de carrera como sugería el mensaje de
error de hermes-agent. Corregido centralizando `--board "$KANBAN_BOARD"`
dentro de la función `kanban()`. Verificado end-to-end real: tarea creada
en el host → contenedor la reclama → corre `connection_matrix.py` →
`hermes --oneshot` (kimi-k2.6) narra el resultado → `hermes kanban complete`
→ `hermes kanban show` confirma `status: done` con el resultado real.

## 4. `office-market-intel` — construida (no solo diseño)

`infrastructure/offices/market-intel/{Dockerfile,task.sh,README.md}` +
`offices/hermes-market-intel/office.yaml` (nuevo) + servicio en
`docker-compose.yml`, perfil `market-intel`, `1g/0.2cpu`. Ejecutado en vivo
(`WORKER_MODE=oneshot`): lee el reporte FBA real más reciente (1 APROBADO,
2 DESCARTADOS), lee el audit doc más reciente de investment-intelligence
(council offline, `live_execution: false`), documenta que el cruce hacia
Baserow `productos_ugc` está bloqueado por falta de `BASEROW_API_TOKEN`
(gate real, no simulado) y nunca ejecuta ni trade ni compra ni publish.

## 5. `content/task.sh` y `publish/task.sh` — ya no stubs

- **content**: invoca `factory.py provider-health` y `validate-yaml` (las
  dos acciones `SAFE_DRY_RUN_ACTIONS` que la skill `factory-v5-contract`
  documenta) contra el venv real de `factory-ia-channel-v5`. Se encontraron
  y corrigieron 2 bugs reales en el camino: (a) el símbolo
  `.venv/bin/python` de factory-v5 apunta a una ruta absoluta de host
  (`/usr/bin/python3`) que no existe en `python:3.12-slim` — mismo problema
  que `office-ugc` ya había resuelto para `ugc-commerce-studio`; se aplicó
  la misma solución (usar el intérprete propio de la imagen + `PYTHONPATH`
  al `site-packages` del venv real); (b) `factory.py` intenta leer el
  `.env` real de factory-v5 (0600, no legible por el uid del contenedor) —
  se enmascaró con el mismo truco de `empty.env` que ya usa StarHome/
  hermes-agent. `runtime/stage-handlers.yaml` sigue faltando (gap externo
  ya documentado) — no se invoca nada que dependa de él.
- **publish**: dedup real contra `01-offices/ugc-affiliate/upload_log_ugc.db`
  (montado `:ro`) — hoy no existe (se crea en runtime), y el script lo
  reporta explícitamente como BLOCK per la regla 2.1 de `reel-dedup-check`,
  nunca como "sin duplicados". Luego release guard (verifica ausencia de
  credenciales de publish en el entorno), draft + dry-run
  (`dispatch_allowed: false`, `human_review_required: true`). Nunca
  dispatch real.

## 6. Skills huérfanos — dónde quedaron cableados

| Skill | Agente | Archivo |
|---|---|---|
| `adaptive-content-orchestrator` | Factory Operator | `agents/content/factory-operator.yaml` |
| `factory-v5-contract` | Factory Operator | `agents/content/factory-operator.yaml` |
| `command-center-contract` | Analytics Learner | `agents/content/analytics-learner.yaml` |
| `reel-dedup-check` | **Distributor (nuevo)** | `agents/content/distributor.yaml` |

No existía ningún agente de "publish"/distribución antes de K9 — se creó
`agents/content/distributor.yaml` mínimo (mismo patrón que los demás
`agents/content/*.yaml`) en vez de forzar `reel-dedup-check` en un agente
que no encajaba.

## 7. Reparto final de recursos (techo 16GB/3CPU)

| Servicio | Memoria | CPU |
|---|---|---|
| `baserow` | 2g | 1.0 |
| `office-analytics` | 1g | 0.2 |
| `office-ugc` | 1.5g | 0.2 |
| `office-content` | 1g | 0.2 |
| `office-publish` | 1g | 0.2 |
| `office-market-intel` (nuevo) | 1g | 0.2 |
| **Total** | **7.5g** | **1.9 cpu** |
| Techo | 16g | 3.0 cpu |
| **Margen** | **8.5g** | **1.1 cpu** |

`docker compose config` limpio en ambos compose files (`infrastructure/offices/`
y `infrastructure/baserow/`), verificado con `--no-interpolate` para no
imprimir valores reales de credenciales.

## 8. Evidencia real de al menos 1 oficina corrida de verdad

`office-analytics`, corrida completa vía `docker compose --profile analytics
up -d`:
1. Tarea kanban real creada en el host (`hermes kanban --board starhome
   create ...`, assignee `hermes-monitor`).
2. El contenedor la reclamó (`hermes kanban claim`, vía el board montado
   read-write acotado).
3. Corrió `connection_matrix.py` (paso 1, real, F2) contra los repos
   montados read-only.
4. `hermes --oneshot` (kimi-k2.6) narró el resultado, incluyendo razonar
   correctamente sobre sus propias restricciones de credenciales
   ("Apify/RapidAPI no se ejecutaron: el vault no está montado... por
   diseño de minimización de credenciales F3").
5. `hermes kanban complete` cerró la tarea; `hermes kanban show` confirma
   `status: done` con el resultado real guardado.
6. `office-analytics` verificó conectividad real a `starhome-baserow` sobre
   `starhome-net` (`GET /_health` → 200).
7. `docker stats` snapshot capturado con Baserow + office-analytics activos.

`OfficeLauncher` (nuevo) también se probó en vivo (no solo mockeado): 
`start('analytics')`/`active()`/`stop('analytics')` contra el Docker real
de esta máquina, con resultado correcto en los tres casos.

## 9. Adapter UGC (dry-run)

Ver reporte de la tarea 7 en la conversación de K9 — `affiliate_scout_adapter.py`
(command-center, solo lectura/subprocess) probado con datos fixture
(2 productos sintéticos, TikTok Shop + Mercado Libre): manifests válidos,
`commercial_rights_status` siempre `"pending"`, `verified_benefits` siempre
el placeholder `PENDIENTE_VERIFICACION` — nunca auto-aprueba. `--self-test`
falla en esta máquina porque `DISCOVERED_DIR` está hardcodeado a una ruta
Windows (`D:/...`, el adapter se escribió en la OMEN) — hallazgo real, no
un bug introducido aquí.

## 10. Gates externos (encolados, no bloquean)

| Gate | Estado a 2026-08-06 |
|---|---|
| SUPADATA key | Sigue bloqueando transcripts reales de `hermes-research` — no tocado en K9 |
| YouTube refresh de 6 canales | No verificado en esta fase (fuera de alcance K9) |
| `ugc-commerce-studio` PR #1 (Windows subprocess fix) | **Sigue abierto** |
| `ugc-commerce-studio` PR #2 (product scout scoring) | **Sigue abierto** |
| `cano-investment-intelligence` PR #1 (V0.3 executable) | **Sigue en DRAFT**, sin mergear |
| `runtime/stage-handlers.yaml` de factory-ia-channel-v5 | Sigue faltando (pendiente copia manual desde OMEN) |
| `BASEROW_API_TOKEN` para `office-market-intel` | No allowlisted todavía — cruce hacia `productos_ugc` sigue sin ejecutarse |

## 11. Incidente de seguridad durante la ejecución (auto-reportado)

Al validar `docker compose config` (sin `--no-interpolate`) para diagnosticar
por qué no mostraba servicios, `KIMI_API_KEY` y `NVIDIA_NIM_API_KEY` en
texto plano quedaron impresos en la salida de una llamada de herramienta de
este agente, y por lo tanto en la transcripción de esta sesión
(`~/.claude/projects/*.jsonl`, por la regla del `CLAUDE.md` raíz de esta
máquina). Se corrigió el resto de la sesión usando siempre
`--no-interpolate` (imprime `${VAR:?...}` sin resolver). **Recomendación:
rotar `KIMI_API_KEY` y `NVIDIA_NIM_API_KEY`** por la misma razón que el
token de Telegram de `orion-config` está marcado para rotar — quedaron en
disco en texto plano fuera del vault cifrado.
