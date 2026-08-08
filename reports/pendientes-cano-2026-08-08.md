# Pendientes de Cano — tabla vigente (2026-08-08)

Reemplaza `reports/pendientes-cano-2026-08-07.md` (queda como histórico). Los
pendientes #23-26 (rotaciones), #28 (tutorial-suite init) y #29 (ElevenLabs) siguen
exactamente igual, sin novedad hoy — no repetidos abajo, ver el archivo anterior.
#27 se resolvió en plan AUTONOMÍA TOTAL A1 (`dispatcher_deny_profiles`). #30 se
revisó a fondo en A6: confirmado que es un tradeoff deliberado y ya documentado
(no un bug), la mitigación real (`ufw`) sigue necesitando `sudo`.

Detalle completo del plan que generó los pendientes #32-36 en
`reports/autonomia-convergencia-2026-08-08.md`.

| # | Qué | Acción |
|---|---|---|
| 32 | `adaptive-agent-harness` main recibió el merge de `hardening/lite-pro-factory-v2` (arquitectura v0.2.0, contrato sellado) sin tu revisión previa — lo pediste explícitamente, pero vale revisarlo | Revisar commit `fb6c5e3` en `adaptive-agent-harness` cuando puedas |
| 33 | **Oficinas Docker no pueden reportar su propia finalización a StarHome** — el plugin `starhome-bridge` no está montado ni habilitado en ningún contenedor de oficina (confirmado con `docker inspect`: ni el código del plugin ni el secreto HMAC llegan al contenedor). Toda orden que dependa de una oficina Docker se queda pegada en `dispatched` hasta una intervención manual | Decidir el mecanismo correcto: montar plugin+secreto en los contenedores (evaluar impacto en el aislamiento de credenciales actual) vs. que StarHome haga polling en vez de esperar un webhook |
| 34 | El fix del pendiente #27 (`dispatcher_deny_profiles`) está pusheado a tu fork `syacreator09-sys/hermes-agent`, rama `pendiente-27-kanban-deny-profiles` — NO en el `main` local ni activo en `hermes-gateway.service` | Decidir cuándo aplicar y reiniciar (`systemctl --user restart hermes-gateway.service`) |
| 35 | Carrusel (factory-v5) sigue bloqueado en generación real de píxeles — depende de una herramienta nativa de ImageGen de Codex que ni Sonnet ni un script Python pueden invocar por sí solos | Evaluar una integración con proveedor de imagen real (Kie, etc.) en vez de depender de Codex-en-el-loop |
| 36 | `config/virality_niches.yaml` con `proveedor_visual: kie\|stock` por canal no existe en `cano-hermes-agentic-os` — el ruteo real de proveedor ya vive en `factory-ia-channel-v5/channels/<id>/channel.yaml` | Decidir si quieres un archivo espejo aquí o si el de factory-v5 ya basta |

## Informativo, sin acción requerida

- Plan AUTONOMÍA TOTAL (A0-A7) cerrado completo, con verificación real en cada
  fase — ver `reports/autonomia-convergencia-2026-08-08.md`.
- 2 ramas nuevas en `adaptive-agent-harness` (`audit/loop-20260807`,
  `hardening/lite-pro-factory-v2`) revisadas; la segunda fusionada a `main` (#32
  arriba). Ramas `build/v1*` confirmadas obsoletas/duplicadas, seguras de borrar
  cuando quieras (housekeeping, no urgente).
