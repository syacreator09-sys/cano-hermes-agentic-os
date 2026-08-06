# F11 — Infra Docker: Baserow + 4 oficinas

Fecha: 2026-08-06. Máquina: `cano-HP-280-G2-SFF`, i5-6500 (4 núcleos), 32GB RAM,
sin GPU dedicada, Docker Engine 29.7.1 / Compose v5.4.0.

## 0. Incidente de seguridad — ACCIÓN REQUERIDA

Al validar `infrastructure/offices/docker-compose.yml` corrí
`docker compose --profile analytics config`, que **interpola e imprime los
valores reales** de las variables `${...}` en vez de solo la plantilla. Esto
escribió en texto plano, en esta conversación (y por tanto en
`~/.claude/projects/*.jsonl`, tal como advierte el `CLAUDE.md` raíz), los
valores reales de:

- `KIMI_API_KEY`
- `KIMI_BASE_URL`
- `NVIDIA_NIM_API_KEY` (vía `NVIDIA_API_KEY`)

**Recomendación: rotar esas dos llaves (Kimi/Moonshot y NVIDIA NIM) en cuanto
sea posible**, igual que el token de Telegram pendiente de `orion-config`
documentado en el `CLAUDE.md` raíz. No volví a correr `docker compose config`
en el resto de la fase — toda verificación posterior de variables se hizo
leyendo el YAML fuente (que solo contiene `${NOMBRE}`, nunca el valor) o con
`awk`/`grep` que confirman presencia sin imprimir contenido.

## 1. Hallazgo previo — F3/F4 nunca llegaron a `main`

Antes de tocar Docker, `subprocess_executor.py` (para el aislamiento por
tier que este mandato pide revisar) no tenía la lógica de allowlist descrita
en el plan, y `ApprovalRequest` no tenía los campos
`motivo/costo_estimado_usd/presupuesto_restante/canal/evidencia` que F11
asume como ya construidos por F3. Investigando: `main` divergió de
`a8d0c6d` directo a F5 (Personal Runtime) → F10, saltándose F3
(`feat/prometeo-wiring`) y F4 (`feat/prometeo-forge`) — commits reales que
existían, completos y con tests, pero solo en ramas nunca fusionadas
(aunque F3/F4 están marcados `completed` en el tracker).

Fusioné `feat/prometeo-forge` (que ya incluye F3) en `main` — merge limpio,
sin conflictos, suite completa (`python -m unittest discover -s tests` /
`pytest`) en verde después. Commit `0209e43`. Esto trajo lo que F11 de verdad
necesitaba: `EXECUTOR_SECRET_ALLOWLIST` en `subprocess_executor.py`,
`ContainerSandboxExecutor` (F3, `mem_limit=512m`/`cpus=1` — el "sandbox con
su propio límite" que este mandato dice no contar en el presupuesto de F11),
`scripts/connection_matrix.py`, y el `ApprovalRequest` real que la tabla
`solicitudes` de Baserow espeja abajo.

## 2. Baserow

- **URL local**: `http://localhost:8085` (bind solo a `127.0.0.1`).
- **Imagen**: `baserow/baserow:1.31.1`, all-in-one (Postgres+Redis+Django+
  Nuxt+Celery en un contenedor, dato persistente en el volumen nombrado
  `starhome_baserow_data`).
- **Límites**: `mem_limit: 2g`, `cpus: 1.0` (`infrastructure/baserow/docker-compose.yml`).
- **4 tablas creadas** (workspace "StarHome Prometeo" id 29, database id 34),
  vía `infrastructure/baserow/setup_schema.py` (stdlib-only, sin `requests`
  — no está en el venv del repo):
  - `solicitudes` — espejo exacto de `ApprovalRequest` (F3): `motivo`,
    `costo_estimado_usd`, `presupuesto_restante`, `canal`, `evidencia`,
    `requested_by`, `status` (select: pending/approved/rejected), más
    `task_id`/`created_at`.
  - `gastos` — fecha, oficina, concepto, monto_usd, aprobado_por, solicitud_id.
  - `productos_ugc` — nombre, canal, precio_mxn, comision_mxn, score, fuente,
    url, estado.
  - `metricas_diarias` — fecha, oficina, metrica, valor, nota.
- Verificado con una fila de prueba real vía API (`POST
  /api/database/rows/table/130/...`) y confirmado que **sobrevive un
  restart del contenedor** (Postgres corrió "No migrations to apply" al
  recrear, y la fila de prueba seguía ahí).
- **Token**: generado (`f11-office-analytics`, scope: la database de
  Prometeo), guardado en `~/.secrets/credenciales/credenciales/.env` como
  **`BASEROW_TOKEN`** (línea nueva, añadida con `>>`, archivo no
  reescrito). El vault **ya tenía** `BASEROW_API_TOKEN`, `BASEROW_API_URL`,
  `BASEROW_MCP_URL`, `BASEROW_SECRET_KEY`, `BASEROW_DB_PASS` con valores
  reales de antes — no los toqué ni los dupliqué (no sé a qué instancia
  apuntan; si es otra cosa, vale la pena que Cano revise si siguen vigentes).
  El archivo temporal con el token en texto plano
  (`infrastructure/baserow/baserow_api_token.txt`) se sobrescribió con
  `shred -u` inmediatamente después de copiarlo al vault.
- Quedaron 2 workspaces huérfanos (ids 13 y 23) de dos intentos previos del
  script que fallaron por endpoints REST equivocados antes de dar con la
  ruta correcta (`/api/applications/workspace/{id}/`,
  `/api/database/tables/database/{id}/`) — vacíos, sin tablas, cosmético,
  no limpiados por falta de tiempo.

## 3. Las 4 oficinas

Patrón común: `starhome/office-base:latest` (`python:3.12-slim`, usuario no-root
uid 10001, `tini` como PID 1) + `task.sh` propio + supervisor `hermes
--oneshot` compartido (`infrastructure/offices/common/entrypoint.sh`).
`hermes` **no se instala** en la imagen — se monta de solo lectura desde el
host en la ruta absoluta exacta donde vive (`/home/cano/repos/hermes-agent` +
`~/.local/share/uv/python`), porque su venv es una instalación editable (PEP
660) cuyo finder tiene hardcodeado ese path de origen. Validado primero en
host desnudo (`env -i` con solo `HOME`/`PATH`/`KIMI_API_KEY`/`KIMI_BASE_URL`)
antes de dockerizar, y confirmado igual dentro de contenedor.

| Oficina | Estado | Evidencia |
|---|---|---|
| **office-analytics** | **Corrida end-to-end, real** | `scripts/connection_matrix.py` (F2, sin modificar) corrido dentro del contenedor contra 2 de los 5 sistemas (StarHome + hermes-agent montados `:ro`; los otros 3 deliberadamente no montados — minimización de credenciales, ver §5); reporte real escrito en `infrastructure/offices/data/analytics/reports/connection-matrix-2026-08-06.md`; `hermes --oneshot` (kimi-k2.6) resumió el resultado real, incluyendo un error real que detectó (vaults Apify/RapidAPI ausentes) sin inventar cifras. |
| **office-ugc** | **Corrida end-to-end, real** | `ugc-commerce-studio`'s `python -m ugc_commerce.cli plan --product examples/product.json --profile examples/profile.json` — el mismo comando que el dry-run de F9 ya validó en host — corrido dentro del contenedor: `opportunity.score=85.0`, `recommendation=PREMIUM_PRODUCTION`, 5 escenas, `auto_publish=false`, `human_review_required=true`. Cero red, cero Higgsfield, `$0`. `hermes --oneshot` narró el resultado correctamente. |
| **office-content** | Diseño + Dockerfile/compose completos, **no corrida end-to-end** | Build verificado (`docker compose --profile content build` → OK). `task.sh` es un stub honesto: monta `factory-ia-channel-v5` `:ro` y explícitamente **no** invoca `scripts/factory.py` real porque `runtime/stage-handlers.yaml` sigue faltando en ese repo (gap documentado por `skills/factory-v5-contract/SKILL.md`, no inventado aquí). Ver `infrastructure/offices/content/README.md`. |
| **office-publish** | Diseño + Dockerfile/compose completos, **no corrida end-to-end** | Build verificado. `task.sh` es un stub que solo describe la cadena `dedup → release guard → draft → dry-run → gate humano → dispatch → ledger`; **nunca recibe credenciales de publicación real** (verificado, ver §5). Ver `infrastructure/offices/publish/README.md`. |

Bugs reales encontrados y corregidos en el camino (documentados en los
propios archivos, no solo aquí):
- `hermes_cli` crashea con `PermissionError` si monta un `.env` 0600 que el
  usuario del contenedor no puede leer (afecta tanto al `.env` de
  `hermes-agent` como al de este mismo repo) — resuelto montando un archivo
  vacío (`common/empty.env`) encima de esa ruta específica, no dando acceso
  real a esos `.env`.
- `ugc-commerce-studio/.venv/bin/python3` apunta a `/usr/bin/python3`
  (convención Ubuntu del host); `python:3.12-slim` pone Python en
  `/usr/local/bin` — el symlink del venv no resuelve dentro del contenedor.
  Solución: reusar el intérprete `python3.12` de `office-base` (misma minor
  version que el venv del repo → wheels compiladas ABI-compatibles) con
  `PYTHONPATH` apuntando a `src/` + `site-packages` del venv montado, en vez
  de invocar el `python3` del venv directamente.
- `connection_matrix.py` (F2) escribe su reporte en una ruta hardcodeada
  dentro del propio repo (`REPO_ROOT/reports/...`) — con el repo montado
  `:ro` eso falla. Solución: overlay de un subdirectorio específico como
  `:rw` encima del mount `:ro` general, en vez de tocar el script F2 ya
  cerrado.

## 4. `docker stats` real y decisión sobre Coolify

Snapshot con Baserow + office-analytics corriendo a la vez (arrancado con
`docker compose --profile analytics up`, sin `-d`, midiendo mientras
ejecutaba su ciclo real):

```
CONTAINER            CPU %    MEM USAGE / LIMIT    MEM %    PIDS
starhome-baserow      50-100%  1.75-1.78GiB / 2GiB   87-89%   67
office-analytics      2-20%    37-129MiB / 1GiB      4-13%    5-7
```

Lecturas:
- **Baserow, en reposo con actividad ligera, ya usa ~88% de su propio
  límite de 2GB** — el all-in-one (Postgres+Redis+Django+Celery×3+Nuxt+
  Caddy, todo en un proceso supervisado) es pesado de por sí; no es holgura
  falsa, es su huella real.
- Las oficinas son ráfagas cortas (ciclo completo en 15-25s), no daemons:
  su uso real medido (~40-130MB) queda muy por debajo de sus límites
  declarados (1-1.5GB) porque el contenedor vive segundos, no porque el
  límite esté mal puesto — el límite existe para el peor caso, no para el
  caso típico.
- Extrapolando las 4 oficinas corriendo a la vez (caso que el plan pide NO
  hacer por defecto, pero hay que poder responder "cabría"): suma de
  límites declarados = Baserow 2g/1cpu + 4×(~1-1.5g/0.2cpu) = **6.5g/1.8cpu**,
  bajo el techo de 8GB/2CPU pedido — con 1.5GB/0.2cpu de margen nominal.
  Pero ese margen nominal ya está mayormente consumido por Baserow solo en
  la práctica (1.78 de 2GB reales), y el host solo tiene 4 núcleos en
  total, de los cuales 2 son para *todo* el resto (StarHome API nativo,
  Hermes gateway, esta misma sesión de Claude Code) además de la
  infraestructura Docker.

**Decisión: diferir Coolify** (comportamiento por defecto del mandato salvo
margen "muy holgado" — no lo es). Coolify recomienda ~2-4GB/algo de CPU
propio para su propia pila (app+Postgres+Redis+proxy); añadirlo hoy
significaría o romper el techo de 8GB/2CPU, o recortar el ya ajustado
presupuesto de Baserow/oficinas para hacerle espacio. Con Baserow solo
usando el 88% de su límite en reposo, no hay margen real que sostenga
sumar otra pila de servicios ahora mismo.

## 5. Reparto final de `mem_limit`/`cpus`

| Servicio | mem_limit | cpus | Notas |
|---|---|---|---|
| baserow | 2g | 1.0 | uso real medido ~1.78g (88%) |
| office-analytics | 1g | 0.2 | uso real medido ~130MiB |
| office-ugc | 1.5g | 0.2 | uso real no medido en `docker stats` conjunto (sí corrida end-to-end por separado) |
| office-content | 1g | 0.2 | no corrida (diseño) |
| office-publish | 1g | 0.2 | no corrida (diseño) |
| **total** | **6.5g** | **1.8** | ≤ 8g/2cpu ✓ |
| container-sandbox (F3, referencia, no contado aquí por instrucción explícita) | 512m | 1.0 | ya existente, fuera del alcance de F11 |

## 6. Confirmación de allowlist de credenciales por contenedor

Verificado leyendo el **YAML fuente** de `docker-compose.yml` (nunca
`docker compose config`, ver §0) — cada servicio solo declara estos
*nombres* de variable:

- **office-analytics**: `HERMES_MODEL`, `HERMES_PROVIDER`, `HERMES_TOOLSETS`,
  `KIMI_API_KEY`, `KIMI_BASE_URL`, `NVIDIA_API_KEY`, `OFFICE_NAME`. Nada más.
- **office-ugc**: lo mismo + `RAPIDAPI_KEY`, `APIFY_API_KEY` (allowlisted
  para su función de scraping/tracking aunque el `task.sh` de hoy, basado en
  fixtures offline, todavía no las usa).
- **office-content**: lo mismo que analytics (tier 0 solo).
- **office-publish**: lo mismo que analytics (tier 0 solo) — **sin ninguna
  variable `UPLOAD_POST_*`/`TIKTOK_*`/`META_*`/`YOUTUBE_*`**, confirmado por
  ausencia en el archivo fuente. El dispatch real queda fuera de este
  contenedor por diseño, gateado por `ApprovalService` (F3).

Ninguna oficina recibe el `.env` de StarHome, de hermes-agent, ni de ningún
otro sistema por bulk-injection (`env_file` a nivel de servicio no se usa en
ningún lado de `infrastructure/offices/docker-compose.yml`) — todo pasa por
`environment:` explícito, mismo espíritu que
`EXECUTOR_SECRET_ALLOWLIST` en `cano_hermes/runtimes/subprocess_executor.py`
(F3), trasladado a la capa Docker.

## 7. Systemd

`infrastructure/systemd/baserow.service` (nuevo, checked-in) instalado en
`~/.config/systemd/user/baserow.service`, habilitado
(`systemctl --user enable`) y arrancado — mismo patrón que
`starhome-os.service`/`hermes-gateway.service` ya en esta máquina (unidad de
usuario, no de sistema; sin `Requires=docker.service` porque eso no resuelve
desde un manager `--user`, confirmado por error real al intentarlo). Las 4
oficinas **no** llevan unidad systemd, por diseño (bajo demanda).

## 8. Bloqueos / lo que queda incompleto — honesto

1. **Rotar `KIMI_API_KEY`/`NVIDIA_NIM_API_KEY`** — ver §0, es lo más urgente
   de todo este reporte.
2. **office-content y office-publish son diseño, no ejecución real** — el
   primero bloqueado por el gap ya conocido de `stage-handlers.yaml`
   (externo, no se inventó nada); el segundo, por tiempo — conectar el
   `task.sh` real de publish a `ApprovalService` vía la API de StarHome
   desde dentro de un contenedor es trabajo de diseño real que no alcanzó.
3. **2 workspaces huérfanos vacíos en Baserow** (ids 13, 23) de intentos
   fallidos del script — cosmético, seguro dejarlos o borrarlos a mano.
4. **`BASEROW_API_TOKEN`/`BASEROW_API_URL`/`BASEROW_MCP_URL` preexistentes
   en el vault, con valores reales, de origen desconocido para mí** — no
   tocados, pero vale la pena que Cano confirme si son de una instancia
   distinta (¿nube, otra máquina?) o son restos de un intento anterior de
   esta misma fase.
5. **office-ugc solo prueba el tramo offline/fixture** (`ugc_commerce.cli
   plan`) — el pipeline completo de 6 etapas de command-center
   (scraper→scout→orchestrator→daily-producer→performance-tracker→
   sales-dashboard) no está conectado al contenedor; es exactamente lo que
   F9 ya dejó documentado como "diseño de conexión, aún no construida", y
   sigue así.
6. **`docker stats` conjunto solo se midió con office-analytics**, no con
   las 4 a la vez (el mandato pide extrapolar, no correr las 4 juntas por
   defecto — ver §4).
