# MCP portables — estado en esta máquina (F7)

**Fase:** F7 del plan Prometeo · **Generado:** 2026-08-06

## Los 4 MCP portables (SYSTEMS_MATRIX_HERMES.md §7 de command-center)

Portables = solo necesitan una API key por variable de entorno, no OAuth
específico de esta máquina (a diferencia de Higgsfield/HeyGen/YouTube/etc.,
que requieren cuenta propia provisionada aquí):

| MCP | Variable(s) esperada(s) | ¿Presente en vault (`~/.secrets/credenciales/credenciales/.env`)? |
|---|---|---|
| `n8n-mcp` | `N8N_API_KEY`, `N8N_HOST`, `N8N_MCP_TOKEN`, `N8N_WEBHOOK_URL` | ✓ las 4 |
| `notion-mcp` | `NOTION_TOKEN` (+ `NOTION_WORKSPACE`, `NOTION_PAGE_ID`, `NOTION_*_DB_ID`) | ✓ |
| `rapidapi-tiktok` | `RAPIDAPI_KEY` | ✗ no existe en el vault bajo ningún nombre (confirmado ya en F1 y F2) |
| `factory-ia-channel MCP` | credencial propia del MCP de factory-v5 (ver `.mcp.json` de ese repo, no auditado aquí — factory-v5 no es de contrato read-only, pero su MCP config no se tocó en esta fase) | pendiente de confirmar |

Nombres de variables únicamente, ningún valor fue leído ni impreso.

## Mecanismo real en esta máquina

`hermes-agent` (`hermes_cli/mcp_config.py`, `hermes_cli/mcp_startup.py`,
`hermes_cli/mcp_security.py`) es el componente de esta máquina que sabe
cargar servidores MCP: espera una clave `mcp_servers` en
`~/.hermes/config.yaml`, con las credenciales de cada servidor
interpoladas desde variables de entorno (potencialmente vía un
`~/.hermes/.env` opcional).

Estado real verificado en esta máquina:
- `~/.hermes/config.yaml` **no tiene ninguna clave `mcp_servers`** —
  ningún MCP está registrado todavía (ni los 4 portables ni ningún otro).
- `~/.hermes/.env` **no existe**.
- StarHome OS (`cano-hermes-agentic-os`) no tiene mecanismo propio de
  registro de MCP servers — los MCP son responsabilidad de hermes-agent
  como ejecutor, no de StarHome como orquestador.

## Qué falta antes de activarlos

1. Decidir en `~/.hermes/config.yaml` la sección `mcp_servers` con las
   entradas de `n8n-mcp` y `notion-mcp` (los dos que sí tienen llave
   completa en el vault) — esto es configuración, no requiere escribir
   secretos en el chat ni en este repo.
2. `rapidapi-tiktok` queda bloqueado hasta que Cano provisione
   `RAPIDAPI_KEY` (no existe en ningún vault ni servicio ya conectado,
   confirmado en tres fases distintas: F1, F2, F7).
3. `factory-ia-channel MCP` requiere revisar `.mcp.json` de
   `~/repos/factory-ia-channel-v5` (no se auditó su config de MCP en
   esta fase; queda para F8, que sí trabaja ese repo).

No se creó ni modificó `~/.hermes/config.yaml` en esta fase — activar un
MCP server implica que hermes-agent empiece a invocarlo en producción, y
eso es una decisión operativa, no de inventario. Queda documentado aquí
para que F15 (bucle de convergencia) o Cano decidan activarlo.

## Actualización 2026-08-06 — n8n-mcp y notion-mcp ACTIVADOS

Cano pidió explícitamente conectar todo lo que ya tuviera credenciales
listas. Se activaron los dos MCP que sí tenían llave completa:

1. `~/.hermes/.env` creado (600, no trackeado en ningún repo) con
   `N8N_API_URL` (copiado de `N8N_HOST` del vault, ya era una URL completa),
   `N8N_API_KEY` y `NOTION_TOKEN` — copiados por script sin imprimir
   valores en ningún momento.
2. `hermes mcp add n8n-mcp --command npx --args -y n8n-mcp --env
   'N8N_API_URL=${N8N_API_URL}' 'N8N_API_KEY=${N8N_API_KEY}'` — los
   placeholders `${VAR}` quedan literales en `~/.hermes/config.yaml`, el
   valor real solo vive en `~/.hermes/.env` y se interpola en tiempo de
   conexión (mecanismo ya existente de `mcp_config.py`, no inventado).
   **Conectado en vivo: 7 herramientas reales descubiertas contra la
   instancia n8n real** (`tools_documentation`, `search_nodes`,
   `get_node`, `validate_node`, `get_template`, `search_templates`,
   `validate_workflow`).
3. Mismo patrón para `notion-mcp` (`npx -y @notionhq/notion-mcp-server`,
   `NOTION_TOKEN`). **Conectado en vivo: 24 herramientas reales** contra
   el workspace real de Notion.
4. `hermes mcp list` confirma ambos `✓ enabled`.
5. `rapidapi-tiktok` sigue bloqueado — `RAPIDAPI_KEY` no existe en ningún
   vault, confirmado por cuarta vez (F1, F2, F7, hoy).
6. `factory-ia-channel MCP` sigue sin auditar — no es parte de
   hermes-agent, vive en el `.mcp.json` de `~/repos/factory-ia-channel-v5`
   (pendiente, no es urgente, ese repo ya tiene sus proveedores Apify/
   Supadata/UploadPost como código Python directo, no como MCP).

Nadie usó estas herramientas todavía para ninguna tarea real (ni workflows
n8n ni escritura en Notion) — solo se conectaron y verificaron. Cualquier
uso real (crear workflow, escribir página) sigue sujeto a las mismas
reglas de aprobación que el resto del plan si toca producción.
