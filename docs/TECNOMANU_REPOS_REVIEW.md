# Revisión de repos GitHub — `tecnomanu`

**Fase:** F7 del plan Prometeo · **Generado:** 2026-08-05 · **Método:**
`gh search repos --owner tecnomanu --limit 50` (40 repos públicos, no-fork,
cuenta completa confirmada con `gh search repos --owner tecnomanu --json
name | ... | len()`) + `gh api repos/tecnomanu/<repo>` (licencia, tamaño,
archivado) + `gh api repos/tecnomanu/<repo>/contents/` (confirmar presencia
real de `LICENSE`) + lectura de README vía `gh api .../readme`.

## Filtro (aplicado estrictamente)

Para clonar a `~/repos/`, un repo debe cumplir **las cuatro** condiciones:

1. Relacionado con **video, grabación, o generación de documentación**.
2. Open-source con licencia real presente en el repo (no `null`/ausente).
3. Corre en **CPU** — esta máquina no tiene GPU dedicada utilizable (GT 720
   Kepler, sin CUDA).
4. Sin llaves de pago **obligatorias** para funcionar (proveedores gratuitos/
   locales deben ser suficientes para el camino principal).

## De los 40 repos, 5 caen en la categoría video/grabación/documentación

| Repo | Qué hace | Licencia | ¿CPU? | ¿Llave de pago obligatoria? | Decisión |
|---|---|---|---|---|---|
| [`video-docs-builder`](https://github.com/tecnomanu/video-docs-builder) | Graba tutoriales de apps web: Playwright (grabación de navegador) + narración TTS (Piper/ElevenLabs/OpenAI) + FFmpeg (ensamblaje), opcionalmente genera sitio de docs en React. | **MIT** (archivo `LICENSE` confirmado en raíz) | Sí — Playwright/Chromium + FFmpeg + Piper, todo local | No — Piper es gratis y local; ElevenLabs/OpenAI son opcionales | ✅ **APROBADO** — clonado en `~/repos/video-docs-builder`. Ya evaluado también en command-center (`01-offices/factory-ia-channel-v5/docs/integrations/video-docs-builder.md`, ver `docs/SKILLS_MATRIX.md` de este repo para la entrada de matriz) — esa evaluación de command-center marcó un falso-positivo Critical/High Risk de Snyk por 2 CVEs de dependencias de desarrollo transitivas (`ws`, `esbuild`), revisado manualmente sin hallar comportamiento malicioso. |
| [`agent-rules-kit`](https://github.com/tecnomanu/agent-rules-kit) | CLI que genera reglas/documentación (`.mdc`/`.md`) para que agentes de IA (Cursor, VS Code, Claude, Windsurf, etc.) entiendan la estructura y prácticas de un stack. Encaja en "generación de documentación". | **ISC** (archivo `LICENSE` confirmado en raíz) | Sí — CLI Node puro | No — escribe archivos locales; integraciones MCP opcionales (ej. `pampa`) no son requeridas para el uso base | ✅ **APROBADO** — clonado en `~/repos/agent-rules-kit`. Útil para F15/forja: generar reglas/documentación consistente para los distintos engines (Claude/Codex) sin escribirlas a mano cada vez. |
| [`framevox`](https://github.com/tecnomanu/framevox) | CLI de producción de video: wrapper sobre HyperFrames (HTML→MP4) + TTS (Gemini/Piper/ElevenLabs). | **Ninguna** — se confirmó por listado directo de archivos (`gh api repos/tecnomanu/framevox/contents/`) que el repo **no tiene archivo `LICENSE`** en la raíz (`.apc`, `.github`, `AGENTS.md`, `README.md`, `bin`, `docs`, `package.json`, `public`, `scripts`, `skill`, `src`, `templates` — sin `LICENSE`). | Sí — Node, TTS con Piper local disponible | No obligatorio (Piper gratis), pero el ejemplo principal del README usa Gemini | ❌ **RECHAZADO** — licencia ausente/desconocida. Mismo criterio de gobernanza que command-center aplica a los repos santmun "UNKNOWN license" (ver `docs/SANTMUN_REFERENCE_MAP.md`): sin licencia confirmada, no se clona ni se instala. Si Cano quiere reconsiderar, pedirle al autor que agregue `LICENSE` o confirmar licencia por otro medio antes de clonar. |
| `agent-rules-kit-mcp` | Servidor MCP compañero de `agent-rules-kit` (gestión de reglas vía MCP). | **Ninguna** — confirmado por listado de archivos (`.cursor`, `.github`, `README.md`, `config.example.json`, `package-lock.json`, `package.json`, `src`, `tsconfig.json` — sin `LICENSE`). | Sí — Node | No | ❌ **RECHAZADO** — sin licencia. Además redundante: `agent-rules-kit` (ya aprobado y clonado) cubre el caso de uso principal sin necesitar el servidor MCP compañero. |
| `qwen3-tts-api` | Servidor/daemon local de TTS (Qwen3-TTS), API estilo OpenAI, panel web, CLI `qvox`, voces clonables. Backends MLX (Apple Silicon) y PyTorch (CUDA/ROCm/**CPU**). | MIT | Backend CPU explícito soportado (aunque MLX/CUDA son las rutas optimizadas) | No — self-hosted | ⚠️ **EVALUADO, NO CLONADO — fuera de categoría.** Es un servidor de síntesis de voz (TTS), no una herramienta de video/grabación/generación de documentación en el sentido del filtro de esta fase — es infraestructura de audio adyacente. Se deja documentado por si una fase futura de voz/narración (p. ej. para video-docs-builder o Tutorial Suite) quiere evaluarlo explícitamente; pasaría el resto del filtro (MIT, CPU disponible, sin llave de pago) si se re-clasificara. |

## Los otros 35 repos — descartados sin clonar (fuera de categoría)

Ninguno de los siguientes es una herramienta de video, grabación o
generación de documentación — son infraestructura genérica, proyectos
personales/portfolio, microservicios de ejemplo, o herramientas sin relación
(gateway, auth, Docker images, hardware/Arduino, trading bot, etc.). Se
listan por transparencia de la búsqueda, sin evaluación de licencia/GPU/
llaves porque no aplican al criterio de categoría:

`pampa` (protocolo de memoria de artefactos, MCP), `nerdearla-agenda-mcp`,
`docker-php8-laravel-nginx-supervisor`, `panel-base-frontend-api`,
`tecnomanu` (perfil README), `control-cursor-with-hand`,
`remove-background-local` (herramienta de imagen, no video/docs),
`dokploy-dograh`, `atlas-world-cup-2026`,
`docker-php74-laravel-nginx-supervisor`, `puppeteer-server`,
`multitenant-nestjs-api-base`, `porfolio-frontend`, `bootstrap-project-mcp`,
`microservice-gateway`, `open-in-whatsapp`,
`yaydoo_examen_algoritmos_manuel_bruna`, `network-mcp`, `dejatips`,
`plant77`, `mundocrm-vendor-leads-sender`, `my-own-custom-hooks`,
`portfolio-api`, `tradingbot`, `microservice-redis`,
`microservice-authentication`, `docs` (notas personales, no herramienta),
`mcp-telegram-agent`, `tecnomanu.github.io`, `android-rtmp-client`,
`cloudflare-mcp`, `microservice-users`, `unilogin-laravel-lumen`,
`docker-php74-mongodb-nginx-supervisor`, `api-rest-mutation`.

## Resumen

- **40** repos públicos evaluados (conteo completo, no-fork).
- **5** relacionados con video/grabación/generación de documentación.
- **2 clonados y aprobados**: `video-docs-builder`, `agent-rules-kit` — ambos
  en `~/repos/`, con `LICENSE` confirmado (MIT / ISC), CPU-only, sin llave de
  pago obligatoria.
- **2 rechazados** por licencia ausente/desconocida (mismo criterio de
  gobernanza que command-center aplica a santmun): `framevox`,
  `agent-rules-kit-mcp`.
- **1 evaluado y no clonado** por estar fuera de la categoría del filtro
  (TTS/audio, no video/grabación/docs): `qwen3-tts-api`.
- **35** fuera de categoría, no evaluados a fondo.

## F7b: dry-run real (2026-08-06)

**Contexto.** F7 ya había corrido `rehearse.ts` (valida selectores/navegación
con un navegador real, pero **sin grabar video ni generar audio**) contra una
app fixture de una sola página — resultado documentado en
`docs/SKILLS_MATRIX.md` (2/2 pasos OK). Esta fase va más allá: corre el
**pipeline completo real** (TTS → grabación de navegador → ensamblaje FFmpeg)
y produce un `.mp4` de verdad, para confirmar que la herramienta funciona de
punta a punta y no solo que sus selectores son válidos.

**Instalación (dentro del propio repo `~/repos/video-docs-builder`, nada
fuera de él):**

- `npm install` — ya estaba resuelto desde F7 (20 paquetes; Playwright
  `^1.50.1` declarado, `1.59.1` instalado).
- `npx playwright install chromium` — el binario ya estaba cacheado en
  `~/.cache/ms-playwright/`; no se descargó nada nuevo.
- Piper TTS: `python3 -m venv tools/piper-tts/.venv && pip install piper-tts`
  (v1.6.0 de PyPI, dentro de un venv aislado **dentro del propio repo** — el
  Python del sistema en esta máquina es "externally managed" y rechaza `pip
  install` fuera de un venv). No hizo falta el `espeak-ng` del sistema: la
  versión instalada de `piper-tts` (proyecto sucesor `OHF-voice/piper1-gpl`)
  trae el phonemizer embebido, sin depender del binario CLI de espeak-ng.
- Voz descargada: `es_AR-daniela-high.onnx` (109MB, HuggingFace
  `rhasspy/piper-voices`) — la misma que documentan `TTS-PROVIDERS.md` y
  `tools/piper-tts/README.md`.
- Nota de compatibilidad: `piper-tts` 1.6.0 expone flags con guion
  (`--length-scale`, `--noise-scale`, `--noise-w-scale`) pero también acepta
  los alias con guion bajo (`--length_scale`, `--noise_scale`,
  `--noise_w`) que usan `scripts/generate-audio.ts` y
  `tools/piper-tts/src/generate.ts` — no hizo falta parchear nada.
- `.env` en la raíz del repo con `TTS_PROVIDER=piper` (gitignorado, igual que
  `tools/piper-tts/.venv/` y `tools/piper-tts/voices/*.onnx`) — cero llaves
  de pago tocadas.

**Fixture usada:** la misma app trivial de una sola página de F7
(`index.html`: título + botón que cambia un párrafo), servida con
`python3 -m http.server` en `127.0.0.1`, con su flow de 2 pasos (cada uno
con narración real en español). No se tocó ninguna app pública ni de
terceros.

**Pipeline real corrido, paso a paso:**

1. `rehearse.ts` → 2/2 pasos OK (repite la validación de F7, confirma que
   nada cambió).
2. `generate-audio.ts` con `TTS_PROVIDER=piper` → **2 clips MP3 generados de
   verdad** (1.9s + 1.2s) vía Piper local — $0, sin llave de API.
3. `generate-video.ts` → grabación real de navegador con Playwright/Chromium
   headless → `.webm` de 4.84s.
4. `assemble.ts` → FFmpeg mezcla los 2 audios sobre el video y transcodea a
   H.264/AAC.

**Resultado verificado con `ffprobe`:** `01-click-demo.mp4`, 52KB, **4.45s,
un stream de video h264 + un stream de audio aac** — un tutorial real
narrado en español, no un mock ni un placeholder. Costo total: **$0** (Piper
+ Playwright + FFmpeg, 100% local, sin llamadas a API de pago).

**¿Reemplaza o complementa la integración ya existente en Factory V5?**
**Complementa, no reemplaza.**
`01-offices/factory-ia-channel-v5/docs/integrations/video-docs-builder.md`
(command-center, solo lectura) ya documenta un clon **aislado y separado**
del mismo repo tecnomanu (`tools/external/video-docs-builder/`, con su
propio `.git`, instalado también como skill local
`.agents/skills/video-docs-builder`) para un caso de uso específico:
documentar las apps internas que construye Factory V5 (dashboards, paneles
de cliente). El clon evaluado aquí (`~/repos/video-docs-builder`, F7 de
Prometeo) es una instancia independiente del mismo repo open-source, para el
ecosistema Hermes/StarHome (p. ej., documentar en el futuro el propio
dashboard de StarHome OS en `:8787` o `hermes dashboard`). Las dos
instancias:

- Son clones separados con su propio `.git` — no hay dependencia cruzada, no
  hay riesgo de que uno rompa al otro, y ninguno de los dos se registró como
  dependencia del otro.
- Usan la misma estrategia de costo cero (`TTS_PROVIDER=piper`) que la doc de
  factory-v5 recomienda explícitamente.
- No se solapan en propósito: factory-v5 la usa para su pipeline editorial
  adyacente (apps que Factory V5 construye); esta instancia documenta apps
  propias del ecosistema Hermes/StarHome — nunca el pipeline de contenido de
  Factory V5.

Lo que esta fase añade y que la doc de factory-v5 todavía no tenía verificado
explícitamente: una corrida real de punta a punta más allá de `rehearse.ts`
(que por diseño NO graba video ni genera audio) — confirma que el pipeline
completo (TTS + grabación + ensamblaje) funciona de verdad en esta máquina,
con Piper instalado desde cero vía venv, sin tocar nada del sistema ni de
command-center.
