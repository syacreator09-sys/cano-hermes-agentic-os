# Contrato de integración — Adaptive Agent Harness (AAH)

**Estado:** contrato futuro. AAH (`syacreator09-sys/adaptive-agent-harness`)
**sigue en construcción por otro agente**: este repo NO lo clona, NO lo
implementa y NO escribe código de executor todavía. Este documento fija, por
adelantado, cómo StarHome OS lo envolverá cuando exista, para que la adopción
sea un cambio pequeño y sin sorpresas.

Fuente del diseño de AAH: `docs/superpowers/specs/2026-08-07-adaptive-agent-harness-design.md`
en el repo del harness (leído vía `gh api`, read-only). Referencias abajo como
"spec §N".

---

## 1. Qué es AAH para StarHome

AAH es un runtime externo de tipo CLI, igual que Codex o Claude Code: StarHome
lo invoca por contrato, nunca lo absorbe. El flujo previsto por el propio spec
(§16, "Hermes integration") coincide con nuestro modelo de ejecución:

```
Hermes → AAH CLI → capability discovery → profile/router → execution loop → structured result
```

AAH es **subscription-first** (spec §7): funciona sin API keys porque usa los
CLIs ya autenticados de la máquina (`claude`, `codex`). Esa propiedad define
todo el contrato de credenciales de la sección 3.

## 2. Envoltorio: `AAHExecutor(CommandExecutor)`

El executor vivirá en `cano_hermes/runtimes/aah.py` y seguirá el patrón exacto
del executor más simple del repo, `cano_hermes/runtimes/codex.py`
(`CodexExecutor`): subclase de `CommandExecutor`
(`cano_hermes/runtimes/subprocess_executor.py`) que solo define `__init__` y
`build_args`. Todo lo demás — dry_run, strip de secretos, timeout, parsing a
`ExecutionResult` — lo hereda.

Forma prevista (ilustrativa, NO implementar aún):

```python
from __future__ import annotations

from typing import Sequence

from .base import ExecutionPacket
from .subprocess_executor import CommandExecutor


class AAHExecutor(CommandExecutor):
    def __init__(self, command: str = "factory", mode: str = "dry_run") -> None:
        super().__init__("aah", command, mode)

    def build_args(self, packet: ExecutionPacket) -> Sequence[str]:
        # CLI contract del spec §17. `--profile auto` deja que el router de
        # AAH elija LITE/PRO/FACTORY; `--guardian guarded` es el default
        # razonable para trabajo normal (spec §6).
        return [self.command, "run", packet.objective,
                "--profile", "auto", "--guardian", "guarded"]
```

`mode="dry_run"` por defecto significa que, como todos los executors, el
primer registro es inocuo: reporta `Would execute: [...]` sin tocar nada.

## 3. Credenciales: allowlist con frozenset VACÍO

`EXECUTOR_SECRET_ALLOWLIST` en
`cano_hermes/runtimes/subprocess_executor.py:27-41` da a cada executor solo
las credenciales de su tier; un executor con `frozenset()` corre con **cero
secretos** (`build_env` los stripea todos y no restaura ninguno). La entrada
futura:

```python
EXECUTOR_SECRET_ALLOWLIST: dict[str, frozenset[str]] = {
    ...
    "aah": frozenset(),  # subscription-first: AAH usa los CLIs autenticados
                         # del host (spec §7); no recibe NINGUNA credencial.
}
```

Justificación: el spec §7 declara `subscription_only` como política de
facturación por defecto, "AAH must not silently fall back to paid API usage",
y "Provider authentication remains owned by the provider CLI. AAH does not
copy OAuth tokens into project files, prompts, logs, or Git". Darle una API
key a AAH sería contradecir su propio diseño y el aislamiento por tier de este
repo (cubierto por `tests/test_credential_isolation.py` — la entrada nueva
debe añadirse a ese test cuando exista el executor).

## 4. Mapeo runtime → executor

En `cano_hermes/orchestration/execution_service.py`, dos toques:

1. `AGENT_RUNTIME_TO_EXECUTOR` (líneas 34-41): añadir `"aah": "aah"` — un
   manifiesto de agente (`agents/**/*.yaml`) con `runtime: aah` enruta al
   executor nuevo.
2. `ExecutionService.__init__` (dict `self.executors`, líneas 72-78): añadir
   `"aah": AAHExecutor(mode=mode)`.

```python
AGENT_RUNTIME_TO_EXECUTOR: dict[str, str] = {
    "hermes": "hermes-agent",
    "api": "hermes-agent",
    "claude-code": "claude-code",
    "codex": "codex",
    "browser": "openclaw",
    "python": "container-sandbox",
    "aah": "aah",            # ← futuro
}
```

## 5. Comando y resultado estructurado

Comando por invocación (CLI contract, spec §17):

```bash
factory run "<objetivo>" --profile auto --guardian guarded
```

- `--profile auto`: el router de AAH puntúa complejidad/riesgo (spec §5) y
  elige LITE/PRO/FACTORY. StarHome no duplica esa decisión.
- `--guardian guarded`: default del spec §6 para trabajo normal. Tareas de
  alto riesgo (producción, pagos, auth) usarían `--guardian locked`, mapeable
  desde metadata del packet cuando se implemente.

**Parsing del resultado:** el spec promete "stable machine-readable CLI
output" recién en el **Milestone 7** (spec §23, "Hermes adapter and
hardening"). El formato exacto — ¿JSON en stdout?, ¿`factory report` sobre
`.aah/runs/RUN-*/FINAL_REPORT.md` + `STATE.json`? — **se confirmará cuando ese
milestone exista**. Hasta entonces el contrato solo asume lo que el spec §10-11
garantiza: run ID estable, `STATE.json`, `FINDINGS.json`, `EVIDENCE.jsonl` y
`FINAL_REPORT.md` bajo `.aah/runs/<RUN-ID>/` en el workspace. El executor
mapeará eso a `ExecutionResult` (summary desde FINAL_REPORT, status desde el
Final Gate determinista del spec §13, métricas desde STATE.json).

También relevantes a futuro: `factory status` / `factory resume` (runs
reanudables sin memoria conversacional, spec §10) encajan con reintentos del
Task Engine, y `factory rollback` con checkpoints Git (spec §18).

## 6. Perfil de modelo

Entrada futura en `cano_hermes/intelligence/profiles.py` (`DEFAULT_PROFILES`),
junto a `claude-subscription` y `codex-subscription` que ya modelan el patrón
"CLI por suscripción, cost_tier 1":

```python
ModelProfile("aah-subscription", "aah", "auto-routed", "cli", 1, 5, 5,
             True, False, True)
#            id                provider  model        runtime tier q ctx
#            supports_tools=True, supports_vision=False, subscription=True
```

- `runtime="cli"`, `cost_tier=1`: mismo tier que Claude Code y Codex — es
  consumo de suscripción, no de API.
- `model="auto-routed"`: AAH resuelve capabilities → modelo internamente
  (spec §8); StarHome no fija modelo.
- `subscription=True`: coherente con el `frozenset()` vacío de la sección 3.

## 7. Checklist de adopción

Ejecutar **solo cuando Cano avise** que el repo del harness tiene código
funcional, y en este orden estricto:

- [ ] 1. Clonar `syacreator09-sys/adaptive-agent-harness` a `~/repos/` (fuera
      de este repo; se invoca por contrato, no se absorbe).
- [ ] 2. `factory setup` — wizard de primera ejecución (spec §9): estrategia
      de provider, confirmación subscription-only (sí), política de calidad,
      perfil default, Guardian. Genera `factory.local.yaml` (fuera de Git).
- [ ] 3. `factory doctor` — verificar probes: CLIs detectados, sesiones
      autenticadas, Git, Docker.
- [ ] 4. Probar el perfil **LITE** con una tarea fixture pequeña y observable
      (p. ej. un script trivial con rubric binario) y revisar los artefactos
      de `.aah/runs/` a mano: SPEC, FINDINGS, EVIDENCE, FINAL_REPORT, y que el
      Final Gate rechace un run incompleto.
- [ ] 5. Confirmar el formato real del output machine-readable (Milestone 7)
      y actualizar la sección 5 de este documento con el contrato exacto.
- [ ] 6. **Recién entonces** escribir `cano_hermes/runtimes/aah.py` (sección
      2), la entrada en `EXECUTOR_SECRET_ALLOWLIST` (sección 3), el mapeo en
      `execution_service.py` (sección 4) y el perfil (sección 6), **con
      tests**: registro en `test_credential_isolation.py`, dry_run del
      executor, y parsing del resultado con fixtures del formato confirmado.

Nada de esto se adelanta: escribir el executor contra un CLI que no existe
produciría código no verificable, que es exactamente lo que tanto AAH como
este repo prohíben.

## 8. Qué NO se hará — nunca

1. **Nunca copiar tokens OAuth** de `~/.claude/` o `~/.codex/` hacia AAH, sus
   artefactos, prompts, logs o Git. El spec §7 y §19 lo prohíben del lado de
   AAH; del lado de StarHome, el allowlist vacío (sección 3) lo hace
   estructuralmente imposible.
2. **Nunca habilitar API spending** para AAH. El spec §26 lo lista como
   invariante ("API spending is never silently enabled") y la regla 5 del
   `CLAUDE.md` de este repo ("Do not enable paid APIs...") lo refuerza. Si un
   día se quisiera un adapter de API, requiere decisión explícita de Cano, no
   configuración silenciosa.
3. **Nunca dejar que AAH se auto-apruebe** dentro de StarHome. El invariante
   central del spec (§2, §26: "Producer != approver", "Agents cannot set
   DONE=true") coincide con la regla 10 del `CLAUDE.md` de este repo — "A
   worker cannot approve its own output" — y con `ApprovalService`
   (`cano_hermes/governance/approvals.py`), que lo impide en código. El Final
   Gate interno de AAH complementa pero **no sustituye** la aprobación de
   StarHome: un run "completo" según AAH sigue pasando por el circuito de
   aprobaciones de este repo.
4. **Nunca clonar ni vendorizar** el código de AAH dentro de este repo:
   invocación por contrato CLI, igual que `cano-ai-command-center` y
   `factory-ia-channel-v5`.
