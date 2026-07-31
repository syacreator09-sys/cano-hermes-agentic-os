# Cano Hermes Agentic OS

**Sistema operativo agéntico personal, modular y supervisado para Cano.**

Cano Hermes Agentic OS coordina equipos de agentes, Claude Code, Codex, proveedores económicos de modelos, memoria Obsidian + Graphify, creación de agentes y skills, producción de contenido y conexiones con sistemas externos. Es un proyecto independiente de Cano AI Command Center.

> Estado actual: **foundation v0.2.0**. El código fuente está construido, pero las credenciales, proveedores reales, publicaciones, despliegues y acciones sensibles permanecen desactivados por defecto.

## Objetivo

Permitir que Cano solicite resultados de alto nivel —por ejemplo contenido, investigaciones, agentes, automatizaciones o sistemas— y que Hermes pueda:

1. comprender el objetivo;
2. recuperar contexto relevante;
3. dividir el trabajo;
4. seleccionar agentes, modelos y herramientas;
5. construir y revisar entregables;
6. registrar decisiones, costos y aprendizajes;
7. solicitar aprobación antes de acciones sensibles.

## Arquitectura principal

```text
Cano
  ↓
Hermes Gateway / Dashboard
  ↓
Conductor + Task Engine + Governance
  ↓
Model Router + Capability Registry
  ↓
Claude Code · Codex · Kimi · DeepSeek · Qwen · Grok · OpenAI · Local
  ↓
Engineering · Research · Content · Forge · Operations
  ↓
Nexus: Obsidian + Graphify + Context Builder
```

## Componentes incluidos

- API FastAPI y dashboard web.
- tareas, eventos y aprobaciones persistentes en SQLite;
- Conductor ligero y Task Governor;
- router multmodelo con estrategia `subscription-first`;
- perfiles para Claude Code, Codex, Hermes Agent y OpenClaw;
- registro de capacidades, agentes, skills y herramientas;
- 38 agentes organizados por equipos;
- 40 skills reutilizables;
- Nexus Markdown/Obsidian con grafo y contexto compacto;
- Agent Forge y Skill Forge;
- Radar y Content OS;
- adaptadores separados para Factory V5 y Cano AI Command Center;
- gobierno de permisos, presupuestos, aprobaciones y auditoría;
- estructura Docker, Ubuntu y systemd;
- documentación de arquitectura, seguridad, roadmap y operación.

## Principios de seguridad

- ninguna clave se almacena en Git;
- producción, publicación, gasto, mensajes y despliegues requieren aprobación;
- los agentes no reciben acceso al socket de Docker;
- Claude Code y Codex trabajan en espacios separados;
- capacidades importadas comienzan en cuarentena;
- las escrituras de memoria se promueven de forma supervisada;
- los proveedores externos están desactivados hasta configurarse explícitamente.

Consulta [SECURITY.md](SECURITY.md) y [PRIVACY.md](PRIVACY.md).

## Estructura

```text
cano_hermes/       núcleo, API, router, Nexus y Forge
agents/            manifiestos de agentes
skills/            skills reutilizables
integrations/      contratos con sistemas externos
docs/              arquitectura, seguridad y operación
vault/             estructura base de Obsidian
infrastructure/    Docker, Ubuntu y systemd
scripts/           utilidades administrativas
tests/             pruebas incluidas en el proyecto
```

## Configuración local

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn cano_hermes.api.app:app --reload
```

Dashboard local:

```text
http://127.0.0.1:8000
```

## Estado de integraciones

| Capacidad | Estado inicial |
|---|---|
| API y dashboard | Construido |
| Tareas y eventos SQLite | Construido |
| Registro de agentes y skills | Construido |
| Nexus Markdown/Obsidian | Construido |
| Claude Code | Adaptador seguro, requiere autenticación local |
| Codex | Adaptador seguro, requiere autenticación local |
| Kimi, DeepSeek, Qwen, Grok y OpenAI | Requieren claves y presupuesto |
| Factory V5 | Contrato externo, sin activación productiva |
| Command Center | Sistema externo, no absorbido |
| Publicación y despliegue | Bloqueados por defecto |

## Documentación

- [Arquitectura](docs/ARCHITECTURE.md)
- [Seguridad](docs/SECURITY.md)
- [Roadmap](ROADMAP.md)
- [Reglas de agentes](AGENTS.md)
- [Instrucciones para Claude Code](CLAUDE.md)
- [Privacidad](PRIVACY.md)
- [Contribución](CONTRIBUTING.md)

## Licencia

Este repositorio utiliza una licencia propietaria. Consulta [LICENSE](LICENSE). La visibilidad pública del repositorio no concede permiso para copiar, redistribuir, vender o reutilizar el código.

---

**Propietario:** Cano / `syacreator09-sys`  
**Repositorio:** `cano-hermes-agentic-os`  
**Versión de foundation:** `0.2.0`
