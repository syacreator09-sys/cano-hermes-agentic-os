# reel-dedup-check

Regla de dedup para cualquier oficina que produzca reels/videos afiliados o de canal
propio: **leer el ledger de publicados ANTES de producir**, y no aceptar como "ya
publicado" ninguna fila sin un ID de video real y verificable. Este skill es la
capacidad/regla, no el dato — no copia ni modifica ningún ledger de otros repos.

## Qué se buscó y qué se encontró (2026-08-06, evidencia de F9)

No existía este skill en `cano-hermes-agentic-os/skills/` ni un skill equivalente en
`ugc-commerce-studio` antes de esta corrida. Tampoco existe, en ningún repo auditado, un
archivo literal `published_ledger.csv`:

- `cano-ai-command-center/01-offices/ugc-affiliate/06-tracking/` solo contiene
  `TRACKING_SHEET_SCHEMA.md` (schema de referencia para Sheets/Supabase, 27 columnas
  documentadas incluida `url_video_tiktok`) — es un documento, no un CSV poblado.
- `scripts/sync_tracking.py` (esa misma oficina, solo lectura desde StarHome) consolida
  `output/**/tracking_entry.json` → `tracking_log.csv`, pero ese archivo se genera bajo
  demanda dentro de `output/` (que está en `.gitignore` de esa oficina) y no está
  commiteado ni es el "ledger de publicados": es un log de producción/performance, y su
  schema actual (`ugc-orchestrator.py::save_tracking_entry`) **no incluye ningún campo
  de video ID de plataforma** — la columna 12 (`url_video_tiktok`) del schema documentado
  nunca se popula en el JSON real.
- El mecanismo de dedup que sí opera hoy en producción vive en otro lugar y con otra
  forma: `scripts/uploaders/uploader.py` mantiene una base SQLite propia,
  `01-offices/ugc-affiliate/upload_log_ugc.db` (no versionada, se crea en runtime),
  tabla `uploads` con clave `(canal, slug, fecha)` y columnas `status`, `req_id`
  (identificador que devuelve el SDK de upload-post), `platforms`, `started_at`,
  `finished_at`. Bloquea duplicados por combinación canal+slug+fecha, no revisando video
  IDs de TikTok/IG directamente — `req_id` es lo más cercano a un identificador real de
  publicación que el sistema guarda hoy, y queda vacío en filas de error o `dry_run`.
- `ugc-commerce-studio` (repo propio) no tiene ningún ledger de publicación — es
  `draft_only` por diseño (`publication_mode=draft_only` en su README), no publica.

**Conclusión**: el "published_ledger.csv" referenciado por el mandato de F9 es
aspiracional — todavía no existe con ese nombre ni ese formato en ningún repo. Este
skill documenta la regla que debe cumplir cuando exista (o el mecanismo real —
`upload_log_ugc.db` — mientras no exista), no inventa el archivo.

## Regla

1. Antes de producir cualquier reel (gasta créditos Higgsfield/HeyGen/etc.), leer el
   ledger de publicados vigente:
   - Si `published_ledger.csv` existe en la oficina relevante (p. ej.
     `cano-ai-command-center/01-offices/<oficina>/06-tracking/published_ledger.csv` o
     equivalente en `ugc-commerce-studio`), usarlo.
   - Si no existe, usar el mecanismo real de esa oficina — para `ugc-affiliate` hoy eso
     es `upload_log_ugc.db` (SQLite, `SELECT status, req_id FROM uploads WHERE
     canal=? AND slug=? AND fecha=?`), consultado por contrato (solo lectura, subprocess
     o import directo — nunca copiando la DB a StarHome).
2. Una fila cuenta como "ya publicado" **solo si** tiene un identificador de video real
   y no vacío (`req_id`, `video_id`, o `url_video_tiktok` según el ledger disponible) Y
   `status` indica éxito. Filas con `status=error`, `status=dry_run`, o con el campo de
   ID vacío/placeholder (`"1"`, `"test"`, URLs con dominios inventados como `https://x/...`
   — ver hallazgo de fixtures de test en el reporte F9) **no cuentan como publicadas** y
   no deben usarse para bloquear ni para desbloquear una producción.
2.1. Si el ledger disponible no tiene ningún campo de ID de video real (como pasa hoy
   con `tracking_entry.json` de `ugc-affiliate`), ese ledger **no es suficiente** para
   aplicar esta regla con confianza — repórtalo como bloqueo en vez de asumir que "no
   hay filas" significa "no hay duplicados".
3. Si el producto+canal (o producto+canal+fecha, según el ledger) ya aparece con un ID
   real y éxito, no producir de nuevo sin aprobación explícita del operador (puede ser
   intencional: variación, re-take).
4. Registrar el chequeo (encontrado/no encontrado, ledger consultado, decisión) como
   evidencia antes de continuar al paso de generación paga.

## Procedure

1. Confirmar oficina/canal/producto objetivo y localizar el ledger real vigente para esa
   oficina (no asumir `published_ledger.csv` sin verificar que existe).
2. Leer el ledger por contrato — solo lectura, nunca escribir ni copiar el archivo o la
   DB fuera de su repo de origen.
3. Aplicar la regla de la sección anterior: descartar filas sin ID de video real antes
   de decidir si hay duplicado.
4. Si hay duplicado real → detener y pedir aprobación explícita antes de producir de
   nuevo. Si no hay duplicado, o el ledger es insuficiente (§2.1) → continuar dejando
   constancia explícita de cuál fue el caso.
5. Registrar evidencia (ledger consultado, resultado, aprendizajes candidatos) en Nexus.
