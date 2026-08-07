# K11 — Memoria unificada (gbrain + graphify + Nexus)

**Fecha:** 2026-08-06 · **Ejecutor:** Sonnet (sin supervisión, "no
preguntes, decide y documenta") · **Rama:** `main`.

---

## 1. gbrain — GATE bloqueado, no se intentó portar (decisión ya tomada)

Confirmado de nuevo esta iteración, sin tocar nada de infraestructura de
Cano:

| Falta | Detalle |
|---|---|
| Credenciales Supabase | `database_url` con password del proyecto `gbrain-knowledge` (pooler `aws-1-us-east-1:6543`) vive solo en `~/.gbrain/config.json` de la máquina OMEN de Cano. No existe en el vault de esta máquina, en ningún `.env` accesible aquí, ni en `~/.secrets/`. |
| RLS sin resolver | Auditoría previa de la OMEN marca las 10 tablas de `gbrain-knowledge` con RLS deshabilitado. La propuesta de fix ya existe como `~/repos/cano-ai-command-center/docs/gbrain-rls-advisory.sql` (confirmado presente en esta iteración) — **sin aplicar**. Ese repo es solo-lectura para este agente (regla 1 del `CLAUDE.md` raíz), así que ni el advisory ni nada de ese repo se tocó aquí. |
| Alcance | Es infraestructura cloud de producción de Cano (Supabase), no de esta máquina — aplicar el advisory de RLS y decidir el nivel de acceso que un agente autónomo debería tener es una decisión suya, no algo que este agente pueda resolver por su cuenta. |

**Pasos exactos para cuando Cano quiera resolverlo:**

1. Aplicar `~/repos/cano-ai-command-center/docs/gbrain-rls-advisory.sql`
   contra el proyecto Supabase `gbrain-knowledge` (vía
   `mcp__claude_ai_Supabase__apply_migration` con sesión de Cano, o
   `supabase` CLI directo) — habilita RLS en las 10 tablas antes de
   exponerlas a cualquier agente.
2. Decidir si el acceso de agentes es de solo lectura (recomendado para el
   primer corte) o lectura/escritura, y con qué rol/policy.
3. Copiar `database_url` (o mejor, una API key/rol con permisos acotados
   por el paso 2, no el `service_role` completo) desde
   `~/.gbrain/config.json` de la OMEN a esta máquina — vía `hermes
   dashboard` o `.env`, **nunca pegado en el chat** (regla del `CLAUDE.md`
   raíz).
4. Con eso en mano, implementar `GBrainAdapter` (mismo contrato que
   `GraphifyAdapter`: `query(text, limit) -> list[dict]`, read-only) y
   pasarlo como tercer argumento opcional a `ContextBuilder` — el punto de
   extensión ya está preparado y documentado en
   `cano_hermes/nexus/context.py` (ver `ContextBuilder`'s docstring,
   sección "Extension point for a future gbrain adapter"). No hace falta
   rediseñar Nexus: es agregar una función y pasarla en
   `api/dependencies.py`/`api/app.py`/`mcp/nexus_server.py` igual que se
   hizo con `GraphifyAdapter` en esta misma iteración.

---

## 2. Nexus como fachada única — estado antes / después

### Antes de esta iteración

- `cano_hermes/nexus/context.py` ya existía (`ContextBuilder` +
  `ContextPacket`) mezclando `MarkdownVault` (búsqueda full-text) +
  `KnowledgeGraph` (vecindario de wikilinks `[[...]]`) — funcional pero
  **vault-only**.
- `cano_hermes/nexus/graphify_adapter.py` ya existía (`GraphifyAdapter`
  con `load()`/`summarize()`) pero **sin un solo caller** en todo el
  repo — importaba `graph.json` sin que nada lo usara. Muerto.
- `settings.vault_path` (`HERMES_VAULT_PATH` en `.env`) apuntaba a
  `vault` (relativo) — el vault de demo/fixture dentro del propio repo
  (`./vault/01-home`, `./vault/05-systems`, etc., 4 notas), **no** al
  vault real (`~/StarHomeVault`, mencionado en el `CLAUDE.md` raíz). El
  contexto que `GET /api/nexus/context` devolvía en producción venía de 4
  notas de ejemplo, nunca del vault real de Cano.
- `graphify` (CLI, `~/.local/bin/graphify`) estaba instalado y operativo
  (`graphify --help` funciona), pero **nunca se había corrido** contra
  este repo ni contra el vault — no existía `graphify-out/graph.json` en
  ningún lugar de la máquina.
- Se descubrió además un sistema separado y ya maduro,
  `~/repos/starhome-nexus` (binario `nexus`, ver `nexus --help`): dueño
  real de `~/StarHomeVault`, con sus propios comandos `query` / `context`
  / `memory-propose` / `memory-review` / `graph-index`. Es el "StarHome
  Nexus (memoria)" de la tabla de sistemas vivos del `CLAUDE.md` raíz —
  un repo y servicio *distintos* de `cano_hermes/nexus/` (este paquete).
  **No se tocó ese repo** en esta iteración: el plan K11 acota el trabajo
  a `cano-hermes-agentic-os` (`cano_hermes/nexus/` + `storage/sqlite.py`).
  Vale la pena que una fase futura decida si `cano_hermes/nexus/` debería
  delegar en el `nexus` CLI de `starhome-nexus` en vez de reimplementar
  búsqueda/contexto sobre el vault por su cuenta — hoy son dos caminos de
  lectura del mismo vault que no se pisan (ambos son solo-lectura salvo la
  promoción de candidatos del punto 3), pero es una duplicación real que
  merece revisión en K15 (mejora continua de memoria).

### Cambios de esta iteración

1. **`HERMES_VAULT_PATH` repuntado al vault real**: `.env` ahora tiene
   `HERMES_VAULT_PATH=/home/cano/StarHomeVault` (el repo local `./vault`
   queda como fixture de tests/`scripts/validate.py`, sin tocar).
   `MarkdownVault.__init__` gana `.expanduser()` para que un futuro
   `HERMES_VAULT_PATH=~/StarHomeVault` (con tilde) no se rompa
   silenciosamente. Verificado en vivo:
   `settings.vault_path.expanduser().exists() == True`, `ContextBuilder`
   devuelve notas reales de `~/StarHomeVault` (hoy solo tiene las
   plantillas de `nexus init`: `Home.md` + 4 templates en
   `01-Projects/05-Decisions/06-Procedures/11-Handoffs` — vault real pero
   todavía sin contenido operativo cargado, eso es trabajo de uso diario,
   no de esta fase).
2. **`GraphifyAdapter.query()`** — nuevo método, primer caller real del
   adapter. Busca nodos por término (label/id/source_file, mismo scoring
   que `MarkdownVault.search`), nunca lanza excepción (grafo ausente o
   corrupto → `[]`). Cubierto por 5 tests nuevos.
3. **`ContextBuilder` gana una tercera fuente opcional** (`graphify:
   GraphifyAdapter | None = None`, `graphify_graph_path`) — `off` por
   defecto así que todo caller anterior (incl. `test_foundation.py`, que
   sigue sin tocarse) obtiene exactamente el mismo `ContextPacket` que
   antes. `GET /api/nexus/context`, el tool MCP `nexus_context`
   (`cano_hermes/mcp/nexus_server.py`) y el nuevo campo
   `ContextPacket.graphify_matches` sí lo activan.
4. **Grafo real generado y verificado en vivo**: se corrió extracción AST
   (sin LLM, `graphify.extract`) sobre todo `cano_hermes/` (69 archivos) y
   se construyó el grafo con `graphify.build.build()` → **590 nodos, 1520
   aristas** en `graphify-out/graph.json`. Verificación real con el CLI,
   no simulada:
   ```
   $ graphify explain "ContextBuilder" --graph graphify-out/graph.json
   Node: ContextBuilder
     ID:        cano_hermes_nexus_context_contextbuilder
     Degree:    10
     <-- app.py [imports] ...
     <-- nexus_context() [calls] ...
   $ graphify path "ContextBuilder" "MarkdownVault" --graph graphify-out/graph.json
   Shortest path (1 hops): ContextBuilder --uses [INFERRED]--> MarkdownVault
   ```
   `graphify-out/` se agregó a `.gitignore` (artefacto derivado y
   regenerable, mismo trato que `build/`/`*.egg-info/`) — regenerar con
   `graphify update cano_hermes` (AST-only, sin LLM/API key). El
   `graph.json` generado hoy queda en disco local para que el contexto
   siga enriquecido sin esperar a que alguien lo regenere.

---

## 3. Lector + promoción humana de `memory_candidates`

- Confirmado con grep: `add_memory_candidate` (Prometeo F3) no tenía
  lector **ni tampoco ningún caller de escritura** en todo el repo —
  tabla completamente muerta en ambos sentidos antes de esta iteración.
- Nuevo: `SQLiteStore.list_memory_candidates(status=None)`,
  `get_memory_candidate(id)`, `resolve_memory_candidate(id, status,
  resolved_by)` (folds `resolved_by`/`resolved_at` dentro de `payload`,
  sin migración de esquema — mismo patrón que `save_order`).
- Nuevo: `cano_hermes/governance/memory_candidates.py` ·
  `MemoryCandidateService` — capa de gobierno sobre el store. Reusa el
  patrón anti-self-approval de `ApprovalService`, pero acotado: solo
  bloquea `decision="approved"` cuando el payload trae `proposed_by`
  (auto-rechazar tu propia propuesta no tiene el riesgo que sí tiene
  auto-aprobarla). Único camino en todo el codebase que escribe en el
  vault a partir de un candidato — nunca en el insert, solo en
  `resolve(..., "approved", ...)`.
- **Dónde vive la memoria promovida**: `~/StarHomeVault/00-Candidatos-Aprobados/<namespace>--<id>.md`
  — deliberadamente NO una de las carpetas canónicas del vault
  (`01-Projects`, `05-Decisions`, `06-Procedures`, `11-Handoffs`, que son
  "memoria activa" según la propia regla de `Home.md` del vault: "Los
  agentes proponen candidatos; no modifican memoria activa
  directamente"). El archivo queda marcado `status:
  approved_pending_index` — un humano todavía tiene que archivarlo en la
  carpeta canónica correcta; esta fase resuelve la aprobación, no la
  clasificación editorial final.
- Endpoints nuevos: `GET /api/memory/candidates` (filtrable por
  `?status=`), `GET /api/memory/candidates/{id}`, `POST
  /api/memory/candidates/{id}/resolve` (`{"decision": "approved"|
  "rejected", "actor": "..."}`).
- **Verificado en vivo contra el vault real** (no solo en tmpdir de
  tests): candidato de humo `smoke-1` propuesto, aprobado, archivo
  confirmado en `~/StarHomeVault/00-Candidatos-Aprobados/`, contenido
  verificado, y **borrado** después de la verificación — el vault real
  queda exactamente como estaba antes de esta iteración.

---

## 4. Tests y suite

- `tests/test_k11_memory_candidates.py` (16 tests): store round-trip,
  filtro por status, anti-self-approval (bloqueada en approve, permitida
  en reject), promoción real a archivo, candidato ya resuelto → 400,
  decisión inválida → 400, actor distinto → permitido, endpoints HTTP
  completos (200/403/404/400).
- `tests/test_k11_nexus_graphify.py` (8 tests): `GraphifyAdapter.query`
  (scoring, límite, grafo ausente, grafo corrupto, query en blanco),
  `ContextBuilder` sin adapter (comportamiento idéntico al anterior a
  esta fase) y con adapter (merge real de `graphify_matches`).
- Suite completa corrida dos veces (`unittest discover` y `pytest`) desde
  cero después de todos los cambios:

  ```
  python -m unittest discover -s tests   → Ran 236 tests, OK (skipped=2)
  python -m pytest                       → 239 passed, 2 skipped
  ```

  Piso previo: 214 unittest / 219 pytest. Ambos suben exactamente en 22
  (los tests nuevos de esta fase), cero regresiones.

---

## 5. Decisiones no triviales

1. **No se tocó `~/repos/starhome-nexus`** pese a que ya resuelve buena
   parte de "memoria + vault + candidatos" de forma más madura que lo
   construido aquí — el plan K11 acota el trabajo a este repo, y mezclar
   ambos sistemas sin que Cano decida cuál es la fuente de verdad sería
   diseño no autorizado. Queda anotado arriba como candidato a revisión
   en K15.
2. **`graphify-out/` gitignored, no versionado** — es un artefacto
   derivado (como `build/`/`*.egg-info/`), se regenera en segundos sin
   LLM. El grafo generado hoy (590 nodos/1520 aristas, AST-only sobre
   `cano_hermes/`) queda en disco local para que el contexto no dependa
   de que alguien lo regenere manualmente antes del primer uso.
3. **Anti-self-approval de memory candidates acotado a `approved`**,
   divergiendo deliberadamente de `ApprovalService` (que bloquea ambos
   sentidos) — justificado en el docstring de `MemoryCandidateService`:
   auto-rechazar no tiene el riesgo que sí tiene auto-aprobar (nada se
   escribe en el vault).
4. **`./vault/` local del repo no se tocó ni se borró** — sigue siendo el
   fixture que usan `tests/test_foundation.py` y `scripts/validate.py`;
   solo se dejó de ser la fuente que usa el server en runtime.
