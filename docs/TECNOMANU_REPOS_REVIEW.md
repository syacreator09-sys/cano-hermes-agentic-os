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
