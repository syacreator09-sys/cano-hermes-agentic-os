# Arquitectura de StarHome OS

![Arquitectura oficial de StarHome OS](assets/starhome-os-architecture.svg)

StarHome OS se organiza como un sistema operativo agéntico modular, supervisado y desacoplado. El nombre visible del producto es **StarHome OS**; el paquete técnico foundation continúa temporalmente bajo `cano_hermes`.

## Planos principales

### 1. Plano de control

Incluye:

- Conductor;
- Task Engine;
- Capability Registry;
- Policy Engine;
- Budget Controller;
- Approval Engine;
- Evaluation Engine;
- Event Timeline.

El Conductor recibe contexto compacto, interpreta el objetivo y delega. No realiza directamente el trabajo especializado.

### 2. Plano de ejecución

Incluye:

- Claude Code;
- Codex;
- Hermes Agent;
- OpenClaw;
- browser workers;
- Python workers;
- Docker rootless;
- worktrees y espacios aislados.

Cada ejecución utiliza un contrato con objetivo, archivos permitidos, permisos, presupuesto, timeout, criterios de aceptación y rollback.

### 3. Plano de inteligencia

El router usa una estrategia `subscription-first` y selecciona proveedor según costo, complejidad, riesgo, contexto y disponibilidad.

Proveedores previstos:

- Claude Code / Anthropic;
- Codex / OpenAI;
- Kimi;
- DeepSeek;
- Qwen;
- Grok;
- modelos locales.

### 4. Plano de conocimiento

StarHome Nexus conecta:

- Obsidian Markdown;
- Graphify;
- búsqueda;
- backlinks;
- decisiones;
- memoria por proyecto;
- Context Builder;
- candidatos de memoria supervisados.

Los agentes no reciben toda la memoria. Nexus construye un paquete pequeño con las notas, relaciones, archivos y decisiones relevantes.

### 5. Plano de capacidades

StarHome Forge administra:

- agentes;
- skills;
- MCP;
- blueprints;
- contenedores;
- pruebas y evaluaciones;
- cuarentena;
- versiones;
- promoción y retiro.

El ciclo esperado es:

```text
DRAFT → CANDIDATE → QUARANTINE → TESTING → REVIEW → APPROVED → ACTIVE → ARCHIVED
```

### 6. Plano de experiencia

StarHome UI reúne:

- chat central;
- dashboard;
- tareas y Kanban;
- mapa de agentes;
- Nexus;
- Agent Forge;
- Radar;
- Content Studio;
- costos;
- aprobaciones;
- actividad y auditoría.

## Módulos oficiales

```text
StarHome OS
├── Conductor
├── Nexus
├── Forge
├── Radar
├── Executors
├── Governance
└── UI
```

## Equipos especializados

```text
Governance
Engineering
Research
Content
Forge
Operations
```

Claude Code se orienta a arquitectura, análisis y revisión. Codex se orienta a implementación, pruebas, depuración y construcción de interfaces. No escriben simultáneamente en el mismo workspace.

## Integraciones externas

Factory V5 y Cano AI Command Center permanecen como sistemas separados. StarHome OS se conecta mediante adaptadores y contratos versionados.

También se contemplan:

- Supabase;
- Cloudflare;
- Modal;
- WhatsApp;
- Telegram;
- voz;
- servicios de publicación y métricas.

## Nexus: `cano_hermes/nexus/` vs. `~/repos/starhome-nexus` (K15)

K11 descubrió, sin resolver, que existen **dos implementaciones separadas**
de "memoria + contexto + candidatos human-gated sobre el mismo vault"
(`~/StarHomeVault`) — este `cano_hermes/nexus/` (in-process, parte de este
repo) y `~/repos/starhome-nexus` (paquete Python instalable independiente,
CLI `nexus`). K15 la revisó a fondo. Conclusión: **duplicación real de
responsabilidad, no solo de nombre — pero no accidental, y no se
resuelve fusionando código en esta fase.**

### Qué hace cada uno, concretamente

| | `cano_hermes/nexus/` (este repo) | `starhome-nexus` (repo aparte) |
|---|---|---|
| Búsqueda + contexto | `ContextBuilder` (`context.py`) sobre `MarkdownVault` (grep/frontmatter propio) + `KnowledgeGraph` (vecindario de wikilinks) | `ContextBuilder` propio sobre `Catalog` — **SQLite FTS5 real**, con `sensitivity_allowed()` como filtro de política |
| Grafo de código | `GraphifyAdapter.query()` — lee `graphify-out/graph.json` ya construido, scoring por término | `GraphifyAdapter` propio — invoca el CLI real de graphify (`explain`/`path`), desactivado por defecto |
| Candidatos de memoria | `MemoryCandidateService` (K11, `governance/memory_candidates.py`) — tabla `memory_candidates` propia de este repo, humano resuelve vía `POST /api/memory/candidates/{id}/resolve`, promueve escribiendo un `.md` ad hoc en `00-Candidatos-Aprobados/` | `nexus memory-propose` / `nexus memory-review` — su propio flujo, indexado en su propio catálogo FTS5, ciclo de vida documentado en `docs/MEMORY_MODEL.md` (`draft → candidate → review → approved → active → superseded/archived`) |
| Alcance | Un cliente: StarHome OS (`GET /api/nexus/context`, tool MCP `nexus_context`) | Multi-cliente por diseño: Claude Code, Codex, Hermes Agent, OpenClaw, StarHome OS — instala skills administradas en cada uno |
| Madurez operativa | Cubierto por la suite de 271 tests de este repo, corre en producción (daily cycle, dashboards) | `IMPLEMENTATION_STATUS.md` propio lo declara **"foundation portable construida, NO una versión productiva validada"** — cero CI, cero backups/restore reales ejecutados, cero validación en máquina limpia |

### Por qué es duplicación real (no solo semántica)

El síntoma concreto: un candidato aprobado por `MemoryCandidateService.
resolve()` aquí escribe un `.md` en `00-Candidatos-Aprobados/` con su propio
frontmatter — **starhome-nexus no lo ve** hasta que alguien corra `nexus
index-vault` manualmente, y el candidato nunca pasó por el ciclo de vida de
`docs/MEMORY_MODEL.md` (`memory-propose`/`memory-review`) que starhome-nexus
exige para todo lo demás. Si Cano usa `nexus query`/`nexus context` (la
fachada que se supone es "memoria portable multi-herramienta") para
buscar algo que aprobó vía el dashboard de StarHome, no lo encuentra.
Dos catálogos, dos ciclos de vida de candidato, un solo vault de destino.

### Decisión (K15) — coexistencia deliberada, no fusión

**No se toca `starhome-nexus`** (fuera de alcance: es otro repo, y
fusionar sistemas de memoria sin que Cano decida la fuente de verdad
sería diseño no autorizado — regla ya establecida en K11). Tampoco se
reescribe `cano_hermes/nexus/` para delegar en el CLI `nexus` esta fase:

1. `cano_hermes/nexus/` es la capa que **StarHome opera en caliente**
   (`GET /api/nexus/context`, ciclo diario, dashboards) — depender de un
   subprocess `nexus` externo ahí introduciría una dependencia dura sobre
   un paquete que su propio `IMPLEMENTATION_STATUS.md` marca como no
   validado en producción. Prematuro cambiarlo hoy.
2. `starhome-nexus` es la capa de **memoria personal portable de Cano**,
   compartida entre las 5 herramientas — su valor real (FTS5, backups con
   SHA-256, multi-cliente) es justamente lo que `cano_hermes/nexus/` no
   necesita duplicar para su propio caso de uso interno.
3. Ambos son **solo-lectura sobre el vault salvo la promoción de
   candidatos** (la única escritura real) — el riesgo de la duplicación
   hoy es de **descubribilidad** (dos catálogos, un candidato aprobado en
   uno no aparece en el otro), no de corrupción de datos ni de conflicto
   de escritura concurrente.

**Camino de convergencia futuro (no implementado, para una fase que
Cano priorice explícitamente):** el punto de extensión ya existe —
`ContextBuilder.__init__` de este repo acepta un tercer adaptador opcional
(mismo contrato `query(text, limit) -> list[dict]` que `GraphifyAdapter`,
documentado en su propio docstring como "extension point for a future
gbrain adapter"). El mismo patrón sirve para un `StarHomeNexusAdapter`
que invoque `nexus query`/`nexus context` como fuente adicional, y para
que `MemoryCandidateService.resolve()` invoque `nexus memory-propose` en
vez de (o además de) escribir su propio `.md` — ambos son cambios
aditivos, sin romper el `ContextPacket` actual, el día que Cano decida
que `starhome-nexus` es la fuente de verdad para candidatos.

## Gobierno

Las acciones sensibles requieren aprobación:

- gasto;
- publicación;
- envío de mensajes;
- despliegue;
- modificación productiva;
- credenciales;
- operaciones destructivas;
- cambios de permisos.

La arquitectura prioriza privilegio mínimo, memoria segmentada, auditoría, aislamiento y reversibilidad.
