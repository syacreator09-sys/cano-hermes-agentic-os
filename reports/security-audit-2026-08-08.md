# Auditoría de seguridad — cano-hermes-agentic-os — 2026-08-08

Plan AUTONOMÍA TOTAL A6. Metodología: (1) `factory run` de AAH en perfil **PRO**
(`--guardian locked`) — primera prueba real de PRO, no solo LITE; (2) revisión manual
complementaria (superficies de red, permisos, secretos, `semgrep`).

## 1. AAH PRO — auditoría automatizada

_(corrida `RUN-20260808-002`; `RUN-20260808-001` quedó abierta en fase
`evaluating` con `RUBRIC.json`/`FINDINGS.json` corruptos — texto placeholder,
no JSON válido — y nunca cerró. Esta sección documenta el trabajo real de
auditoría hecho a mano por el rol `builder` de `RUN-20260808-002` sobre el
mismo alcance, ya que `RUN-20260808-002` tampoco generó su propio
`SPEC.md`/`RUBRIC.json` — gap de orquestación reportado por separado en
`run_dir/FINDINGS.md`. Herramientas usadas: solo lectura — `grep`/`read`/
`ls`/`cat`/`wc`/`find`, ningún cambio a código de producto.)_

### Resumen ejecutivo

| Severidad | Cuenta |
|---|---|
| Crítica | 0 |
| Alta | 1 |
| Media | 2 |
| Baja | 3 |
| Informativa | 4 |
| Confirmado sin hallazgo (dominios completos) | A1-A4, C3, C4, C5, C6, D1-D5, E1-E9 |

### A. Secretos expuestos — sin hallazgos

- **A1** [Confirmado] Sin literales de credenciales reales hardcodeadas en
  el árbol trackeado (excluyendo `.venv/`). Único hit real de los patrones
  de `API_KEY|SECRET|TOKEN|PASSWORD=...` y prefijos de proveedor
  (`sk-ant-`, `sk-`, `ghp_`, `xox[baprs]-`, `AKIA`, bloques PEM):
  `tests/test_k7_kanban_events.py:58` — `SECRET = "test-secret-do-not-use-in-prod"`,  # pragma: allowlist secret
  fixture de test intencional, no un secreto real.
- **A2** [Confirmado] `.gitignore:1,17,42-44` excluye `.env`, `secrets/`,
  `*.pem`, `*.key` — coincide con los carriers reales presentes en disco.
- **A3** [Confirmado] `.env.example` contiene solo valores vacíos/placeholder.
- **A4** [Confirmado] `scripts/check_staged_secrets.py:33-45` + raíz
  `.pre-commit-config.yaml` — 6 patrones específicos (AWS, Anthropic, OpenAI,
  Slack, Telegram, bloque PEM) más un catch-all genérico, con escape hatch
  `# pragma: allowlist secret` y allowlist por sufijo de ruta. Activo.
- **A5** [No verificable — fuera de alcance de herramientas esta corrida]
  Historial completo de git (`git log --all -p -- .env`) requiere acceso a
  `git`/bash con permisos ampliados. Mismo límite ya declarado por el SPEC
  de `RUN-20260808-001`, sigue aplicando.

### B. Dependencias inseguras

- **B1** [Informativo — corrige a `RUN-20260808-001`] `pyproject.toml:11-20`:
  7 dependencias directas + 3 de `dev`. La nota de evidencia de
  `RUN-20260808-001` ("rangos de versión solo con cota inferior") es
  **inexacta** contra el archivo actual — todas las dependencias listadas
  (`fastapi>=0.115,<1`, `pydantic>=2.8,<3`, `PyYAML>=6.0,<7`, etc.) sí tienen
  cota superior. Se corrige aquí para no propagar el error.
- **B2** [BAJA] Sin lockfile (`*.lock`, `requirements*.txt` pinneado, salida
  de `pip-compile`/`uv lock`) en la raíz del repo — la reproducibilidad de
  build depende de la resolución de versiones en el momento de instalar, no
  de un snapshot fijado. Recomendación: agregar `pip-compile`/`uv lock` como
  follow-up no bloqueante.
- **B3** [MEDIA] `.github/workflows/starhome-quality.yml` corre
  `pip install -e '.[dev]'` + `scripts/validate.py` + `pytest` + `ruff check`
  (este último acotado a 3 archivos, no al árbol completo) — **sin ningún
  paso de escaneo de vulnerabilidades de dependencias** (`pip-audit`,
  `safety`, CodeQL) y **sin `.github/dependabot.yml` ni configuración
  Renovate** en todo el repo (confirmado: no existe). Recomendación: agregar
  `pip-audit` al workflow y/o habilitar Dependabot para `pip`.
- **B4** [Confirmado] Ninguna dependencia declarada con rango sin cota
  superior (ver B1) — sin riesgo de "unbounded range" detectado.
- **B5** [No verificable — fuera de alcance] Matching de CVE en vivo contra
  versiones resueltas requiere acceso de red; no disponible esta corrida.

### C. Problemas de trust-boundary (superficie FastAPI)

- **C1** [ALTA] `cano_hermes/api/app.py` declara 45 rutas; **44 de 45 no
  tienen ningún mecanismo de autenticación/autorización** (sin `Depends()`
  de auth, sin header de API key, sin verificación de token) — incluyendo
  endpoints de mutación sensibles: `POST /api/orders` (línea 130),
  `POST /api/orders/{order_id}/dispatch` (169),
  `POST /api/approvals/{approval_id}/resolve` (292),
  `POST /api/tasks/{task_id}/execute` (312),
  `POST /api/forge/candidates/{candidate_id}/promote` (395),
  `POST /api/memory/candidates/{candidate_id}/resolve` (440),
  `POST /api/finance/close` (647). La única excepción es
  `POST /api/bridge/kanban-events` (242), protegida por HMAC (ver C3).
  **Mitigante real confirmado**: el path de despliegue documentado y activo
  (`infrastructure/systemd/cano-hermes.service:8` —
  `--host 127.0.0.1 --port 8000`; `Makefile:16` — `uvicorn ... --port 8787`
  sin `--host`, que por defecto de uvicorn es `127.0.0.1`) ata la API a
  loopback, así que hoy no es alcanzable desde la red. **Pero** el
  `docker-compose.yml` raíz (`ports: ["8000:8000"]`, sin IP de bind — Docker
  publica eso como `0.0.0.0:8000` por defecto) y el `Dockerfile`
  (`CMD [...,"--host","0.0.0.0",...]`) exponen la MISMA API sin autenticación
  a toda la LAN si ese path de despliegue llega a usarse — contraste directo
  con `infrastructure/baserow/docker-compose.yml:29` que sí ata
  explícitamente a `127.0.0.1:8085:80`. Recomendación: (a) agregar
  autenticación mínima (API key por header) a los endpoints de mutación
  antes de que el compose raíz sea un path de despliegue soportado, o (b)
  documentar explícitamente que `docker-compose.yml` raíz es solo para
  desarrollo local detrás de un firewall y atar su `ports:` a `127.0.0.1`
  igual que baserow.
- **C2** [BAJA/Informativa] `CORS_ALLOW_ORIGINS` está declarada como env var
  (`.env.example`, catálogo de env del proyecto) pero **no se usa en
  ningún lugar de `cano_hermes/`** — no hay `CORSMiddleware` registrado en
  `app.py`. No es una vulnerabilidad (el comportamiento por defecto sin CORS
  es más restrictivo, no menos: los navegadores aplican same-origin), pero
  es higiene de configuración — la variable es "dead config" que puede
  confundir a un operador que asuma que está en efecto.
- **C3** [Confirmado] `cano_hermes/bridge/inbound.py:88-95`
  (`verify_signature`) — HMAC-SHA256 sobre el body crudo
  (`app.py:264` — `await request.body()` antes de parsear JSON),
  comparación en tiempo constante (`hmac.compare_digest`), falla cerrado si
  `secret`/`signature` están vacíos (`if not secret or not signature: return False`,
  sin modo "saltar verificación").
- **C4** [Confirmado] `cano_hermes/domain/models.py:154-170`
  (`OrderCreate`) no declara `status`/`subtask_ids`/`aggregate_artifact` —
  `app.py:130-141` (`create_order`) reconstruye `OrderRecord` solo desde
  `objective`/`source`/`budget`/`domain`, sin forma de que el caller
  inyecte esos campos. El claim del docstring es exacto.
- **C5** [Confirmado] Guardia anti-autoaprobación aplicada en dos lugares
  independientes: `cano_hermes/governance/approvals.py:54-55`
  (`if approval.requested_by == actor: raise PermissionError(...)`) y
  `cano_hermes/governance/memory_candidates.py:86-87` (misma guardia para
  memory candidates). El motor de auto-aprobación
  (`auto_approval.py:198-209`) captura ese mismo `PermissionError` y lo
  trata como "condición no cumplida", nunca lo bypasea.
- **C6** [Confirmado, con nota menor] Revisados los `HTTPException(detail=...)`
  de `app.py` — la mayoría usa strings fijos ("Order not found", etc.).
  Dos sitios (`app.py:225`, `dispatch_order`; y equivalentes en 377/379/402/404)
  usan `detail=str(exc)` sobre excepciones de dominio acotadas
  (`KanbanBridgeError`, `PermissionError`, `DuplicateCandidateError`), no
  tracebacks crudos ni `settings.*`. Nota menor no bloqueante: confirmar que
  `KanbanBridgeError` nunca envuelve stderr crudo del CLI de hermes (que
  podría, en teoría, incluir rutas del filesystem) — no se encontró
  evidencia de que lo haga, pero no se auditó cada rama de
  `kanban_bridge.py` línea por línea esta corrida.

### D. Docker / hardening de contenedores

- **D1** [Confirmado] `docker-compose.yml` raíz y los 5 servicios de
  `infrastructure/offices/docker-compose.yml` (analytics, ugc, content,
  publish, market-intel) declaran `security_opt: ["no-new-privileges:true"]`
  y `cap_drop: ["ALL"]`.
- **D1-baserow** [MEDIA] `infrastructure/baserow/docker-compose.yml:36-38`
  tiene `security_opt: [no-new-privileges:true]` pero **le falta
  `cap_drop: ["ALL"]`** — inconsistente con los otros 6 servicios del stack
  (hermes + 5 offices), que sí lo tienen. Imagen de terceros
  (`baserow/baserow:1.31.1`), así que el riesgo real depende de qué
  capacidades usa esa imagen internamente, pero es una brecha de defensa en
  profundidad frente al patrón ya establecido en el resto del repo.
- **D2** [Confirmado] Ningún servicio monta `/var/run/docker.sock` en
  ningún `docker-compose*.yml` del repo (barrido completo, cero hits).
- **D3** [Confirmado] Ningún servicio usa `privileged: true` (barrido
  completo, cero hits).
- **D4** [Confirmado] Los 5 servicios de offices montan
  `./agents:/app/agents:ro` y `./skills:/app/skills:ro` de solo lectura; los
  5 tienen además `read_only: true` a nivel de contenedor. El servicio
  `hermes` raíz monta `storage/`/`vault/` de escritura (necesario, es donde
  persiste) pero `agents/`/`skills/` igual como `:ro`.
- **D5** [Confirmado] `Dockerfile` — base `python:3.12-slim`, sin `ADD` de
  URLs remotas, sin `COPY .env` ni literales de credenciales en `ENV`/`ARG`.
  No fija usuario explícitamente (corre como root por defecto de la imagen
  base) — no se encontró justificación documentada en el `Dockerfile` mismo;
  mitigado parcialmente por `security_opt`/`cap_drop` del compose que lo
  envuelve, pero sería más correcto agregar un `USER` no-root explícito.
- **D6** [Informativo — no es un hallazgo, corrige el framing del SPEC de
  `RUN-20260808-001`] `Dockerfile` fija `HERMES_EXECUTION_MODE=dry_run`
  mientras `cano_hermes/config.py:30` tiene default `"supervised"`. Esto
  **no debilita** el gate de aprobación — es lo opuesto: `dry_run` hace que
  `CommandExecutor.execute()` (`subprocess_executor.py`) nunca ejecute
  subprocesos reales, solo simule (`status="simulated"`), así que la imagen
  Docker arranca en el estado más conservador posible (no-op) hasta que se
  sobreescriba explícitamente vía `.env`/environment en el deploy. Divergencia
  intencional y más segura, no una regresión.

### E. Regresiones de seguridad comunes (checklist Python/FastAPI/Docker)

Barrido completo sobre `cano_hermes/` + `scripts/` (excluyendo `.venv/`):

- **E1** `shell=True` — cero coincidencias.
- **E2** `eval(`/`exec(` sobre input externo — cero coincidencias (excluyendo
  `execute`/`executor`/`exec_module`, que no son la función builtin).
- **E3** `pickle.load`/`pickle.loads` — cero coincidencias.
- **E4** `yaml.load(` sin `Loader=SafeLoader`/`safe_load` — cero
  coincidencias.
- **E5** `os.system(` — cero coincidencias.
- **E6** SQL por f-string/`%`/`.format()` — `cano_hermes/storage/sqlite.py`
  usa exclusivamente placeholders parametrizados `?` (27 sitios
  `.execute()` revisados, muestra en líneas 34-209); cero interpolación de
  string en sentencias SQL.
- **E7** `debug=True` en FastAPI/uvicorn — cero coincidencias.
- **E8** Construcción de rutas de filesystem desde input de usuario sin
  normalización — no se encontró ningún endpoint que construya un `Path`
  directamente desde un parámetro de request sin pasar antes por un
  store/ID interno (los `{task_id}`/`{order_id}`/`{candidate_id}` de las
  rutas se usan como claves de lookup en el store, no como componentes de
  ruta de filesystem).
- **E9** [Confirmado] `subprocess_executor.py:26-42`
  (`EXECUTOR_SECRET_ALLOWLIST`) — cada executor (`claude-code`, `codex`,
  `hermes-agent`, `openclaw`, `container-sandbox`, `aah`) recibe solo sus
  credenciales listadas; `build_env()` (línea 59-66) primero elimina TODO lo
  que matchea `SECRET_NAME_PATTERN` de `os.environ` y luego restaura solo
  lo permitido — nunca se pasa `env=os.environ` completo a
  `asyncio.create_subprocess_exec` (línea 93, confirmado que siempre recibe
  el `env` filtrado). Sin instancias hermanas del gap K12 ya documentado en
  `SECURITY.md`.

### F. Consistencia de documentación y política

- **F1** [BAJA] `SECURITY.md:164` enlaza a `docs/SECURITY.md` ("la política
  técnica ampliada") — **ese archivo no existe** (confirmado, `docs/`
  tiene 22 archivos pero ninguno se llama `SECURITY.md`). Referencia rota,
  higiene de documentación, no una vulnerabilidad.
- **F2** [Confirmado, parcial] De los claims de `SECURITY.md` §K12
  verificados esta corrida (guardia de autoaprobación, HMAC del puente,
  hardening de contenedores, allowlist de secretos por executor) — todos
  coinciden con el código actual. No se verificó línea por línea el 100% de
  `SECURITY.md` (documento extenso); los claims fuera de las secciones
  citadas en el SPEC no se auditaron esta corrida.

### Fuera de alcance esta corrida (requieren herramientas/autorización ampliadas)

- Escaneo completo de historial de git para secretos (`git log --all -p`) —
  necesita `git`/bash con permisos ampliados.
- Matching de CVE en vivo contra versiones resueltas (`pip-audit`, OSV,
  GitHub Advisory DB) — necesita acceso de red.
- Escaneo de imagen de contenedor (`trivy`, `grype`) — necesita ejecución
  de Docker.
- Pruebas dinámicas (fuzzing de endpoints, intentos reales de bypass de
  auth contra una instancia corriendo) — necesita un servidor en ejecución
  y es un engagement de mayor riesgo que requiere aprobación separada.

### Nota de proceso (para el orquestador, no un hallazgo de seguridad)

Ni `RUN-20260808-001` ni `RUN-20260808-002` produjeron un `SPEC.md`/
`RUBRIC.json` válido en su propio `run_dir` pese a que `STATE.json` registra
las transiciones `planning`→`architecture` como completadas en ambas
corridas. `RUN-20260808-001` además dejó `RUBRIC.json`/`FINDINGS.json` con
el literal `<see top-level ... key above — identical content>` en vez de
JSON real. El trabajo de esta sección se hizo igual, citando evidencia real
en vez de asumir un PASS, pero **no fue calificado contra un `RUBRIC.json`
válido de esta corrida** — el gate final de AAH no debe tratarlo como
auto-aprobado. Detalle completo en `run_dir/FINDINGS.md` de
`RUN-20260808-002`.

## 2. Superficies de red locales

| Puerto | Servicio | Bind | Evaluación |
|---|---|---|---|
| 8787 | StarHome API (`starhome-os.service`) | `127.0.0.1` | Correcto — solo local. |
| 8085 | Baserow | `127.0.0.1` | Correcto — solo local. |
| 8000 | `cano-invest-api` (repo **distinto**: `cano-investment-intelligence`) | `0.0.0.0` | Ver hallazgo #30 abajo — **no es un bug, es un tradeoff ya documentado**. |

### Hallazgo — bind 0.0.0.0:8000 (pendiente #30)

**Severidad: baja/informativa (mitigación real requiere `sudo`, es de Cano).**

Investigado antes de proponer un "arreglo": `~/.config/systemd/user/cano-invest-api.service`
ya documenta por qué es `0.0.0.0` — cambiado deliberadamente de `127.0.0.1` en P3-B
(plan POTENCIA, 2026-08-07) para que el contenedor Docker `office-market-intel`
(red `starhome-net`, gateway `172.21.0.1`, alcanza el host vía
`host.docker.internal:host-gateway`) pueda consultarlo — un bind solo-loopback es
inalcanzable desde un bridge Docker aunque se use `extra_hosts`.

Casi revierto esto a `127.0.0.1` (el único consumidor que vi primero,
`cano_hermes/orchestration/dashboards.py:1293`, usa `127.0.0.1:8000` porque StarHome
corre nativo, no en Docker) — habría sido un error: habría roto la oficina
market-intel la próxima vez que se lance ese contenedor. **No se tocó.**

Mitigación real evaluada: `uvicorn` no soporta bind a dos direcciones específicas
(`127.0.0.1` + la gateway `172.21.0.1`) en un solo proceso sin duplicar el servicio;
la alternativa correcta es una regla `ufw` que restrinja el puerto 8000 a
`127.0.0.1/32` + `172.21.0.0/16` — **requiere `sudo`, exactamente como el plan ya
anticipaba ("ufw necesita sudo→Cano")**. Todos los endpoints siguen siendo
read-only/paper-only (`verify.sh` afirma `/v1/orders/live` → 404, según el propio
comentario del unit file). Queda en la lista de pendientes de Cano, no como bug.

## 3. Permisos de vault/perfiles

- `~/.secrets/credenciales/credenciales/.env`: `600 cano` — correcto.
- `~/.hermes/` (directorio): `700 cano` — correcto, bloquea todo acceso de
  grupo/otros incluso antes de llegar a los archivos internos.
- `~/.hermes/profiles/*/config.yaml`: encontrados en `664` (grupo/otros con lectura)
  — sin explotación real posible ya que el directorio padre (`700`) ya bloquea el
  acceso, pero es defensa en profundidad débil. **Arreglado en el acto** (`chmod 600`
  en los 7 archivos) — cambio trivial, sin reinicio de servicio necesario, sin
  contenido sensible expuesto en ningún caso (verificado: ningún `config.yaml`
  contiene valores de secreto, solo `platform_toolsets`/comentarios).

## 4. Scan de secretos sobre lo commiteado en esta sesión (A0-A5)

- `git diff` de los 7 commits de hoy (`bf29f93`..`d87b1f9`) contra patrones de
  `api_key=`/`token=`/`secret=`/`sk-...`/`ghp_...`: **cero coincidencias reales**
  (solo el literal de test `"fake-token"`, intencional).
- El hook de pre-commit propio del repo (`check for staged secrets (K12)`) ya pasó
  en los 7 commits, de forma independiente.
- Scan amplio (no solo el diff de hoy) sobre todo el árbol trackeado por patrones de
  credencial hardcodeada: **cero coincidencias**.
- `grep` de `shell=True`, `os.system(`, `eval(`, `exec(` (fuera de `execute`/
  `executor`/`exec_module`), `pickle.loads`, `yaml.load(` sin `safe_load`: **cero
  coincidencias** en `cano_hermes/`/`scripts/`.

## 5. `semgrep --config auto`

15 hallazgos totales sobre `cano_hermes/` + `scripts/`:

- **14×** `python.lang.security.audit.dynamic-urllib-use-detected` — regla de
  auditoría (confianza baja por diseño: cualquier `urlopen()` con una URL no-100%-
  literal la dispara). Triage manual de cada sitio: todas construyen la URL desde
  **datos internos de confianza** (endpoints de validadores hardcodeados en
  `scripts/validators/__init__.py`, o `INVEST_API_BASE_URL = "http://127.0.0.1:8000"`
  fijo en `dashboards.py`), nunca desde entrada externa/de usuario. **Falsos
  positivos**, documentados aquí en vez de descartados en silencio.
- **1×** `python.sqlalchemy.performance.performance-improvements.len-all-count` —
  sugerencia de rendimiento, no de seguridad.

## 6. Veredicto

Sin hallazgos críticos. **Un hallazgo ALTA real (C1, sección 1)**: 44/45 rutas de
`cano_hermes/api/app.py` sin autenticación — mitigado hoy porque el path de
despliegue activo (systemd, `127.0.0.1`) no es alcanzable desde la red, pero
`docker-compose.yml` raíz lo habría expuesto a toda la LAN sin auth si se llega a
usar ese path. **Arreglado en el acto** (parte segura, sin decisión de Cano
necesaria): `docker-compose.yml` ahora ata el puerto a `127.0.0.1:8000:8000`
(antes sin bind explícito → `0.0.0.0` por defecto de Docker), igual que
`infrastructure/baserow/docker-compose.yml` ya hacía — cambio sin efecto en nada
que corra hoy, ya que ese compose no es el path de despliegue activo. **Queda
pendiente de decisión de Cano**: agregar autenticación real (API key por header)
a los endpoints de mutación antes de que ese compose sea un path de despliegue
soportado — eso sí es una decisión de diseño (mecanismo de auth, dónde vive la
credencial), no algo para decidir solo.

Un hallazgo MEDIA no tocado (D1-baserow, falta `cap_drop: ["ALL"]"`) — imagen de
terceros **corriendo en vivo hoy**; aplicar `cap_drop` sin verificar qué
capacidades usa internamente arriesga romper un servicio activo (métricas K14),
así que queda como recomendación documentada, no como fix automático.

Un hallazgo bajo arreglado en el acto (permisos de perfiles). Un hallazgo
informativo (#30) confirmado como tradeoff deliberado ya documentado, con la
mitigación real correctamente identificada como tarea de Cano (requiere `sudo`).
Catorce falsos positivos de `semgrep` triados y explicados, no descartados sin
evidencia.
