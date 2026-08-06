# Mapa de referencia — santmun (solo lectura)

**Fase:** F7 del plan Prometeo · **Generado:** 2026-08-05 · **Tipo:** resumen de
lectura, sin cambios de código, sin ejecución de nada de santmun.

Este documento resume lo que hay en `~/repos/cano-ai-command-center` (checkout
local, rama `feat/factory-v5-upload-campaign-10-day`, **repo externo,
SOLO LECTURA — nunca se edita**) sobre los 21 repos de `github.com/santmun`
auditados el 2026-07-27. No se clonó, instaló ni ejecutó nada de santmun para
producir este documento. Fuentes leídas:

1. `docs/architecture/capability-governance/SANTMUN_QUARANTINE_AUDIT_20260727.md`
2. `01-offices/factory-ia-channel-v5/docs/reuse-map-santmun.md`
3. `01-offices/factory-ia-channel-v5/docs/SANTMUN_INTEGRATION_AUDIT.md`
4. `00-core/obsidian-vault/decisiones/santmun-governance-consolidation-2026-07-27.md`
5. `01-offices/factory-ia-channel-v5/.vendor/santmun-quarantine/MANIFEST.json`

## Regla dura heredada de estas fuentes

`.vendor/santmun-quarantine/` en command-center nunca se ejecuta, instala o
importa como dependencia de runtime — ni desde command-center ni, por
extensión, desde esta máquina/repo. **Explícitamente prohibido invocar
`broll-generator` o cualquier `meta-ads-*`** (marcados abajo con 🚫); son
menciones de solo lectura, nunca ejecución.

## Tabla: repo santmun → conceptos → ya-extraído-en-extensions/ → falta

| Repo santmun | Conceptos | Ya extraído en `extensions/` (Factory V5, command-center) | Falta / estado |
|---|---|---|---|
| `videos-virales-skill` | Investigación viral, scoring, calidad de transcripción | ✅ `extensions/viral_research_engine/` → skill `viral-research` (provider-free, dry-run). Licencia MIT. | Nada — clon mantenido solo para comparación, no es dependencia nueva. |
| `forja` (patrones, no la app) | Normalización de eventos entrantes, ruteo omnicanal, escalamiento | ✅ patrón extraído como skill `omnichannel-inbound-routing` (dry-run aprobado) | La **app** forja (MIT) sigue en cuarentena; falta adapter completo antes de activarla. |
| `video-explainer` | Explicador editorial por beats, timing de audio | ✅ `extensions/editorial_explainer_engine/` (preset Pro) | Nada — REFERENCE_ONLY/KEEP_EXISTING; adaptación de comportamiento, no de código; licencia nunca confirmada en la raíz del repo. |
| `video-vox` | Mismo motor, preset `video_vox_short`; patrón visual (fondo papel, tipografía Anton, transiciones de slide) | ✅ preset `video_vox_short` + `renderers/remotion/src/compositions/EditorialExplainer.tsx` (código 100% original de Factory V5, inspirado solo visualmente — addendum 2026-07-29 que revierte la exclusión original únicamente para este uso) | Licencia sigue **UNKNOWN** — el clon nunca se ejecuta, importa ni se usa como dependencia; solo referencia de estilo y para confirmar el nombre del modelo `google/nano-banana` usado en sus ilustraciones. |
| `broll-generator` 🚫 | Mapeo beat → generación de imagen | ✅ concepto extraído en `extensions/broll_engine/` (beat → Native ImageGen handoff) | **Prohibido ejecutar** (cuarentena explícita). Llama Kie AI (`KIE_AI_API_KEY`) — nunca será dependencia real; Factory V5 usa Native ImageGen, no Kie. |
| `thumbnail-simple-skill` | Brevedad/contraste de texto en miniatura, identidad de canal | ⚠️ `reuse-map-santmun.md` dice extraído como `thumbnail_engine` (code-native) | **Contradicción sin resolver entre las fuentes**: la auditoría de gobernanza 2026-07-27 lo lista bajo "Bloqueadas por licencia desconocida", pero el reuse-map lo da por extraído. No se pudo determinar aquí si `thumbnail_engine` es reimplementación 100% original (patrón video-vox) o si la extracción es anterior al bloqueo formal de licencia. Pendiente de aclarar por quien mantiene Factory V5 — no es algo que este documento pueda resolver sin acceso de escritura a command-center. |
| `editor-tiktok` | Remoción de silencios, edición estilo TikTok | ❌ no extraído directamente | Reimplementado **independientemente** en `factory/creative/silence_trim.py` (solo ffmpeg). Dependencia AssemblyAI y `scripts/doctor.sh` explícitamente no permitidos. Licencia UNKNOWN. |
| `color-grade-skill` | Color grading | ❌ ninguna extracción | Bloqueado, licencia UNKNOWN, revisión de licencia pendiente sin fecha. |
| `sofia-voice-agent` | Contratos de estado de voz / handoff humano | ❌ ninguna extracción todavía | Licencia UNKNOWN — bloqueado. Plan documentado es "adaptar tras revisión de licencia"; no se ha hecho. |
| `ugc-ad-meta` | Ads UGC | ❌ no se usa directamente | `ugc-commerce-studio` (repo propio de Cano, `~/repos/ugc-commerce-studio`, Higgsfield-only) ya documenta su propia comparación contra este commit exacto en `docs/source-audit.md`. Ese repo propio es el runtime real, nunca este clon. |
| `meta-ads-skills` 🚫 / `meta-ads-launch` 🚫 | Automatización Meta Ads (CLI `meta`, creative generation vía Kie) | ❌ ninguna | `DEFERRED` — fase Meta Ads separada, requiere aprobación explícita. **Prohibido invocar.** |
| `crear-agente` | Creación de agentes | ❌ ninguna, redundante | MIT pero solapa con `architecture-blueprint` canónico de command-center — no se planea extraer. |
| `intro-edit-pipeline-skill`, `docs-entrega-skill`, `skill-propuestas`, `mantenimiento-skill`, `blog-pdf-skill` | Sin detalle de concepto en las fuentes leídas (solo aparecen listados por nombre en la lista de gobernanza) | ❌ ninguna | Bloqueados por licencia UNKNOWN (auditoría 2026-07-27), sin fecha de revisión. |
| `historias-ig-skill`, `instagram-stories-skill`, `preguntale-a-tus-datos`, `carruselesdef` | Sin detalle de concepto en las fuentes leídas | ❌ ninguna | Reference-only — "Cano ya tiene mejor equivalente"; no se planea extraer. |
| 38 repos restantes del perfil santmun (de 59 totales, solo 21 auditados) | No auditados | ❌ | Nunca clonados. La nota de decisiones (2026-07-27) marca como "relevantes a trabajo activo, esperando permiso explícito para clonar": `instagram-carousel-generator`, `carousel-horizontes-ia`, `carruanimados`, `tweet-carousel` (carruseles), `meta-ads-launch`, `agente-prospeccion` (Ads/CRM), `instagram-stories-generator`, `thumbnail-horizontes-ia` (content-studio), `claude-skills-hub` (referencia de catálogo). Ninguno de estos se clonó ni se tocó aquí. |

## Notas de gobernanza relevantes para Hermes

- El junction `.claude/skills` → `.agents/skills` que asume el diseño de Codex
  **no está aplicado** en command-center — sigue siendo carpeta real. No
  asumir lo contrario si algún plan futuro de Hermes referencia esa ruta.
- Cualquier repo nuevo de santmun requiere permiso explícito antes de clonar
  (según la nota del propio command-center) — esta regla se hereda aquí
  también: este documento no clonó ni clonará santmun sin permiso explícito
  de Cano, incluso si un repo de la lista "pendiente" pareciera útil para
  Hermes.
- Regla canónica de adopción en command-center:
  `.command-center/canon/EXTERNAL_CAPABILITY_LIFECYCLE.md` (mencionada en la
  nota de decisiones, no releída en detalle aquí — referencia para quien
  audite command-center directamente).
