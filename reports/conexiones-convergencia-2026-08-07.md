# Convergencia PLAN CONEXIONES (C0-C6) — 2026-08-07

Cierre del plan completo `fluffy-twirling-lecun.md`. Rama `main`, partiendo de
`58fb487` (C0-C5 ya en main). Esta fase es C6: bucle de convergencia sobre los
7 `✗` conocidos de la matriz de conexiones, máx. 3 iteraciones, más la
verificación global de todo el plan.

## Resumen de fases (una línea cada una)

- **C0** — `config/key_registry.yaml` (273 llaves con dueño/uso/dominio),
  `scripts/build_key_registry.py` (escaneo de consumidores + `--check` de
  drift), `docs/KEY_REGISTRY.md` generado.
- **C1** — `scripts/validators/` (paquete nuevo, contrato común
  `validate(env) -> dict`), ~30 validadores en vivo gratuitos registrados en
  `VALIDATORS`, vault como 6º sistema de la matriz, policy-skip explícito
  para Kie/Higgsfield/Modal.
- **C2** — propagación de llaves con consumidor real hacia los `.env` de cada
  repo que las usa, saneo de placeholders, permisos 0600.
- **C3** — dashboard `/dashboard/connections` (7ª vista, patrón K18): estado
  por proveedor, resumen por dominio, llaves sin consumidor, rotaciones
  pendientes.
- **C4** — lector de `gastos` (antes write-only), desglose de costo por
  proveedor en el dashboard de finanzas, cruce registry↔uso real para llaves
  ociosas.
- **C5** — ciclo diario con sección de validadores, alerta de regresión
  ✓→✗ contra el día anterior, filas nuevas en `metricas_diarias`.
- **C6** (esta fase) — investigación real de los 7 `✗` conocidos, reparación
  de un bug de validador, reclasificación de un proveedor a `policy-skip`,
  4 llaves marcadas `rotacion_pendiente`, verificación global del plan
  completo, cierre con reporte + Telegram.

## Investigación de los 7 `✗` conocidos

Para cada uno se confirmó en vivo (solo status HTTP + mensaje de error del
proveedor, nunca el valor de la llave) si el endpoint/header documentado en
el validador coincide con lo que el proveedor espera hoy, antes de decidir
categoría.

| Proveedor | Antes | Causa raíz confirmada | Categoría | Después |
|---|---|---|---|---|
| **Replicate** | ✗ (HTTP 403, "error code: 1010") | Bug real del validador: `http_get()` no enviaba `User-Agent`, y el default de `urllib` (`Python-urllib/3.x`) dispara el WAF de Cloudflare de Replicate (error 1010 "Access denied"), no la llave. Confirmado repitiendo el mismo request con un `User-Agent` de navegador → HTTP 200, cuenta obtenida, llave válida. | (a) reparable | ✓ |
| **Pexels** | ✗ (HTTP 403, "error code: 1010") | Mismo bug, mismo síntoma Cloudflare (error 1010) en el mismo `http_get()` compartido. Con el `User-Agent` corregido → HTTP 200, búsqueda de prueba ok, llave válida. | (a) reparable | ✓ |
| **xAI** | ✗ (HTTP 403) | El endpoint (`GET /v1/models`, Bearer) es correcto y en teoría gratis, pero el team de la llave del vault devuelve 403 `permission-denied` con mensaje literal "has either used all available credits or reached its monthly spending limit... please purchase more credits or raise your spending limit" — no es 401, no es llave inválida. xAI exige spending limit/créditos configurados en la cuenta para *cualquier* request, incluida esta de solo lectura. Resolverlo implica cargar facturación, fuera de alcance por política de cero gasto. | (c) policy-skip | policy-skip |
| **Mistral** | ✗ (HTTP 401, "Invalid API Key") | Endpoint/header correctos (coincide con la documentación oficial), la llave es genuinamente inválida o revocada — confirmado consistente en dos intentos. | (b) rotación pendiente | ✗ (marcado) |
| **GitHub** | ✗ (HTTP 401, "Bad credentials") | Endpoint/header correctos; probado también con esquema `token` en vez de `Bearer` y con `User-Agent` explícito por si acaso — mismo 401 en los tres casos. Token genuinamente revocado o expirado. | (b) rotación pendiente | ✗ (marcado) |
| **HeyGen** | ✗ (HTTP 401) | Endpoint/header correctos. El valor de `HEYGEN_API_KEY` en el vault no tiene forma de llave real de HeyGen — es un texto de marcador de posición, nunca se cargó la llave real (verificado programáticamente sin exponer el valor). No hay nada que rotar porque nunca hubo una llave real; hace falta que Cano genere una nueva desde `app.heygen.com`. | (b) rotación pendiente | ✗ (marcado) |
| **Cloudinary** | ✗ (HTTP 401) | El mensaje del proveedor es específico: `"cloud_name mismatch"`. Confirmado programáticamente (sin exponer valores) que `CLOUDINARY_CLOUD_NAME` en el vault es **idéntico carácter por carácter** a `CLOUDINARY_API_KEY` — no es un nombre de cuenta real, parece un error de carga (alguien copió el api_key en el campo del cloud_name). El endpoint/auth del validador son correctos. | (b) rotación pendiente (dato incorrecto en vault, no llave revocada) | ✗ (marcado) |

**Resultado neto:** 2 reparados de verdad (Replicate, Pexels — bug de
validador, no llaves), 1 reclasificado a `policy-skip` (xAI — gate de
facturación de la cuenta, no llave inválida), 4 marcados
`rotacion_pendiente` en `config/key_registry.yaml` con `rotacion_motivo`
explícito cada uno (Mistral, GitHub, HeyGen, y las 3 variables de Cloudinary
—`CLOUDINARY_API_KEY`/`_API_SECRET`/`_CLOUD_NAME`— que comparten una sola
causa raíz).

**Fix aplicado** (`scripts/validators/__init__.py`, función `http_get()`):
se añadió un `User-Agent` de navegador por defecto (overridable si algún
validador futuro necesita otro). Antes, todo el paquete usaba el
`User-Agent` por defecto de `urllib` (`Python-urllib/3.x`), que Cloudflare
identifica como tráfico de bot y bloquea con su error genérico 1010 en
proveedores que ponen su API detrás de Cloudflare (confirmado en Replicate y
Pexels; podría afectar a validadores futuros del mismo estilo). Esto es un
patrón a recordar: **un 403/1010 de Cloudflare no siempre es la llave** —
antes de marcar rotación pendiente, probar el mismo request con un
`User-Agent` real.

## Iteraciones corridas (2 de 3, convergió antes del tope)

1. **Iteración 1** — matriz base: 7 `✗` (Mistral, xAI, Replicate, HeyGen,
   GitHub, Pexels, Cloudinary). Clasificados Replicate y Pexels como (a)
   reparable → fix de `User-Agent` en `http_get()` → matriz re-corrida:
   `✓ 20 / ✗ 5 / — 8 / policy-skip 3`.
2. **Iteración 2** — de los 5 `✗` restantes, xAI se reclasificó a (c)
   `policy-skip` (gate de facturación de cuenta, no llave). Matriz
   re-corrida: `✓ 20 / ✗ 4 / — 8 / policy-skip 4`.
3. **Iteración 3 (confirmación)** — matriz corrida de nuevo sin ningún
   cambio de código ni de registry: mismo resultado exacto, `✓ 20 / ✗ 4 /
   — 8 / policy-skip 4`. Los 4 `✗` restantes (Mistral, GitHub, HeyGen,
   Cloudinary) son genuinamente (b) — credenciales inválidas o dato de
   vault incorrecto, no hay nada más reparable en el validador ni en la
   clasificación de política. Se paró aquí: no quedaban `✗` nuevos
   reparables, no hizo falta llegar a la 3ª iteración con cambios (el
   "tope de 3" nunca se alcanzó como límite real, la convergencia llegó
   antes).

## Estado final de la matriz de validadores en vivo

```
✓ 20   ✗ 4   — 8   policy-skip 4
```

- **✓ (20):** apify, cloudflare, cohere, deepl, exa, firecrawl, huggingface,
  kimi_moonshot, notion, nvidia_nim, openai, openrouter, perplexity, pexels,
  pixabay, rapidapi, replicate, stripe, telegram, uploadpost.
- **✗ (4, todos `rotacion_pendiente` en el registry):** mistral, github,
  heygen, cloudinary.
- **— (8, sin llave utilizable en el vault o respuesta inesperada no-2xx no
  clasificable como fallo):** anthropic, baserow, elevenlabs, gemini, groq,
  n8n, supabase, upstash.
- **policy-skip (4):** kie, higgsfield, modal (ya existían), + xai (nuevo
  esta fase).

Reporte del día regenerado en `reports/connection-matrix-2026-08-07.{md,json}`
— revisado a mano, cero valores de llave en ninguno de los dos.

## Verificación global de todo el plan (C0-C6)

- **Suite completa:** `python -m unittest discover -s tests` →
  **435 tests, OK (skipped=2)** — mismo piso documentado antes de esta fase,
  sin regresiones.
- **`python scripts/build_key_registry.py --check`** → `sin drift: el YAML
  coincide con el vault` (273 llaves, 283 líneas de vault).
- **`python ~/repos/factory-ia-channel-v5/scripts/factory_v5_preflight.py`**
  → mismo estado documentado el 2026-08-07 antes de esta fase: Apify
  `configured_metadata_only`, Kie `configured_execution_disabled`, ElevenLabs
  `configured_executor_required`, Remotion `available`, Supadata
  `not_configured` (pendiente por diseño — la llave genuinamente no existe
  en ningún vault ni `.env`, no es un bug de esta fase). **4/5 gates en
  verde**, sin cambios respecto al último estado documentado
  (`reports/pendientes-cano-2026-08-07.md`).

## Pendientes para Cano

Los mismos 4 quedaron encolados también en
`reports/pendientes-cano-2026-08-07.md` (tabla vigente):

1. **Rotar `MISTRAL_API_KEY`** — 401 "Invalid API Key" consistente, el
   validador está bien, la llave está revocada o caducada.
2. **Rotar `GITHUB_TOKEN`** — 401 "Bad credentials" consistente en tres
   variantes de auth probadas, token revocado o expirado.
3. **Generar una `HEYGEN_API_KEY` real** — la que hay en el vault es un
   texto de marcador de posición, nunca se cargó la llave real. Conseguirla
   en `app.heygen.com`.
4. **Corregir `CLOUDINARY_CLOUD_NAME` en el vault** — hoy es idéntico a
   `CLOUDINARY_API_KEY` (error de carga), el proveedor responde
   específicamente "cloud_name mismatch". El nombre real de la cuenta está
   en el dashboard de Cloudinary.
5. **Decisión de política, no acción técnica** — xAI quedó en
   `policy-skip`: para usar la API (incluso el listado de modelos gratuito)
   hace falta spending limit/créditos cargados en la cuenta. Si en algún
   momento se decide gastar ahí, hay que revertir la reclasificación en
   `scripts/validators/registry.py` (`validate_xai`) de vuelta a un
   validador HTTP normal.

## Lección para memoria futura

Un `403`/"error code: 1010" de un proveedor detrás de Cloudflare (Replicate,
Pexels, y probablemente otros que se añadan después) puede ser el WAF
bloqueando el `User-Agent` por defecto de `urllib`, no la llave. Desde esta
fase `scripts/validators/__init__.py::http_get()` manda un `User-Agent` de
navegador por defecto — pero si se añade un validador nuevo con su propio
cliente HTTP (no vía `http_get()`), vale la pena recordar este patrón antes
de asumir rotación pendiente.

## Notificación Telegram

Reutilizado el mecanismo real ya construido en K4
(`cano_hermes/notifications/telegram.py::send_telegram_message`, HTTP
directo a `https://api.telegram.org/bot<token>/sendMessage`, sin pasar por
`hermes-gateway`). Se confirmó en vivo con `getMe` que el token configurado
en el `.env` de este repo pertenece exactamente a
`@CANO_DIGITAL_OPENCLAW_BOT` antes de enviar. Mensaje enviado con el resumen
completo (fases, los 7 `✗` investigados, matriz final, verificación global,
los 4 pendientes) al chat configurado en `TELEGRAM_CHAT_ID` —
**`send_telegram_message()` devolvió `True`** (2xx confirmado por Telegram).
