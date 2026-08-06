# F9 — UGC-Affiliate: tramo gratuito end-to-end (dry-run, $0)

Fecha: 2026-08-06
Alcance: `cano-ai-command-center/01-offices/ugc-affiliate/` (checkout local, rama
`feat/factory-v5-upload-campaign-10-day`, commit `7560f56`) — **solo lectura**, sin
escritura en ese repo en ningún paso. Cero llamadas a RapidAPI/TikTok/ML/Higgsfield.
Cero publicación real.

---

## 1. Inventario y estado real (contra CLAUDE.md / RUNBOOK.md / STATUS.md / AUDIT_GAPS.md)

- `STATUS.md`: score `ready`, capacidades Codex/Claude adapter + OMC memory + Runbook = True.
- `RUNBOOK.md`: research/guiones/comparativas = seguro; uploads/compras/scraping pagado =
  bloqueado sin confirmación.
- `AUDIT_GAPS.md` (2026-05-22, post-verificación MCP Higgsfield real): plan Higgsfield
  **FREE**, 8 créditos (no alcanza para producir), 0 Soul characters creados. Acción P0:
  activar plan Ultimate $39/mo antes de producir video real — sigue sin resolver, no se
  tocó (fuera de alcance de F9, que es explícitamente gratis).
- `NEXT_ACTIONS.md`: apunta a un `D:/cano-ai-command-center/...` (rutas Windows) y a
  `.omc/handoff.md` que no existe en este checkout — confirma lo que ya reportó
  `command-center-contract`: el repo fue escrito para invocarse desde Windows.
- Confirmado (F1/F2/F7): no hay `.env` en `01-offices/ugc-affiliate/` ni `RAPIDAPI_KEY`
  en el `.env` raíz de command-center. Sin esa key, `rapidapi_client.py` /
  `tiktok_api_discovery.py` / `product_search.py --sources api` no pueden llamar a
  RapidAPI real — coherente con por qué este F9 usa los fixtures ya commiteados en vez
  de intentar descubrimiento en vivo.

## 2. Tramo gratuito ejecutado: scraper(fixture) → scout(scoring) → video-brief

### 2.1 Scraper → fixture

`01-products-research/discovered/*.json` (4 archivos commiteados, sin PII ni tokens):

| Archivo | Productos |
|---|---|
| `2026-05-23.json` | 15 |
| `2026-06-16.json` | 17 |
| `2026-06-18.json` | 47 |
| `2026-06-21.json` | 60 |
| **Total crudo** | **139** |

`fuente` de cada fila revela su origen real: `tiktok_api23` (corridas reales pasadas de
RapidAPI, cuando la key sí existía), y `dry_run` / `dry_run_web` / `dry_run_gstack`
(datos sintéticos de pruebas previas de los scrapers). **Hallazgo**: `2026-06-16.json`
contiene al menos un registro con huellas inequívocas de fixture de test unitario —
`"url": "https://www.tiktok.com/@a/video/1"`, `"autor": "a"`, `"video_id": "1"`,
`"imagenes": ["https://x/c1.jpg"]` (dominio `x` no existe) — mezclado con productos que
parecen reales. Cualquier consumidor de estos JSON como "productos del día" debe
filtrar por `fuente` antes de tratarlos como datos de producción.

### 2.2 Scout (scoring) — dos sistemas de scoring distintos, uno es código y el otro es prompt

**Hallazgo central**: el sistema de "100 puntos, mínimo 60" descrito en
`CLAUDE.md` §Criterios de scoring y en el agente `.claude/agents/ugc-product-scout.md`
**no está implementado en código** — existe solo como rúbrica para que un agente Claude
(`ugc-product-scout`) la aplique por juicio, producto por producto. El único scoring que
sí es código ejecutable es `scripts/recommender.py::score()`:

```python
score = 0.6 * norm(playCount, 0, 15_000_000) + 0.4 * norm(comision_mxn, 0, 150)
```

— una heurística 0–1 de virality×comisión para *rankear y asignar canal*, no un gate de
aprobación. `ugc-orchestrator.py` sí tiene un gate (`--score`, aborta si <60), pero ese
número tiene que **entrar como argumento ya calculado** — nada en el repo lo calcula
automáticamente a partir de un producto crudo.

**Ejecución real (offline, sin red)**: se importó `recommender.py` (solo lectura, sin
tocar el repo) desde un script en el scratchpad de StarHome, se cargaron los 139
registros de los 4 fixtures, se aplicó la misma lógica de dedup de `product_search.py`
(`nombre[:40].lower()`) y se llamó `recommend_by_channel()`:

```
[fixture] 139 filas crudas en 4 archivos discovered/*.json
[fixture] 137 productos únicos tras dedup
[fixture] 19 productos con comision_mxn > 0

> cano-digital: top score 0.5420 (240W charger, 13.5M views, comisión $0)
> sya-motive:   top score 0.1120 (organizador bambú, comisión $42, 0 views)
> sya-animals:  top score 0.6000 (pet hair cleaner, 19.4M views, comisión $0)  [tope de la fórmula]
> cass-health-beauty: top score 0.1918 (plancha Remington, comisión $72, 0 views)
> mujer-ugc:    top score 0.3236 (bolsa viral, 8M views, comisión $0)
> sin-nicho:    top score 0.6000 (Cheese/vegetable graters, cocina — fuera de los 5 nichos)
```

Corrida completa, código real, cero red, cero costo.

**Aplicación manual de la rúbrica de 100 pts (yo actuando como el agente
`ugc-product-scout`, sin llamar ningún LLM externo ni API)** a 3 candidatos
representativos, para poner a prueba el gate de 60 pts descrito en el plan:

| Producto | Comisión (25) | Visual (20) | Fit canal (20) | Viral (15) | Riesgo | Producción (10) | **Total** | Decisión |
|---|---|---|---|---|---|---|---|---|
| Plancha Remington (cass-beauty, real ML, $799/$72) | 15 | 20 | 20 | 5 | −5 | 2 | **57/100** | 🟡 EN ESPERA (55-59) |
| Pet hair cleaner (sya-animals, 19.4M views, TikTok real) | 0 | 20 | 20 | 10 | −5 | 7 | **52/100** | 🔴 RECHAZADO |
| Mini proyector 1080p $899 (cano-digital, fixture de test) | 20 | 20 | 20 | 10 | −5 | 7 | **72/100** | 🟢 PROCEDE — pero dato sintético |

**Conclusión del scout**: de los 3 candidatos evaluados con la rúbrica real de 100 pts,
ninguno "limpio" (dato real, no sintético) llega a 60. El único que pasa (72/100) es el
registro de `2026-06-16.json` identificado en §2.1 como fixture de test unitario
(`video_id: "1"`, `autor: "a"`). **Causa raíz del bloqueo**: los registros con
`fuente: tiktok_api23` (reales) casi siempre traen `precio_mxn: 0` y por tanto
`comision_mxn: 0` — la búsqueda de video de TikTok no expone precio de producto, así que
el eje de comisión (25 pts, el más grande) queda en 0 salvo que alguien complete el
precio manualmente. Los registros con comisión real (`fuente: dry_run_web/gstack`) son
ellos mismos sintéticos (de pruebas previas del scraper ML), no productos vivos.
**Esto es el hallazgo más accionable para F15**: el pipeline de descubrimiento actual no
cierra el ciclo precio→comisión→score sin un paso manual o un fetch adicional al
producto (que si es real, cuesta cuota).

### 2.3 Video-brief (aplicando `.claude/agents/ugc-video-brief.md` al único PROCEDE)

Brief generado como ejercicio — **no ejecutado, no consume créditos, no escribe en
command-center** — para "Mini proyector 1080p $899" en `cano-digital` (Valentina,
`cd6fb78c-e1a2-42f1-8b1e-902c15511877`):

```
Avatar: Valentina | Preset: Product Review (product_review) | Hook: Product Hit
Setting: Office | Res: 720p | generate_audio: false
Racional: gadget con demo visual obvia, canal tech encaja perfecto, fórmula de voz
70% valor/tutorial.

Script (≤30s, safe-copy):
"¿Buscas mejorar tu setup? Encontré este mini proyector 1080p que puede servirte —
se ve compacto y fácil de llevar. Lo dejé etiquetado abajo para que lo revises."

TTS: edge-tts --voice es-MX-DaliaNeural --text "..." --write-media voz.mp3

Caption TikTok: "📽️ Mini proyector 1080p que cabe en tu mochila — lo dejé linkeado
👆 #minitproyector #techfinds #setup #gadgetsdeoficina #tiktokshopmx"
```

Recordatorio explícito en el propio brief: el producto de origen es un fixture de test
(`video_id: "1"`), así que este brief es solo demostración del formato — **no debe
usarse para producir un video real** sin antes reemplazar el producto por uno con
`fuente: tiktok_api23` genuino y precio verificado.

## 3. Puente a producción — `factory-ia-channel-v5`

Búsqueda exhaustiva en `~/repos/factory-ia-channel-v5` (repo propio, editable):

- `affiliate_scout_adapter.py` — **no existe** (0 resultados, ni por nombre exacto ni
  variantes con "affiliate"/"ugc").
- `docs/integrations/ugc-affiliate-bridge.md` — **no existe** (la carpeta
  `docs/integrations/` no existe en ese repo).

Por instrucción explícita de F9: no se construye ni se inventa. Es un vacío real a
registrar para una fase futura si se decide puentear UGC-Affiliate → Factory V5.

## 4. `ugc-commerce-studio` — auditoría + tests + diseño de conexión a `office-ugc`

Repo propio, editable, ya con `.venv` presente (Python 3.12).

```
pip install -e ".[dev]"   → OK (cano-ugc-commerce-studio 0.4.0 + pytest 8.4.2)
python -m compileall -q src scripts   → OK
pytest -q                              → 11 passed
python scripts/check_release.py        → {"status": "PASS", "required_files": 16, "unsafe": []}
```

Smoke funcional gratuito (sin Higgsfield, `paid_generation: false` confirmado en el
output):

```
python -m ugc_commerce.cli plan --product examples/product.json \
  --profile examples/profile.json --output storage/plan.json
→ opportunity.score = 85.0, recommendation = PREMIUM_PRODUCTION, scenes = 5
```

`storage/plan.json` quedó escrito dentro de `ugc-commerce-studio` (repo propio, permitido),
no en command-center.

### Diseño de conexión como motor de `office-ugc` (F11, aún no construida — solo diseño)

`ugc-commerce-studio` ya tiene exactamente el contrato que `office-ugc` necesitaría
consumir: `ProductManifest` (JSON validado por `contracts/*.schema.json`) →
`Opportunity Score` (0-100, con `reasons`/`warnings`, distinto del score 0-1 de
`recommender.py` — no confundir los dos) → `CreativeMatrix` → plan Higgsfield inmutable
con `scope_id` → gate de aprobación → ejecución Higgsfield secuencial → draft-only.

Propuesta de cableado (documentación únicamente, nada de esto se construyó):

1. **Adaptador de formato** (nuevo, viviría en StarHome o en `ugc-commerce-studio`, no
   en command-center): mapear una fila de `01-products-research/discovered/*.json`
   (`nombre`, `precio_mxn`, `comision_pct`, `url`, `categoria`, `imagenes`) al
   `ProductManifest` de `ugc-commerce-studio` (`product_id`, `ownership_type: affiliate`,
   `platform`, `title`, `price_amount`, `commission_value`, `media_assets`,
   `commercial_rights_status`). Los campos que `ugc-affiliate` no captura hoy
   (`verified_benefits`, `prohibited_claims`, `commercial_rights_status`) tendrían que
   completarse a mano o vía el propio agente `ugc-product-scout` como parte de su output.
   Ver `docs/source-audit.md` en `ugc-commerce-studio` para el detalle de campos.
2. **Reemplazo de motor, no de política**: `office-ugc` reutilizaría el `Opportunity
   Score` + `CreativeMatrix` de `ugc-commerce-studio` en vez del score 0-1 de
   `recommender.py` (más completo, con `reasons`/`warnings` auditable) — pero seguiría
   respetando el gate ≥60/100 y el approval gate de ambos sistemas (son compatibles:
   ninguno permite producción sin aprobación explícita).
3. **Higgsfield sigue siendo el mismo bloqueo P0** que `AUDIT_GAPS.md` reportó en mayo:
   plan FREE / 8 créditos. Nada de esto cambia con la conexión propuesta.
4. **Avatares por canal (Sofia=sya-motive, Valentina=cano-digital, etc.)**: el mapeo
   canal→avatar ya existe por partida doble — `CHANNEL_CONFIG` en `ugc-orchestrator.py`
   (command-center, solo lectura) y `profile.avatar_id` en `ugc-commerce-studio`
   (editable). Cualquier paso que cree o active un Soul ID de Higgsfield para un canal
   queda **PENDIENTE_APROBACION** — es gasto, cae en el gate de Finanzas
   (`ApprovalService`, F5) y no se ejecutó nada de eso aquí.

## 5. Dedup y ledger

Ver skill nuevo `skills/reel-dedup-check/` (StarHome) para el detalle completo. Resumen:
no existía el skill ni un archivo literal `published_ledger.csv` en ningún repo
auditado. El mecanismo de dedup que sí existe hoy en producción es distinto de lo que
el nombre del archivo sugiere: una base SQLite
(`01-offices/ugc-affiliate/upload_log_ugc.db`, tabla `uploads`, clave
`canal+slug+fecha`, columna `req_id`) dentro de `scripts/uploaders/uploader.py` — no un
CSV. El skill nuevo documenta ambos (el nombre esperado por este mandato y el mecanismo
real encontrado) sin copiar ni modificar nada de esos repos.

## 6. Bloqueos y hallazgos para F15

1. **Gap precio→comisión en descubrimiento TikTok**: los productos con `fuente:
   tiktok_api23` reales no traen precio, así que el eje de comisión del scoring de 100
   pts queda en 0 y ningún producto "limpio" pasa el gate de 60 en las pruebas
   realizadas hoy. Se necesita un paso adicional (manual o de otra fuente) para cerrar
   precio antes de que el scout pueda aprobar honestamente.
2. **Fixtures de test mezclados con datos reales** en `01-products-research/discovered/`
   sin un campo booleano explícito de "es sintético" — solo se infiere por el valor de
   `fuente` y por huellas como `video_id: "1"`. Cualquier consumo automático de estos
   JSON como "productos reales del día" debería filtrar por `fuente` primero.
3. **`published_ledger.csv` no existe** en ningún repo auditado (command-center ni
   `ugc-commerce-studio`); el dedup real de publicación vive en una SQLite
   (`upload_log_ugc.db`) sin video ID de plataforma persistido, solo `req_id` del SDK de
   upload-post. Si F15 o una fase posterior quiere una regla dura de "nunca publicar sin
   video ID real verificable", falta ese campo en el esquema actual
   (`tracking_entry.json` tampoco lo tiene — ver `TRACKING_SHEET_SCHEMA.md` columna 12
   `url_video_tiktok`, declarada pero no poblada por el código actual).
4. **`affiliate_scout_adapter.py` y `docs/integrations/ugc-affiliate-bridge.md`
   no existen** en `factory-ia-channel-v5` — el puente descrito en el mandato F9 §3 es
   aspiracional, no construido. No se creó en esta fase (no estaba pedido).
5. Higgsfield sigue bloqueado por plan FREE (8 créditos, 0 Soul characters) — sin
   cambios desde `AUDIT_GAPS.md` (2026-05-22). Cualquier producción real de video sigue
   requiriendo aprobación de gasto (Finanzas, F5) antes de continuar.
