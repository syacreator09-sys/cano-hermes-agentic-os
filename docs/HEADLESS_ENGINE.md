# Headless Engine — Hermes maneja Claude Code sin el operador presente

> La pieza que convierte a Hermes en "el operador ausente": un proceso
> persistente que se sienta frente a Claude Code por el humano. Extiende el
> plano de ejecucion de `ARCHITECTURE.md` (Claude Code ya esta listado ahi
> como executor); aqui se define el contrato operativo exacto.

## Loop principal

```
PM2: hermes-master (Node o Python)
  1. Toma la siguiente tarea de la cola (Task Engine, SQLite)
     - origen: scheduler (cadencia), Telegram (orden del operador),
       o el propio master (subtareas de un plan)
  2. Clasifica: oficina destino + modelo + aislamiento (Docker si/no)
  3. Lanza la sesion headless:
       claude -p "<prompt con contexto de la tarea>" \
         --model <ver tabla de ruteo> \
         --permission-mode acceptEdits \
         -C <carpeta de la oficina>
     (para control fino de streaming/turnos: Agent SDK en lugar del CLI)
  4. Al terminar, valida el resultado:
       - tests (pytest -q / validate-yaml) si toco codigo
       - preflight si toco providers
       - runbook de QA (editing-quality) si produjo video
  5. Decide:
       - OK      → commit tematico + registro en timeline + reporte Telegram
       - FALLA   → reintenta con el error como contexto (max 2 reintentos)
       - GATE    → detecta que la tarea requiere gasto/publicacion →
                   crea ApprovalRequest + mensaje Telegram al operador → espera
  6. Vuelve a 1.
```

## Ruteo de modelos (usa las llaves ya disponibles)

| Tipo de tarea | Motor | Racional |
|---|---|---|
| Plan/arquitectura/decision de diseño | Claude **Opus** (max 5/dia) | maximo razonamiento, pocas llamadas |
| Construccion: codigo, produccion, fixes | Claude **Sonnet** | caballo de trabajo de las sesiones headless |
| Guiones masivos, SEO, hooks, titulos, clasificacion, resumenes | **NVIDIA NIM** (~80 modelos, 1 key) / **Kimi** / **Cloudflare AI** | $0 — portar el patron `ai.py` del command center (`cano-ai-command-center/ai.py`) |
| Segunda opinion / decision critica | **Council multi-modelo** — portar `cano-ai-command-center/scripts/council/` (providers ya escritos: nvidia_nim, nvidia_deepseek, nvidia_nemotron, kimi, cloudflare, openai_oauth, xai_grok, mistral, groq_fast) | consenso barato antes de gastar |
| QA visual de video | Claude con vision o NIM con vision | verificacion post-render |

Regla de presupuesto: gratis primero (NIM/Kimi/CF) para todo lo que no exija
calidad Claude; Opus SOLO para planes; Sonnet ejecuta.

## Contrato de cada sesion headless

Cada tarea lanzada lleva (mismo espiritu que los contratos de ejecucion de
ARCHITECTURE.md): objetivo, carpeta permitida, comandos bloqueados,
presupuesto (tokens/tiempo), criterio de aceptacion y validacion, y que
reportar. La sesion NO hereda permisos del master: `--permission-mode` y
carpeta de trabajo la acotan.

## Que NUNCA hace una sesion headless

- Aprobar su propio gate (el ApprovalRequest lo responde solo el operador por Telegram).
- Tocar `.env` o leer secretos fuera de su oficina.
- Publicar, pagar, desplegar, o subir contenido publico.
- Instalar software de sistema (eso es tarea del master con log).

## Telegram como consola remota

Comandos minimos del bot:
- `/estado` — cola, sesiones vivas, creditos, pendientes
- `/aprobar <id>` / `/rechazar <id>` — resolver gates
- `/tarea <texto>` — encolar orden en lenguaje natural (el Conductor la interpreta)
- `/briefing` — resumen inmediato
- `/parar` — pausa el loop (las sesiones vivas terminan, no se lanzan nuevas)
Solo `TELEGRAM_OPERATOR_CHAT_ID` puede usar comandos; cualquier otro chat se ignora.
