# factory-v5-contract

Invocar Factory V5 (`~/repos/factory-ia-channel-v5`) por contrato, sin absorberla.
Este skill SOLO LEE ese repo (`scripts/factory.py` vía subprocess) — nunca lo edita,
nunca escribe dentro de su árbol. Es un sistema externo con su propio ciclo de vida
(regla dura del `CLAUDE.md` raíz: "Nunca absorber factory-ia-channel-v5").

## Contrato de invocación

```bash
cd ~/repos/factory-ia-channel-v5
source .venv/bin/activate   # el repo trae su propio venv con pydantic_settings, etc.
python scripts/factory.py <comando> [args]
```

- El ejecutor es `subprocess`, con `cwd` fijado al repo de Factory V5 y sin escritura
  fuera de sus propios directorios de trabajo (`.factory/`, `.nexus/`, `logs/`, que son
  del propio repo, no de StarHome).
- Credenciales: el `.env` de `factory-ia-channel-v5` (armado en F1), aislado por tier
  como el resto del ecosistema (`cano_hermes/runtimes/subprocess_executor.py`).

## Dry-run por defecto

Igual que el resto de StarHome (`cano_hermes/governance/policy.py`):
`SENSITIVE_ACTIONS = {"paid_api","publish","deploy","send_external_message","delete","merge","credential_change","production_write"}`.

Comandos de `factory.py` que caen en esas categorías (p.ej. `kie`, `upload-post-dry-run`
sin el flag dry-run, `remotion` con render real, `campaign-command` con ejecución real,
`editorial-explainer-render`) **requieren `ApprovalRequest` real** vía
`governance/approvals.py` antes de ejecutarse — no se disparan solos. Comandos de solo
lectura/plan (`provider-health`, `validate-yaml`, `route`, `compute-route`,
`asset-recommend`, `list-*`, `*-status`, `*-doctor`, `secure-config-audit`) corren
directo, son seguros por diseño (`SAFE_DRY_RUN_ACTIONS`: read/plan/simulate/validate/test).

Nadie aprueba su propio trabajo (`ApprovalService.resolve` lo bloquea si
`requested_by == actor`).

## Procedure

1. Confirmar objetivo, comando exacto de `factory.py` y si cae en `SENSITIVE_ACTIONS`.
2. Recuperar contexto mínimo desde Nexus (histórico de invocaciones a Factory V5).
3. Si el comando es de solo lectura/plan → ejecutar directo en el venv del repo.
   Si es sensible → crear `ApprovalRequest` (schema F3.1: `requested_by`, `action`,
   `reason`, `risk`, `costo_estimado_usd` si aplica) y esperar resolución humana.
4. Ejecutar por subprocess, `cwd=~/repos/factory-ia-channel-v5`, sin tocar el repo.
5. Validar salida (stdout/JSON) contra lo esperado; capturar exit code.
6. Registrar evidencia (comando, salida, costo si hubo) y aprendizajes candidatos en Nexus.

## Gap conocido — NO inventar, NO generar

`runtime/stage-handlers.yaml` **no existe** en `~/repos/factory-ia-channel-v5`
(confirmado: `find` sobre el repo no encuentra ni el archivo ni el directorio
`runtime/`). Es un pendiente manual de Cano — el archivo viene de la máquina OMEN y
debe copiarse desde ahí. Mientras falte, cualquier comando de `factory.py` que dependa
de `runtime/stage-handlers.yaml` (pipeline de stages/handlers) fallará o quedará
incompleto. Este skill NO debe generar un `stage-handlers.yaml` sintético — eso
correspondería a absorber/adivinar contenido de un sistema externo, violando el
contrato.

## Smoke test (2026-08-06)

```
cd ~/repos/factory-ia-channel-v5 && source .venv/bin/activate
python scripts/factory.py provider-health
```

Resultado: **éxito** (exit 0), JSON con estado de `apify` (configured), `moneyprinter`
(not_configured, fallback stock+remotion), `coverr`/`pexels`/`pixabay`/`local_asset_bank`
(stock_router con fallback_order correcto), `modal_gpu` (perfil `default` configurado,
`primary`/`secondary` no). Nada pagado se disparó — `provider-health` es de solo lectura.

Nota: fuera del `.venv` del propio repo, `provider-health` falla con
`ModuleNotFoundError: No module named 'pydantic_settings'` — el repo depende de su
propio entorno virtual (`~/repos/factory-ia-channel-v5/.venv`), no del intérprete de
sistema. Este skill siempre debe activar ese venv antes de invocar `factory.py`.
