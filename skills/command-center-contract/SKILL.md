# command-center-contract

Invocar las oficinas Python de `~/repos/cano-ai-command-center/01-offices/` por
contrato. Este skill SOLO LEE ese repo — nunca lo edita, nunca hace refactor allá
(regla dura del `CLAUDE.md` raíz: "Nunca editar cano-ai-command-center — es un sistema
externo. Solo se invoca por contrato"). 250 agentes y 30 canales YT ya operan ahí; se
opera, no se reconstruye.

## Contrato de invocación

```bash
cd ~/repos/cano-ai-command-center/01-offices/<oficina>
PYTHONPATH=. python3 <script relativo> [args]
```

- `cwd` fijado a la oficina invocada (p.ej. `01-offices/content-studio`); cada oficina
  resuelve sus propios imports (`freemium.*`, etc.) contra `PYTHONPATH=.` en su propia
  raíz, no contra la raíz de StarHome.
- Credenciales: cada oficina toma su `.env` propio. F1 ya dejó armados los dos `.env`
  relevantes (raíz del repo y `01-offices/content-studio/.env`), en 0600, con alias de
  variables resueltos (`CLOUDFLARE_API_TOKEN`←`CLOUDFLARE_AUTH_TOKEN`, etc.) — ese es el
  `.env` que este skill hereda al invocar por subprocess, sin copiarlo ni exponerlo en
  el chat.
- Nunca se escribe código, config ni fixtures dentro de `cano-ai-command-center` desde
  este skill. Los artefactos que el propio script de la oficina genera como parte de su
  operación normal (p.ej. `logs/preflight_*.json`) son responsabilidad de ese repo, no
  de StarHome — este skill no los provoca a propósito ni depende de ellos.

## Oficinas conocidas (01-offices/)

`ads-studio`, `ai-research`, `autocredit`, `automation-n8n`, `content-studio`,
`factory-ia-channel-v5` (copia local, distinta del repo hermano en `~/repos`),
`gpt-factory`, `saas-dev`, `ugc-affiliate`.

## Gating de acciones sensibles

Igual que el resto de StarHome: comandos que publican, suben contenido o gastan
(`--upload`, `--upload-sdk`, pasos que llaman proveedores de pago) caen en
`SENSITIVE_ACTIONS` (`cano_hermes/governance/policy.py`) y requieren `ApprovalRequest`
resuelto por un humano distinto de quien lo solicitó. Comandos de solo lectura/plan
(`--help`, `--status`, `--preflight` legacy, `--dry-run`) corren directo.

## Procedure

1. Confirmar objetivo, oficina y comando exacto; verificar que no cae en
   `SENSITIVE_ACTIONS` sin aprobación.
2. Recuperar contexto mínimo desde Nexus.
3. Ejecutar por subprocess con `cwd` en la oficina, `.env` propio de esa oficina,
   nunca escribiendo fuera de los artefactos normales de esa oficina.
4. Validar salida contra el contrato esperado (exit code, formato).
5. Registrar evidencia, costos (si los hubo) y aprendizajes candidatos en Nexus —
   incluyendo errores esperables de portabilidad (ver abajo) sin intentar arreglarlos allá.

## Smoke test (2026-08-06)

Comando: `freemium/run.py --semana 7 --preflight` (validación legacy, solo lectura —
`--preflight-v2` NO se usó porque escribe reportes JSON en `logs/` del repo externo y
el mandato de este smoke es "sin escribir nada en ese repo").

```
cd ~/repos/cano-ai-command-center/01-offices/content-studio
PYTHONPATH=. python3 freemium/run.py --semana 7 --preflight
```

Resultado: **éxito** (exit 0). Reportó `Preflight S7: 0 OK | 27 MISSING` — esperado,
son checks de archivos de render final (`reel_final.mp4`, `slide_00_portada.png`, etc.)
que no existen en este entorno porque no se ha corrido el pipeline de producción; el
comando en sí funcionó y no requirió red ni credenciales pagas. `git status --short`
en `cano-ai-command-center` quedó limpio después de la corrida — confirmado sin
escritura.

Nota separada: invocar `freemium/engine/preflight.py` (el módulo de 13 gates,
`--preflight-v2`) directo con `python3 -m` falla con
`ModuleNotFoundError: No module named 'freemium'` si no se corre desde la raíz de la
oficina con `PYTHONPATH=.` — es la causa típica de los "errores de rutas Windows
esperables" que reporta el plan: el repo fue escrito asumiendo invocación desde
Windows (`/c/windows/py freemium/run.py ...`, ver docstring del propio `run.py`) y
rutas/entornos de ese lado no siempre traducen 1:1 a Linux. Esto es un hallazgo a
reportar, **no** un refactor a aplicar en `cano-ai-command-center` (regla dura: no
tocar ese repo).
