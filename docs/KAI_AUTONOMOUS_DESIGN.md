# KAI Autonomous Design — StarHome OS como operador 24/7

> Traduccion del diseño de referencia "KAI" (Mac Mini 24/7, Claude Code como
> nucleo, Terminal + Telegram + Scheduler como entradas) a la maquina Hermes
> (i5, cloud-first). Este doc extiende `ARCHITECTURE.md` — no lo reemplaza:
> el Conductor, Task Engine, Approval Engine y Budget Controller existentes
> son los componentes que aqui se ponen en marcha con cadencias concretas.

## Diagrama objetivo

```
                     HERMES MASTER (proceso PM2, 24/7)
  ENTRADAS
  ├─ Terminal   → sesion manual del operador (cuando esta presente)
  ├─ Telegram   → mando remoto: ordenes, aprobaciones, voz/audio, briefings
  └─ Scheduler  → PM2 + node-cron: dispara tareas sin nadie presente
  NUCLEO
  ├─ Conductor (cano_hermes/orchestration/conductor.py) — interpreta y delega
  ├─ Task Engine — cola SQLite de tareas
  ├─ Approval Engine — gates humanos (via Telegram, NUNCA API abierta)
  ├─ Budget Controller — tope de gasto por dia y por proveedor
  ├─ Skills + MCPs + Git (paridad con command center)
  └─ StarHome Nexus (memoria Obsidian/Graphify)
  EJECUCION
  └─ Sesiones headless de Claude Code (ver HEADLESS_ENGINE.md)
     opcionalmente aisladas en Docker (ver DOCKER_ISOLATION.md)
  OFICINAS (offices/) — sub-Hermes especializados (ver SPAWNING_PROTOCOL.md)
```

## Cadencias (node-cron bajo PM2)

| Cuando | Que | Oficina |
|---|---|---|
| Diario 08:15 | Briefing del dia al operador (Telegram): cola, creditos, pendientes de aprobacion | monitor |
| Diario 08:30 | Research wave (Apify metadata-only, presupuesto capado) | research |
| Diario 09:00 | Vigilancia: ledger de subidas, metricas disponibles, salud de canales | monitor |
| Diario 10:00 | Produccion del dia (guiones → render → draft, SIN publicar) | guiones+produccion |
| Cada 3 dias 17:00 | Auditoria de calidad de lo producido (runbook editing-quality) | produccion |
| Jueves 10:00 | Novedades/modulos: revisar commits nuevos de ambos repos y actualizarse | master |
| Viernes 14:00 | Resumen semanal (producido, gastado, aprobado, bloqueado) | monitor |
| Dia 1 de mes 10:00 | Informe mensual + propuesta de mejoras | master |
| Cada 10 min | Monitor: procesos vivos, disco, cola atascada, creditos bajo minimo | monitor |

## Regla de oro (no negociable)

- **Producir es autonomo**: research, guiones, renders locales (Remotion/ffmpeg/
  edge-tts, $0), drafts — sin pedir permiso.
- **Gastar creditos** (Higgsfield, Kie, ElevenLabs sobre umbral, Modal) y
  **publicar** (YouTube, Upload-Post, ads): SIEMPRE gate humano via Telegram.
  Si el operador no responde, la tarea espera en cola — jamas se auto-aprueba.
- La API de aprobaciones de factory NO se expone a red en Hermes (en el origen
  no tiene auth); el unico canal de aprobacion es el chat de Telegram del
  operador (`TELEGRAM_OPERATOR_CHAT_ID`).

## Presupuestos por defecto (Budget Controller)

| Recurso | Tope diario inicial |
|---|---|
| Higgsfield | 0 creditos sin aprobacion explicita por plan |
| Kie | scope smoke, 1 task, hasta que el operador suba el limite |
| ElevenLabs | solo voces aprobadas, selectivo |
| Modal GPU | 1 USD/dia |
| LLM Anthropic | Opus max 5 invocaciones/dia (planes); Sonnet sin tope duro pero monitoreado |
| NIM/Kimi/Cloudflare | sin tope (gratis) — default para tareas masivas |

## Hardware i5 — limites operativos

- Max 2-3 sesiones headless pesadas concurrentes (render Remotion = 1 a la vez).
- Nada de GPU local: CUDA/SD/MusicGen quedan N/A; el equivalente es cloud.
- Renders largos van en cola secuencial nocturna si el dia esta saturado.
