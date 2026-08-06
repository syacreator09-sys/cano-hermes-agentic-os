# office-market-intel — design only (F14)

Fecha: 2026-08-06. Fase: Plan Prometeo F14. **No se construye el contenedor en
esta fase** — F11 ya cerró la construcción de infra Docker (Baserow + 4
oficinas núcleo). Este documento es diseño/scaffold, análogo a como quedaron
`office-content`/`office-publish` en F11 (ver
`infrastructure/offices/content/README.md` y
`infrastructure/offices/publish/README.md`): describe la 5ª oficina para que
F15/una fase futura la construya, sin inventar comportamiento que no exista
todavía en ninguno de los tres repos que unifica.

## 0. Regla dura que gobierna todo este documento

**CERO trading real, CERO compra real, CERO credencial de broker en ningún
lado, tocada por ningún LLM.** Esto no es una preferencia de diseño — es una
regla explícita del propio repo `cano-investment-intelligence`
(`docs/architecture/system-architecture.md:138`: *"Ningún LLM tendrá acceso a
`BrokerPort`"*) y se hereda sin relajar a esta oficina. Todo lo que sigue está
subordinado a esa frase.

## 1. Qué unifica

`office-market-intel` combina tres señales que hoy viven en tres repos
separados, sin fusionarlos ni absorber ninguno:

| Señal | Fuente | Qué produce | Estado real (F14) |
|---|---|---|---|
| Financiera | `~/repos/cano-investment-intelligence` (rama `build/full-platform-v0.1`) | Council estructurado con veto (`RiskGuardian`, código determinístico), síntesis CIO, `live_execution: false` siempre | 137/138 tests Python en verde + 7/7 Node en verde (ver hallazgo F14 abajo); council offline probado, cero routing de pago activado |
| Producto físico | `~/repos/amazon-fba-product-hunter` | Score 0-100 y decisión `APROBADO` / `APROBADO_CON_CAUTELA` / `DESCARTADO` (`src/agents/scorer_agent.py`) | Research-only, scraping respetuoso, sin compras — ver registro en `docs/SKILLS_MATRIX.md` |
| Tendencia/contenido | `trend-scout` / Apify / research de `ugc-commerce-studio` (auditado en F9) | Señales de tendencia (ej. TikTok) ya conectadas a `office-ugc` (`RAPIDAPI_KEY`, `APIFY_API_KEY`, ver `infrastructure/offices/docker-compose.yml:96-97`) | Pipeline F9 más completo, aún sin dispatch real (dry-run/fixtures) |

Ninguna de las tres fuentes se absorbe dentro de esta oficina: se consumen
**por contrato**, igual que `office-content` consume `factory-ia-channel-v5`
de solo lectura y `office-ugc` consume `ugc-commerce-studio` de solo lectura.
`office-market-intel` seguiría ese mismo patrón — monta los tres repos como
`:ro`, nunca los modifica desde dentro del contenedor.

## 2. Flujo cruzado hacia `market-intel-daily.md`

Un ciclo diario (mismo patrón que `scripts/daily_cycle.py` de F13, que ya
escribe `reports/daily/<fecha>.md` + filas en Baserow) correría tres
lecturas read-only y produciría **un** reporte de síntesis,
`reports/daily/market-intel-daily-<fecha>.md`, con dos reglas de cruce
explícitas:

1. **Producto físico con score alto en FBA + tendencia TikTok activa** →
   candidato propuesto a `office-ugc`. Regla: `fba_score >= 70` (umbral
   "APROBADO" real de `scorer_agent.py`) **y** el mismo nicho/keyword aparece
   en la salida de `trend-scout`/Apify de las últimas 72h → se escribe una
   fila nueva en la tabla Baserow `productos_ugc` (F11, esquema real en
   `infrastructure/baserow/setup_schema.py:115-124`: `nombre`, `canal`,
   `precio_mxn`, `comision_mxn`, `score`, `fuente`, `url`, `estado`) con
   `estado = "descubierto"` y `fuente = "market-intel"`. Nunca `"procede"` —
   ese estado lo cambia un humano o un flujo de aprobación downstream, no
   esta oficina.
2. **Tendencia macro de investment-intelligence** (ej. hallazgo del council
   offline sobre un sector/commodity) → prioriza qué nichos de contenido
   `factory-v5` (vía `office-content`) debería tratar primero. Esto es una
   *sugerencia de orden*, no una instrucción de producción: se escribe como
   una lista ordenada en el reporte diario, no como un comando ejecutado.

Ambas reglas son **propuestas escritas a datos**, nunca acciones. La oficina
no llama a ningún endpoint de compra, orden, publish o dispatch — ni directa
ni indirectamente vía otra oficina.

## 3. La oficina PROPONE, nunca ejecuta

Igual que `office-publish` (F11) nunca publica sin que `ApprovalService`
resuelva un `ApprovalRequest` humano fuera del contenedor,
`office-market-intel`:

- **Escribe** en Baserow (`productos_ugc`, tabla ya existente desde F11 —
  ninguna tabla nueva que crear) y en el reporte diario agregado de F13
  (`reports/daily/`).
- **Nunca** ejecuta compras (FBA), trades (investment-intelligence) ni
  producción (factory-v5) por sí sola. Cualquier avance de una propuesta más
  allá de "escrita en Baserow/reporte" requiere una acción humana o de otra
  oficina fuera de este contenedor, con su propio gate.
- No tiene credenciales de publicación (`UPLOAD_POST_*`, `TIKTOK_*`,
  `META_*`) ni de broker/marketplace, siguiendo la misma prohibición
  explícita que ya aplica a `office-publish` en
  `infrastructure/offices/docker-compose.yml:138-140`.

## 4. Risk Guardian con veto determinístico

`cano-investment-intelligence` ya implementa esto como código, no como
prompt: `docs/risk/risk-guardian.md` documenta los defaults V0.1 (posición
máx. 10%, apalancamiento máx. 1x, drawdown esperado máx. 35%, liquidez mín.
45/100, calidad de evidencia mín. 65/100, `live_execution: false`), y
`docs/architecture/system-architecture.md:94-121` confirma que corre
**después** del análisis numérico y **antes** de que la salida del CIO se
vuelva accionable, con estados de salida cerrados
(`approved`/`approved_reduced`/`monitor`/`research_more`/`paper_trade_only`/
`rejected`/`insufficient_data`) — nunca un estado libre que un LLM pueda
inventar.

**Cómo se conectaría al `ApprovalService` de F3** (diseño, no implementado
aún):

1. `office-market-intel` invoca el council offline de investment-intelligence
   (`POST /v1/council/offline`, mismo endpoint que usa `scripts/verify.sh`)
   dentro de su propio contenedor/proceso, con datos read-only.
2. Si `RiskGuardian` devuelve cualquier estado que no sea `rejected` o
   `insufficient_data` (es decir, hay algo potencialmente accionable, aunque
   sea solo `paper_trade_only`), la oficina **no actúa** — construye un
   `ApprovalRequest` (mismo modelo que usa StarHome,
   `cano_hermes.domain.models.ApprovalRequest`) con `requested_by =
   "office-market-intel"` y lo pasa a `ApprovalService.request(...)`.
3. `ApprovalService.resolve(...)` (`cano_hermes/governance/approvals.py:17-26`)
   ya impide en código que el solicitante resuelva su propia solicitud
   (`if approval.requested_by == actor: raise PermissionError(...)`) — esta
   oficina hereda esa garantía sin tener que reimplementarla: **un agente no
   aprueba su propio trabajo**, la misma regla del `CLAUDE.md` raíz de esta
   máquina.
4. Solo Cano, resolviendo la aprobación fuera del contenedor, puede mover una
   propuesta financiera más allá de "propuesta escrita". Ningún routing a
   GPT/Claude de pago se activa en este flujo — el council de
   investment-intelligence corre offline (modelos locales/gratuitos), y el
   gate de Finanzas que F5 construyó sigue bloqueando cualquier escalamiento
   a Tier 3 sin aprobación explícita.

## 5. LLMs jamás tocan credenciales de broker (reafirmación explícita)

- `investment-intelligence` ya lo garantiza en su propio código:
  `docs/architecture/system-architecture.md:138` — *"Ningún LLM tendrá acceso
  a `BrokerPort`"* — y `Execution Plane` está deshabilitado desde el diseño
  (`system-architecture.md:123-138`): servicio independiente, credenciales
  aisladas, sin permisos de retiro, aprobación humana, kill switch,
  reconciliación, paper trading antes de capital real.
- `office-market-intel`, si se construyera, seguiría el mismo patrón de
  aislamiento de credenciales por tier que ya usan las 4 oficinas de F11
  (`cano_hermes/runtimes/subprocess_executor.py`): su `environment:` en
  Docker Compose listaría, por nombre, exactamente lo que necesita
  (`KIMI_API_KEY`/`KIMI_BASE_URL` para el supervisor Tier 0, más
  `RAPIDAPI_KEY`/`APIFY_API_KEY` que `office-ugc` ya tiene allowlisted) — y
  **nunca** ninguna variable de broker/exchange (`ALPACA_*`, `IBKR_*`,
  `BINANCE_*` o similar). Ese tipo de credencial no tiene ninguna razón para
  existir dentro de un contenedor que solo lee, sintetiza y propone.

## 6. Presupuesto de infraestructura (F11 ya cerrado; F14 evalúa, no construye)

Presupuesto real de F11 (`infrastructure/offices/docker-compose.yml:22-30`,
confirmado con `docker stats` en esta fase):

| Servicio | Memoria | CPU |
|---|---|---|
| `baserow` | 2g (uso real observado: 1.855GiB) | 1.0 |
| `office-analytics` | 1g | 0.2 |
| `office-ugc` | 1.5g | 0.2 |
| `office-content` | 1g | 0.2 |
| `office-publish` | 1g | 0.2 |
| **Total** | **6.5g** | **1.8** |
| Techo global | 8g | 2.0 |
| **Margen restante** | **1.5g** | **0.2** |

Este techo es una decisión de gobierno (dejar margen para agentes CLI,
sandbox F3, etc.), no un límite físico — la máquina tiene 31GB RAM / 4 CPUs
reales con >27GB libres al momento de esta fase. El límite es intencional y
no se relaja aquí.

**Hallazgo F14 (por qué no se levantó nada de investment-intelligence en
Docker esta fase):** el `docker-compose.yml` de `cano-investment-intelligence`
(`api` + `dashboard`) **no declara `mem_limit` ni `cpus`** — a diferencia de
las 4 oficinas de F11, que sí traen límites explícitos. Además, a diferencia
del patrón "bajo demanda" de las oficinas F11 (sin `profiles:` por defecto,
cero contenedores hasta que se pide una oficina por nombre), el compose de
investment-intelligence **no tiene `profiles:`** — `docker compose up` sin
flags lo levantaría como servicio de pie, no como ciclo bajo demanda. Un
servicio FastAPI/uvicorn de pie necesita, de forma realista, del orden de
0.3–0.5 CPU para no quedar hambriento en una máquina de 4 núcleos ya
compartida con agentes — eso por sí solo consume 150–250% del margen de CPU
restante (0.2). Memoria probablemente sí cabría (estimado 1–1.5g contra 1.5g
de margen), pero CPU no tiene espacio, y el propio mandato de esta fase pide
no forzarlo si no cabe "holgado". **Decisión: diferido.** No se corrió
`docker compose up` en `cano-investment-intelligence` en esta fase.

Si una fase futura quiere levantarlo, necesitaría primero: (a) añadir
`mem_limit`/`cpus` explícitos a su `docker-compose.yml` (hoy ausentes), y (b)
convertirlo al patrón bajo-demanda (`profiles:`) igual que las 4 oficinas de
F11, en vez de servicio de pie, para no competir permanentemente por el
margen de CPU con el resto de la infra.

`office-market-intel` en sí **no se dimensiona en este documento** más allá
de la nota anterior — no hay contenedor que construir todavía (F11 cerró esa
fase); cuando se construya, debería seguir el mismo patrón de límites
explícitos + `profiles:` bajo demanda que las 4 oficinas existentes, y
sumarse al mismo techo de 8g/2cpu, ya con solo 1.5g/0.2cpu de margen
disponible — es decir, esta 5ª oficina tendría que ser más liviana que
cualquiera de las 4 actuales (ej. `office-analytics`, la más ligera con
1g/0.2cpu, como referencia de techo razonable) para caber sin volver a abrir
la conversación de presupuesto global.

## 7. Qué NO hace esta oficina (explícito, para que F15 no lo reinterprete)

- No coloca órdenes, no ejecuta trades, no compra inventario FBA, no publica
  contenido.
- No tiene acceso a ningún `BrokerPort` ni credencial equivalente.
- No aprueba sus propias propuestas (`ApprovalService.resolve` ya lo impide
  en código si esta oficina alguna vez actuara como `requested_by` y
  `actor` al mismo tiempo).
- No activa routing de pago (Tier 2/3) — el council de
  investment-intelligence corre offline; cualquier escalamiento a
  OpenRouter/Anthropic/OpenAI real pasa por el gate de Finanzas de F5, fuera
  del alcance de esta oficina.
- No se construye como contenedor en esta fase (F14 = diseño únicamente).

## 8. Referencias

- `~/repos/cano-investment-intelligence/docs/architecture/system-architecture.md`
- `~/repos/cano-investment-intelligence/docs/risk/risk-guardian.md`
- `~/repos/cano-investment-intelligence/docs/research/github-upstreams.md`
- `~/repos/amazon-fba-product-hunter/src/agents/scorer_agent.py`
- `~/repos/cano-hermes-agentic-os/infrastructure/offices/docker-compose.yml`
- `~/repos/cano-hermes-agentic-os/infrastructure/offices/content/README.md`
  (patrón de README "design only" que este documento sigue)
- `~/repos/cano-hermes-agentic-os/cano_hermes/governance/approvals.py`
- `~/repos/cano-hermes-agentic-os/infrastructure/baserow/setup_schema.py`
  (esquema real de `productos_ugc`)
- `~/repos/cano-hermes-agentic-os/scripts/daily_cycle.py` (patrón de reporte
  diario que `market-intel-daily.md` seguiría)
- `~/repos/cano-hermes-agentic-os/docs/SKILLS_MATRIX.md` (fila F14
  `office-market-intel`, registrada previamente en F6/F14)
