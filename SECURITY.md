# Política de Seguridad

Última actualización: 31 de julio de 2026.

## Alcance

Esta política cubre el núcleo de Cano Hermes Agentic OS, sus agentes, skills, herramientas, proveedores de modelos, Nexus, contenedores, integraciones externas y procesos de desarrollo.

## Principios obligatorios

- modo seguro por defecto;
- privilegio mínimo;
- separación de workspaces y memorias;
- secretos fuera de Git;
- aprobación humana para acciones sensibles;
- trazabilidad de cambios y decisiones;
- rollback antes de operaciones irreversibles;
- cuarentena para capacidades importadas.

## Acciones que requieren aprobación

- llamadas API de pago por encima del presupuesto autorizado;
- publicación de contenido;
- envío de mensajes externos;
- despliegues y cambios productivos;
- acceso o modificación de datos empresariales;
- creación o rotación de credenciales;
- operaciones destructivas;
- cambios de permisos;
- merges a ramas protegidas.

## Secretos

Nunca deben almacenarse en Git:

- API keys;
- tokens OAuth;
- contraseñas;
- cookies y sesiones;
- certificados privados;
- credenciales de bases de datos;
- webhooks secretos;
- archivos `.env` reales.

Los secretos deben inyectarse mediante variables de entorno, servicios de secretos o credenciales temporales y limitadas.

## Agentes y runtimes

- Claude Code y Codex trabajan en worktrees o directorios separados.
- Ningún agente puede editar simultáneamente los mismos archivos que otro worker.
- Los agentes no reciben acceso directo a `/var/run/docker.sock`.
- OpenClaw, Hermes Agent y workers externos deben ejecutarse con permisos delimitados.
- Las capacidades nuevas pasan por `candidate → quarantine → review → approved → active`.
- Los agentes no aprueban su propio trabajo sensible.

## Docker y ejecución de código

- utilizar Docker rootless cuando sea posible;
- limitar CPU, memoria, tiempo y filesystem;
- negar red por defecto y usar allowlists;
- montar únicamente directorios necesarios;
- no ejecutar contenedores privilegiados;
- no compartir secretos maestros;
- destruir entornos temporales al finalizar.

## Memoria y Nexus

Los agentes reciben contexto mínimo mediante Context Builder. Las escrituras a la memoria global deben proponerse como candidatas y revisarse antes de promoción. La memoria de clientes, proyectos y canales debe permanecer separada.

## Proveedores externos

Cada proveedor debe tener:

- perfil de costo;
- límites de uso;
- permisos por agente;
- redacción de datos sensibles;
- fallback controlado;
- interruptor de desactivación;
- registro de consumo y errores.

## HERMES-KICKOFF (K0-K12)

Plan interno `~/.claude/plans/fluffy-twirling-lecun.md`, ejecutado sobre `cano-hermes-agentic-os`. Resumen de la fase de política más sensible del plan (K12 — "Autonomía gobernada + Seguridad v2").

### Autonomía gobernada (auto-aprobación)

`cano_hermes/governance/auto_approval.py` deja que una `ApprovalRequest` se resuelva sola, sin esperar a Cano, únicamente cuando **todas** estas condiciones se cumplen a la vez:

1. `risk == LOW`.
2. `costo_estimado_usd == 0` — ni un centavo.
3. `presupuesto_restante >= 0` — el presupuesto del día no está ya excedido (adición deliberada del K12, más allá de lo mínimo pedido).
4. La acción **no** está en `SENSITIVE_ACTIONS` (`governance/policy.py`) — chequeo propio del motor, no delega en que quien creó la solicitud ya haya filtrado.
5. Si la tarea pertenece a una oficina K9 (`kanban_profile` resuelve a un `offices/<perfil>/office.yaml` real), la acción **no** está en el `never:` de esa oficina.
6. Si hay una ruta de escritura conocida para la acción, cae dentro de `allowed_write_paths` del packet (K1/K2) — sin una allowlist contra la cual validar, falla cerrado (no se auto-aprueba).

Si **cualquiera** de estas falla, la solicitud queda pendiente exactamente igual que hoy — sin cambios, sin atajos. Cuando todas se cumplen, se resuelve llamando a `ApprovalService.resolve(approval_id, True, actor="policy-engine")` — la misma función que usaría un humano, con el mismo guardia anti-autoaprobación (`requested_by == actor` → `PermissionError`) intacto y sin duplicar.

**Garantía central, verificada con test explícito** (`tests/test_k12_auto_approval.py::SensitiveActionsAlwaysApprovalTests`): `publish` y cualquier miembro de `SENSITIVE_ACTIONS`, así como cualquier costo mayor a $0 (por pequeño que sea), **nunca** se auto-aprueban — caen en `APPROVAL` para que Cano decida, sin excepción.

**Zona gris documentada**: en `ExecutionService.run()`, el campo `ApprovalRequest.action` se puebla hoy con el *executor id* (`"claude-code"`, `"hermes-agent"`, etc.), no con un nombre de acción semántico del vocabulario de `SENSITIVE_ACTIONS` (`"publish"`, `"deploy"`, ...). El chequeo #4 de arriba es correcto e independiente tal como está especificado, pero en la práctica rara vez dispara a través de ese call site concreto hasta que un futuro caller etiquete `action` con la operación real en vez del executor. El propio motor, dado directamente un `action="publish"`, nunca se auto-aprueba (ver test explícito arriba) — la garantía vive en el motor, no depende de cómo cada call site etiquete hoy sus solicitudes.

### Modo `supervised` por defecto

`config.py`: `Settings.execution_mode` cambió su default de `dry_run` a `supervised`, alineando el código con la realidad operativa (el `.env` real de esta máquina ya forzaba `HERMES_EXECUTION_MODE=supervised` desde antes de K7). Bajo `supervised`, `PermissionEngine` evalúa siempre la etiqueta `"production_write"` — miembro de `SENSITIVE_ACTIONS` — así que **toda** ejecución de tarea pasa por aprobación antes de correr; el motor de auto-aprobación de arriba es lo que evita que esto signifique "aprobar manualmente cada tarea trivial".

### HMAC del puente StarHome <-> Kanban (K7)

`~/.hermes/plugins/starhome-bridge/` firma cada evento con HMAC-SHA256 sobre `json.dumps(payload, sort_keys=True)`, usando `STARHOME_BRIDGE_HMAC_SECRET` (leído de `.env`, nunca hardcodeado ni logueado) vía el header `X-StarHome-Signature`. Mecanismo actual, confirmado en K12:

- **Sin rotación automática.** El secreto es estático hasta que alguien lo cambia a mano en ambos `.env` (StarHome y `~/.hermes/.env`); no hay ventana de gracia de dos secretos ni versión en el header.
- **Sin expiración.** No hay timestamp firmado ni nonce — una firma válida hoy es válida indefinidamente si el secreto no cambia (no hay ventana de replay-protection más allá del propio `ts` del payload, que no se valida contra el reloj en el receptor).
- **Fail-closed por diseño.** Un secreto vacío en `~/.hermes/.env` hace que el plugin ni siquiera intente enviar (`_send` devuelve `False` sin red), y el lado StarHome (`inbound.py`) trata un secreto vacío como "rechazar todo", nunca como "saltar verificación".
- **Cola de reintento en disco.** Un envío fallido se guarda en `retry-queue/<uuid>.json` y se reintenta en el próximo hook, sin backoff ni límite — best-effort, nunca bloquea la transición kanban que observa.

No se implementa rotación en K12 (fuera de alcance declarado) — queda documentado como mecanismo actual, no como pendiente silencioso.

### Escaneo de secretos pre-commit

No existía `.pre-commit-config.yaml` ni hook real en `.git/hooks/` antes de K12 (solo los `.sample` de Git). Se añadió:

- `scripts/check_staged_secrets.py` — grep de patrones de credencial (AWS, Anthropic, OpenAI, Slack, Telegram, bloques de clave privada, y un catch-all genérico `KEY/SECRET/TOKEN = "..."` de 24+ caracteres) sobre el diff **staged** (`git diff --cached`), no el árbol completo. Mismo patrón que F16 (Plan Prometeo) corrió a mano sobre sus propios diffs, ahora automatizado en cada commit. Escape hatch: `# pragma: allowlist secret` en la misma línea.
- `.pre-commit-config.yaml` — hook local (`language: system`, sin dependencias externas) que invoca el script anterior.
- Activado con `pre-commit install` (verificado en vivo: un commit con una clave falsa `sk-ant-...` staged fue bloqueado con exit 1; un commit limpio pasa).

### Aislamiento por tier extendido a spawns kanban

- **K9 (oficinas Docker)**: cada `office-*` ya declaraba su propio allowlist de credenciales por `environment:` en `infrastructure/offices/docker-compose.yml` (ej. `office-publish` nunca recibe `UPLOAD_POST_*`/`TIKTOK_*`/`META_*`) — equivalente en garantías al patrón de `subprocess_executor.py:19-40`, reforzado además por aislamiento real de contenedor (red, filesystem, capacidades), no solo por variables de entorno. No se duplicó nada aquí.
- **Runtime nativo de hermes-agent** (`hermes kanban dispatch`/gateway fuera de Docker): hermes-agent tiene su propio mecanismo de credential scoping (`SECURITY.md` de ese repo, §2.3 "Credential Scoping" — filtra el entorno que pasa a sus propios subprocesos de menor confianza, con allowlist declarado por el operador/skill en vez de una tabla fija por executor id). Mecanismo distinto en mecánica, equivalente en espíritu (deny-by-default + passthrough explícito) — no se tocó ese repo (regla del `CLAUDE.md` raíz: invocar por contrato, no absorber).
- **Gap real encontrado y corregido en K12**: `cano_hermes/bridge/kanban_bridge.py::_run_hermes` (K6) — el spawn de StarHome hacia `hermes kanban boards create`/`hermes kanban --board ... create` (solo escritura de estado de tablero, sin llamar a ningún proveedor LLM) pasaba `subprocess.run(...)` **sin** `env=`, heredando el ambiente completo del proceso de StarHome (todas las credenciales de todos los tiers). Corregido reutilizando `SECRET_NAME_PATTERN` de `subprocess_executor.py` para despojar cualquier variable con forma de secreto antes de lanzar el subproceso — mismo patrón "cero secretos" que ya usan `container-sandbox`/`openclaw` en `EXECUTOR_SECRET_ALLOWLIST`, sin duplicar su regex. Test de regresión: `tests/test_k12_auto_approval.py::KanbanSubprocessCredentialIsolationTests`.

### Hardening de contenedores (oficinas Docker)

`infrastructure/offices/docker-compose.yml`, los 5 servicios `office-*`:

- `no-new-privileges:true` y `cap_drop: ["ALL"]` — ya presentes desde F11/K9, confirmados en K12.
- `read_only: true` + `tmpfs: [/tmp:rw,size=64m]` — añadido en K12. Verificado en vivo (no vía `docker compose up` real, para no tocar el board kanban de producción montado en esos servicios) con un contenedor aislado (`docker run --rm --read-only --tmpfs /tmp ... --network none`) confirmando que: (a) `/tmp` sigue escribible (los únicos scratch files fuera de `/office/output` son `/tmp/kanban-*.err|out` en `common/entrypoint.sh`), y (b) cualquier escritura fuera de eso (ej. `/office/y`) falla correctamente en vez de pasar en silencio. `docker compose config --quiet` valida el YAML resultante sin errores.

## Reporte de vulnerabilidades

No publiques vulnerabilidades, credenciales o datos sensibles en issues públicos. Reporta el problema de forma privada al propietario del repositorio mediante la cuenta `syacreator09-sys`, incluyendo:

1. componente afectado;
2. impacto estimado;
3. pasos de reproducción seguros;
4. evidencia sin secretos;
5. recomendación de mitigación.

## Respuesta a incidentes

1. aislar el componente;
2. revocar accesos afectados;
3. rotar credenciales;
4. preservar evidencia;
5. corregir la causa;
6. revisar alcance;
7. documentar acciones;
8. restablecer solamente después de aprobación.

## Repositorio público

Este repositorio debe permanecer libre de datos reales, secretos y configuración productiva. Antes de conectar infraestructura, cuentas, clientes o credenciales reales, se recomienda cambiar la visibilidad del repositorio a **Private**.

La política técnica ampliada está en [`docs/SECURITY.md`](docs/SECURITY.md).
