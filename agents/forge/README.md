# PROMETEO — la forja de StarHome OS

PROMETEO es el nombre operativo del team `forge`: los seis agentes en este
directorio, respaldados por el código en `cano_hermes/forge/`. Su trabajo es
construir nuevas capacidades (agentes, skills) de forma segura — nunca
activarlas directamente. Ese último paso siempre pasa por un humano.

Ver también `docs/ARCHITECTURE.md` §5 ("Plano de capacidades") — Forge es
uno de los seis módulos oficiales de StarHome OS, junto a Conductor, Nexus,
Radar, Executors y Governance.

## Quién es PROMETEO

Seis manifiestos YAML, cada uno con un rol fijo en el pipeline:

| Agente | Rol |
|---|---|
| `forge-lead` | Coordina el pipeline completo; es quien típicamente dispara `propose`/`request_approval`. |
| `agent-designer` | Diseña blueprints de agentes con contrato completo (objetivo, permisos, presupuesto). |
| `capability-auditor` | Evita duplicados; decide reutilizar, adaptar o construir desde cero. |
| `container-builder` | Construye/mantiene los sandboxes rootless donde corren los smoke-tests. |
| `mcp-engineer` | Construye servidores MCP acotados y probados (fuera del alcance de F4). |
| `skill-engineer` | Construye y versiona skills reutilizables. |

Todos comparten la misma forma: `permissions.production: approval-required`,
`evaluations: [schema, safety, task-contract]`, presupuesto acotado
(`max_cost_usd: 0.5`, `max_turns: 16`). Ninguno tiene permiso de red abierto
ni acceso de producción sin aprobación — son, ellos mismos, el primer
ejemplo de lo que exigen a cualquier candidato que forjan.

**Regla anti-duplicación**: no crear nuevos agentes de gobierno de la forja.
Estos seis ya existen y ya se cargan vía `AgentRegistry` (que escanea
`agents/**/*.yaml`, no `agents/candidates/`). Cualquier necesidad nueva de
"otro agente de forja" es, con altísima probabilidad, una extensión de uno
de estos seis, no un séptimo agente.

## El código: `cano_hermes/forge/`

| Archivo | Qué hace |
|---|---|
| `agent_factory.py` | Escribe/lee el artefacto candidato de un agente. `create_candidate` (pre-F4) y `create_from_definition` (F4) escriben a `agents/candidates/<id>.yaml` con `status: quarantine`. `rewrite_status` avanza el status en el propio archivo (`quarantine → testing`). `promote` lo materializa en `agents/<team>/<id>.yaml` con `status: active`, solo tras aprobación. |
| `skill_factory.py` | Lo mismo para skills: `skills/candidates/<id>/{manifest.json,SKILL.md}` → `skills/<id>/`. |
| `models.py` | `ForgeCandidate` / `ForgeStage` / `StageResult` — el estado del *pipeline* (no confundir con el `status` del propio manifiesto: son dos lifecycles relacionados pero distintos, ver más abajo). |
| `store.py` | `ForgeCandidateStore` — persiste un `ForgeCandidate` por archivo JSON bajo `storage/forge/candidates/` (efímero, como `storage/workspaces/`; no es el artefacto final versionado). |
| `duplication.py` | La regla anti-duplicación dura (bloqueante) + el escaneo semántico blando (informativo) contra command-center. |
| `evaluations.py` | Los tres checks reales detrás de `evaluations: [schema, safety, task-contract]` que cada YAML de forge ya declaraba. |
| `pipeline.py` | `ForgePipeline` — el orquestador. Une todo lo anterior. |

`agent_factory.py` y `skill_factory.py` ya existían desde antes de F4 (con
`create_candidate`, sin más). F4 los extendió — no los reemplazó — con
`create_from_definition`/`rewrite_status`/`promote`.

## El pipeline

```
propose()          run_sandbox()        cross_review()       request_approval()      promote()
   │                    │                     │                      │                    │
   ▼                    ▼                     ▼                      ▼                    ▼
candidato en      ContainerSandbox-     schema + safety +      ApprovalRequest        agents/<team>/<id>.yaml
agents/candidates/  Executor corre un    task-contract         real vía               o skills/<id>/
 (quarantine)      smoke-test: sin       (evaluations.py)      ApprovalService         (status: active)
                   red, sin creds                              — espera humano
```

1. **Candidato** — `propose(kind, definition)` primero aplica la regla
   anti-duplicación (bloqueante: rechaza si `id` ya existe en
   `agents/**/*.yaml` o `skills/**/manifest.json`), luego escribe el
   artefacto vía `AgentFactory`/`SkillFactory`. Un candidato malformado
   *no* se rechaza aquí — entra igual al pipeline con un artefacto
   best-effort, para que el rechazo quede *registrado y explicado* por
   `cross_review`, no como una excepción muda en el intake.

2. **Sandbox** — `run_sandbox(candidate_id)` corre un smoke-test
   (`python3 -c "..."` validando que el candidato tiene `id`/`objective`)
   dentro de `ContainerSandboxExecutor` (F3,
   `cano_hermes/runtimes/container_sandbox.py`, registrado en
   `ExecutionService.executors["container-sandbox"]`): rootless,
   `--network none`, cero credenciales
   (`EXECUTOR_SECRET_ALLOWLIST["container-sandbox"]` es el conjunto vacío).

3. **Revisión cruzada** — `cross_review(candidate_id)` corre
   `evaluations.cross_review`, que da contenido real a los tres checks que
   cada YAML de forge ya declaraba (`schema`, `safety`, `task-contract`):
   valida contra `AgentManifest` (agentes) o los campos mínimos (skills);
   rechaza permisos de producción/red demasiado abiertos y herramientas
   fuera de allowlist; exige un objetivo descriptivo y un presupuesto
   dentro de un techo razonable para algo aún no probado.

4. **Aprobación** — `request_approval(...)` construye un `ApprovalRequest`
   real (F3, `cano_hermes/governance/approvals.py`) con los cinco campos
   obligatorios: `motivo`, `costo_estimado_usd`, `presupuesto_restante`,
   `canal`, `evidencia` (ruta a un JSON con el resultado completo de
   sandbox + revisión). `ApprovalService` impide que el mismo actor que
   pidió la promoción la resuelva. Cano resuelve desde fuera del pipeline
   (dashboard, `POST /api/approvals/{id}/resolve`, etc.).

5. **Promoción** — `promote(candidate_id)` solo avanza si la
   `ApprovalRequest` ligada está `APPROVED`. Entonces sí materializa el
   candidato en `agents/<team>/<id>.yaml` o `skills/<id>/`, con
   `status: active`, quedando disponible para `AgentRegistry`/
   `SkillRegistry` en el siguiente `load()`.

`submit(kind, definition, ...)` encadena 1→4 y se detiene ahí — la
promoción siempre es una llamada aparte, después de que Cano resuelva.

### Dos lifecycles, no uno

El `status` dentro del manifiesto YAML/JSON (`AgentStatus`: `draft → candidate
→ quarantine → testing → approved → active → stale → archived`,
docs/ARCHITECTURE.md §5) describe al *artefacto*. El `stage` de
`ForgeCandidate` (`proposed → sandboxed → reviewed → pending_approval →
promoted`, con las variantes `*_failed`/`rejected`) describe al *pipeline*.
Un candidato puede fallar `cross_review` (stage `review_failed`) sin que su
artefacto en disco deje de decir `quarantine` — el stage es la fuente de
verdad de "qué tan lejos llegó", no el status del archivo.

## Interfaces

- **API**: `POST /api/forge/agents`, `POST /api/forge/skills` (propose→sandbox→review→request-approval
  en una sola llamada), `GET /api/forge/candidates`, `GET /api/forge/candidates/{id}`,
  `POST /api/forge/candidates/{id}/promote`.
- **CLI**: `hermes-cano forge propose <agent|skill> <definicion.json|yaml>`,
  `hermes-cano forge status <candidate-id>`, `hermes-cano forge promote <candidate-id>`,
  `hermes-cano forge list`.

## Estado real al cierre de F4

Tres candidatos reales corrieron por el pipeline completo (`agents/candidates/`,
evidencia en `storage/forge/candidates/`) y quedaron en `pending_approval`,
esperando que Cano resuelva su `ApprovalRequest` — ninguno fue promovido por
el propio pipeline:

- `connection-auditor` (team `operations`)
- `media-render-worker` (team `content`)
- `upload-dispatcher` (team `content`)

Detalle de cada uno, motivo y resultado de la revisión semántica contra
command-center: ver la descripción del PR que introdujo F4.
