# Spawning Protocol — el master crea y comanda sub-Hermes (oficinas)

> Complementa `AGENT_FORGE.md` (lifecycle draft→...→active) con el mecanismo
> concreto de creacion de OFICINAS: sub-Hermes especializados con carpeta,
> mision, skills y limites propios. El master manda a todos; ninguna oficina
> manda al master.

## Plantilla (offices/_TEMPLATE-OFICINA/)

Toda oficina nace copiando la plantilla y llenando `office.yaml`:

```yaml
# office.yaml — contrato de la oficina
name: hermes-<nombre>
mission: <una frase: que produce y para quien>
skills: [<skills asignados>]
scripts_factory: [<scripts de factory-v5 que replica/usa>]
providers: [<proveedores cloud permitidos>]
default_model: <sonnet|nim|kimi>        # el master puede subir a opus por tarea
budget_daily: {credits: 0, usd: 0}      # 0 = no puede gastar sin gate
cadence: "<cron o 'on-demand'>"
isolation: <none|folder|docker>
never: [publicar, pagar, tocar_env, aprobar_gates]
```

Mas `CLAUDE.md` (contexto que la sesion headless lee al arrancar en esa
carpeta) y `runbooks/` (checklists heredados del command center).

## Reglas de spawning

1. **Registro obligatorio**: crear oficina = copiar plantilla + fila en
   `registry/` + commit. Oficina no registrada no recibe tareas.
2. **Antes de crear, consultar el Capability Registry** (regla de AGENT_FORGE):
   si un skill o MCP existente cubre la necesidad, NO crear oficina nueva.
3. **Herencia de bloqueos**: toda oficina hereda los bloqueos de
   `START-HERE-HERMES-REMOTE.md` (no secretos, no publicar/pagar sin humano,
   mexvibe intocable, VPS1 intocable). El `never:` del yaml solo puede AGREGAR
   restricciones, jamas quitarlas.
4. **Tope i5**: max 2-3 oficinas con tarea pesada concurrente; el master
   respeta la cola (render Remotion = 1 a la vez).
5. **Lo indelegable**: aprobar gasto, publicar, crear/borrar oficinas y
   modificar presupuestos es EXCLUSIVO del master + operador. Una oficina
   puede PEDIR, nunca ejecutar esas acciones.
6. **Ciclo de vida**: oficina sin tareas 30 dias → el master propone
   archivarla (lifecycle stale→archived de AGENT_FORGE).

## Las 6 oficinas iniciales

| Oficina | Mision | Skills/fuentes clave | Modelo default |
|---|---|---|---|
| hermes-research | Radar viral diario (Apify metadata-only) + transcripts bajo demanda (Supadata→Whisper) | providers/apify_*, providers/supadata/, viral_reference_expansion | NIM (clasificar), Sonnet (sintetizar) |
| hermes-guiones | Guiones reales desde research: narracion 7 capitulos, hooks, 8s-optimizer, repair | runbooks long-narration-writer + content-repair, skills 8s-script-optimizer, scroll-stopper-hooks | Sonnet (prosa final), NIM (borradores masivos) |
| hermes-produccion | Render: Remotion + ffmpeg + edge-tts + MoneyPrinter; QA con ffprobe | scripts/produce_*.py, final_remotion_v2.py, renderers/remotion | Sonnet |
| hermes-ugc | Scout afiliados → manifest → (gate) → Higgsfield → draft | ugc-affiliate scout, adapters/ugc/affiliate_scout_adapter.py, engines/ugc/ugc-commerce-studio | Sonnet; generacion = gate SIEMPRE |
| hermes-distribucion | Preparar drafts de subida (YouTube nativo), dedup, metadata veraz | runbook publishing-coordinator, ledger | Sonnet; dispatch = gate SIEMPRE |
| hermes-monitor | Briefings, vigilancia 10 min, creditos, salud, informes | preflight, ledger, PM2 status | NIM (gratis, corre seguido) |

## Jerarquia

```
OPERADOR (Telegram/Terminal)
  └─ HERMES MASTER (Conductor + Task Engine + Approval + Budget)
       ├─ hermes-research ─┐
       ├─ hermes-guiones   ├─ sesiones headless de Claude Code
       ├─ hermes-produccion│  (aisladas por carpeta o Docker)
       ├─ hermes-ugc       │
       ├─ hermes-distribucion
       └─ hermes-monitor  ─┘
```
El master puede crear mas oficinas (misma plantilla + registro + commit) cuando
el operador lo pida o cuando una mision recurrente no encaje en las 6 — siempre
reportandolo en el briefing.
