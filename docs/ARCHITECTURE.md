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
