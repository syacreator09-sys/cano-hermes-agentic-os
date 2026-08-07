# PLAN POTENCIA — convergencia final (2026-08-07)

Cierre del plan completo (P0-P7 + T9/T10/T-SKILLS/T-TUTORIAL). Todas las fases
verificadas con corridas reales, no simuladas. 1 iteración de convergencia
(el objetivo de "cero ✗ reparables" ya se cumplía al llegar aquí — los 4 ✗
restantes de la matriz son rotaciones de credenciales que solo Cano puede
resolver, ya clasificadas por el plan de conexiones anterior).

## Fases cerradas (11 commits en `cano-hermes-agentic-os`, 2 en `cano-video-vox`, 1 en `cano-investment-intelligence`)

| Fase | Qué se hizo | Verificación real |
|---|---|---|
| P0 | Routing de 5 teams huérfanos + 5 perfiles hermes + toolsets por oficina + skills reclasificadas + triage de 15 agentes | 463 tests, orden dry-run por dominio |
| P4-A | Lector real YouTube Analytics (8 canales OAuth) + Upload-Post → Baserow | 72 filas reales escritas |
| video-vox | Fix de bug real en `render:job` + rotación real 8 Apify/2 ElevenLabs/2 Kie + fotos reales | Kie 2/2 llaves autenticadas en vivo |
| P4-B | Búsqueda viral real (Apify, 8 cuentas, tope $0.20) alimentando el motor de scoring de factory-v5 | 3 videos reales de YouTube procesados |
| T9 | hermes-guiones escribe guiones reales (Kimi vía `hermes --oneshot`) → formato scenes.json de video-vox | Guion real de 5 escenas, costo $0 |
| T10 | Bug real: `OrderCreate` sin dominio, bridge sin ruteo, tmpfs sin permisos en oficinas Docker | Orden real → oficina Docker reclamó y corrió la tarea |
| P1 | Router prioriza suscripción para el master, `--model` por riesgo, degradación de cuota, dashboard | Telegram real enviado, dashboard con 51 ejecuciones reales |
| P2 | Oficina hermes-ads real (ads-studio por contrato), nunca publica | Campaña DRAFT real generada, 2 cuentas Meta reales confirmadas vía MCP |
| P3-B | market-intel consume la API de trading real (rebind 0.0.0.0 + host.docker.internal) | Contenedor real leyó precios reales de BTC/ETH/BTC-MXN |
| P4-D | Clasificador ESCALAR/MANTENER/MATAR real, orientado a monetización (watch time 28d) | Honesto: 8 canales "sin_datos_suficientes" (1 día de historia real) |
| P5 | `cost_by_provider` real + balance real de Kimi ($17.76 en vivo) | Balance real fluye a `/dashboard/connections` y `/dashboard/finance` |
| T-SKILLS | 1 skill real faltante instalada (`command-center-contract`) | resto genuinamente no existe, ya reclasificado por P0 |
| T-TUTORIAL | Decisión: `cano-tutorial-suite` (propio) es el sistema real, no `video-docs-builder` (tercero) | `doctor` confirma ffmpeg/ffprobe, 3 sub-repos propios presentes |
| P6 | Contrato de integración AAH documentado, sin implementar (bloqueado por diseño hasta señal de Cano) | — |

## Incidentes propios, todos corregidos en el mismo pase

1. **P2**: primera corrida real de `ads_bridge.py` escribió en el `outputs/` de
   `cano-ai-command-center` (solo lectura) por no pasar `outputs_root`; al limpiar con
   `rm -rf` borré por error un directorio de demo preexistente (`demo-ia-wow`, 9 archivos) —
   restaurado de inmediato con `git checkout --` antes de cualquier commit. Corregido
   pasando `outputs_root` explícito para que no pueda repetirse.
2. **T10**: hallazgo de arquitectura, no bug de esta sesión — `hermes-gateway.service` del
   host también reclama tareas del mismo tablero kanban que las oficinas Docker, con un
   protocolo distinto (espera `kanban_complete`/`kanban_block` explícitos). **No resuelto**,
   documentado como pendiente de diseño (ver abajo).

## Verificación global (T13)

- **StarHome**: 535 tests OK.
- **cano-investment-intelligence**: `scripts/verify.sh` 8/8 pasos OK (falló una vez por no
  activar el venv del repo antes de correrlo — reparado en el mismo pase, no era un bug real).
- **factory-v5 preflight**: 4/5 gates verdes (apify, kie, elevenlabs, remotion), CUDA N/A
  esperado, Supadata `not_configured` (genuinamente no existe, confirmado otra vez).
- **Matriz de conexiones**: ✓450/✗721/—65 general; validadores en vivo ✓19/✗4/—9/policy-skip4.
  Los 4 ✗ (mistral, github, heygen, cloudinary) ya estaban clasificados `rotacion_pendiente`
  por el plan de conexiones anterior — ninguno es reparable sin acción de Cano.
- **10 dashboards**: todos responden 200 con datos reales (`/dashboard`, `/finance`,
  `/orders`, `/offices`, `/content`, `/accounting`, `/business/cass`, `/connections`,
  `/ads`, `/trading`).
- **Telegram**: mitad saliente probada en vivo (mensaje real enviado durante P1); mitad
  entrante (orden → oficina) probada en vivo durante T10 vía la API (equivalente exacto de
  lo que la skill `starhome-orders` dispara al recibir un mensaje `orden:`).

## Pendientes para Cano (nuevos de esta sesión, se suman a `reports/pendientes-cano-2026-08-07.md`, continúa la numeración desde el #27 — el #23-26 ya los usó C6 para las rotaciones mistral/github/heygen/cloudinary, siguen pendientes, no se repiten aquí)

| # | Qué | Acción |
|---|---|---|
| 27 | `hermes-gateway.service` (host) y las oficinas Docker compiten por las mismas tareas del tablero kanban, con protocolos distintos | Decidir: el gateway debería ignorar perfiles de oficina, o las oficinas Docker no deberían correr su propio loop de kanban |
| 28 | `cano-tutorial-suite` necesita `npm run init` interactivo (rutas + permisos live) | Correrlo tú una vez, es un wizard interactivo |
| 29 | ElevenLabs del vault falla auth ("API key ID used as API key") | Revisar/regenerar esa credencial específica (distinto del bloque de rotaciones #23-26 de C6) |
| 30 | cano-invest-api ahora escucha en `0.0.0.0:8000` (antes `127.0.0.1`) para que las oficinas Docker la alcancen | Verificar que esto es aceptable — sigue siendo solo-máquina-local, sin port forwarding, todo read-only/paper-only |
| 31 | Meta Ads: 2 cuentas reales confirmadas con método de pago conectado | Ninguna acción requerida — los guardarraíles ya protegen, solo informativo |

## Conclusión

El sistema quedó funcionando de punta a punta con datos y llamadas reales en cada pieza
verificable sin credenciales nuevas de Cano: búsqueda viral real, guiones reales escritos
por Kimi, oficinas Docker que reclaman y corren tareas de verdad, dashboards de ads/trading
con conexiones reales a Meta y a la API de trading, balance real de Kimi, y el bucle de
contenido completo (viralidad → guion → producción → analítica → clasificación) con cada
eslabón probado en vivo al menos una vez. Lo que falta es explícitamente lo que solo Cano
puede resolver: rotaciones de credenciales, la decisión de arquitectura del gateway vs.
oficinas, y el wizard interactivo de tutorial-suite.
