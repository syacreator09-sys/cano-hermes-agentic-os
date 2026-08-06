# F12 — OAuth canales + provisión de cuentas propias

**Fecha**: 2026-08-06
**Alcance**: 100% inventario/validación, endpoints gratuitos, cero gasto, cero OAuth interactivo, cero escritura en `~/repos/cano-ai-command-center`.

**Método (§1)**: el validador nativo ya existe en command-center, commit `e9a2662`
("native YouTube uploader + live token validation for all 8 channels"),
`01-offices/factory-ia-channel-v5/{providers/youtube_native/{tokens,client}.py, scripts/validate_youtube_tokens.py}`.
No se copió ni modificó esa lógica: se ejecutó como subproceso externo (venv
efímero de esta sesión, `google-auth` + `google-api-python-client`) que
importa `providers.youtube_native.tokens` y `scripts.validate_youtube_tokens`
tal cual desde el checkout de command-center (rama
`feat/factory-v5-upload-campaign-10-day`) y sólo sobreescribe en memoria la
constante `TOKEN_DIR` (que por diseño apunta a `.runtime/credentials/...`,
vacío en este checkout porque las credenciales nunca van a git) para que
apunte al respaldo real,
`~/.secrets/credenciales/credenciales/youtube-tokens/`. Ningún archivo se
escribió dentro de `cano-ai-command-center`. La llamada real ejecutada por el
código del propio repo fue `channels.list(part="snippet,statistics",
mine=True)` — de cuota mínima, sin efectos secundarios.

---

## 1. YouTube por canal (8 canales)

| Canal (slug) | Carpeta de token | Estado | Detalle |
|---|---|---|---|
| cano-digital-ia | `cano-digital-ia` | ✓ válido | LIVE — "Cano Digital", 52 subs, 124 videos. No necesita acción. |
| cass-healt | `cass-healt` | ✓ válido | LIVE — "cass healt&beauty", 33 subs, 106 videos. No necesita acción. |
| sya-animals | `sya-animals` | ✗ falta client_secret | `client_secret.json` presente pero **0 bytes** (corrupto/vacío) y no hay `youtube_token.json`. Requiere que Cano vuelva a descargar el client secret desde Google Cloud Console (paso de navegador, no hay comando posible sin ese archivo). |
| sya-motive | `sya-motive` | ✗ falta client_secret | No existe carpeta ni `client_secret` en el respaldo (`youtube-tokens/` ni `downloads/`). Requiere provisión desde cero en Google Cloud Console. |
| unsolved-lens | `_sh_can` | ✗ refresh necesario | `client_secret` sí existe en `downloads/` pero no hay `youtube_token.json` guardado. Comando exacto abajo. |
| cosmic-lens | `_sya_tester` | ✗ falta client_secret | No hay `client_secret` para esta cuenta en `youtube-tokens/downloads/` (sólo existen los de `sh.can.1`, `casshealt`, `syatesterwork`, `sya.automotriz09`). Requiere provisión desde cero en Google Cloud Console. |
| wild-whiskers | `_sya_testerwork` | ✗ refresh necesario | `client_secret` existe en `downloads/`, falta `youtube_token.json`. Comando exacto abajo. |
| sleepy-lofi | `_sya_automotriz09` | ✗ refresh necesario | `client_secret` existe en `downloads/`, falta `youtube_token.json`. Comando exacto abajo. |

**Resumen: 2/8 válidos · 3/8 con client_secret pero necesitan reautorización por navegador · 3/8 sin client_secret utilizable (necesitan provisión nueva en Google Cloud Console antes de poder correr ningún comando).**

### Comandos exactos para los 3 canales con client_secret (Cano los corre, no Claude — abre navegador)

Requiere `google-auth-oauthlib` + `google-api-python-client`. Ya están instalados en
`~/repos/factory-ia-channel-v5/.venv` (repo externo, uso de su intérprete
únicamente, sin tocar sus archivos) — o instalar en cualquier venv propio con
`pip install google-auth-oauthlib google-api-python-client`.

**unsolved-lens (`_sh_can`)**
```bash
~/repos/factory-ia-channel-v5/.venv/bin/python3 - <<'PY'
from google_auth_oauthlib.flow import InstalledAppFlow
import pathlib

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
secret = pathlib.Path.home() / ".secrets/credenciales/credenciales/youtube-tokens/downloads/client_secret_507798531585-gmlu6j54el3qik4f284fs2d4mc10po89.apps.googleusercontent.com_sh.can.1.json"
flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
creds = flow.run_local_server(port=0)
out_dir = pathlib.Path.home() / ".secrets/credenciales/credenciales/youtube-tokens/_sh_can"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "youtube_token.json").write_text(creds.to_json())
print("guardado:", out_dir / "youtube_token.json")
PY
```

**wild-whiskers (`_sya_testerwork`)**
```bash
~/repos/factory-ia-channel-v5/.venv/bin/python3 - <<'PY'
from google_auth_oauthlib.flow import InstalledAppFlow
import pathlib

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
secret = pathlib.Path.home() / ".secrets/credenciales/credenciales/youtube-tokens/downloads/client_secret_91696043199-h58isk4gni8tp5bb64o0pap6uv4ufi7o.apps.googleusercontent.com_syatesterwork.json"
flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
creds = flow.run_local_server(port=0)
out_dir = pathlib.Path.home() / ".secrets/credenciales/credenciales/youtube-tokens/_sya_testerwork"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "youtube_token.json").write_text(creds.to_json())
print("guardado:", out_dir / "youtube_token.json")
PY
```

**sleepy-lofi (`_sya_automotriz09`)**
```bash
~/repos/factory-ia-channel-v5/.venv/bin/python3 - <<'PY'
from google_auth_oauthlib.flow import InstalledAppFlow
import pathlib

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]
secret = pathlib.Path.home() / ".secrets/credenciales/credenciales/youtube-tokens/downloads/client_secret_2_837097164006-ibubnbejda9b434mmt9umfun2eq9lmq8.apps.googleusercontent.com_sya.automotriz09.json"
flow = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES)
creds = flow.run_local_server(port=0)
out_dir = pathlib.Path.home() / ".secrets/credenciales/credenciales/youtube-tokens/_sya_automotriz09"
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "youtube_token.json").write_text(creds.to_json())
print("guardado:", out_dir / "youtube_token.json")
PY
```

Nota: `run_local_server(port=0)` abre un navegador local. Esta máquina corre
desatendida — si no hay sesión gráfica disponible aquí, correr el comando
desde una máquina con navegador (o vía túnel SSH al puerto que imprima la
consola) y luego copiar el `youtube_token.json` resultante a la ruta indicada
en esta máquina. Scopes tomados de `youtube-tokens/INDEX.md` (mismos 4 usados
en los tokens que ya funcionan).

Para `sya-animals`, `sya-motive` y `cosmic-lens` no hay comando posible: falta
el `client_secret.json` (o está corrupto/vacío) y ese archivo sólo se obtiene
desde Google Cloud Console → credenciales OAuth del proyecto correspondiente,
paso de navegador que le toca a Cano.

---

## 2. UploadPost

Validado en vivo vía MCP `Upload-post` (`get_account_info`, gratuito):

- **Token válido**: sí — `"Token is valid"`, cuenta `shedy.yniguez@gmail.com`, plan **Basic**.
- Confirma que `UPLOADPOST_API_KEY` + `UPLOADPOST_TOKEN_2` (presentes en `.env` de command-center desde F1) están activos.

Perfiles (`list_users`, gratuito) — **4 perfiles, los 4 con YouTube conectado** (coincide con lo esperado en el plan):

| Perfil | YouTube | Otras redes conectadas |
|---|---|---|
| `cano_digital_ia` | ✓ @cano_digital_ai | tiktok, facebook, instagram, threads (reauth), x (reauth) |
| `CASS` | ✓ @casshealtbeauty | tiktok, facebook, instagram, x (reauth) |
| `SYA_MOTIVE` | ✓ @syamotive | tiktok, instagram, facebook, threads, x (reauth) |
| `SYA_ANIMALS` | ✓ @syaanimals | tiktok, instagram, facebook, threads, x (reauth) |

Nota aparte: varias cuentas `x` (y una `threads`) están marcadas
`reauth_required: true` dentro de Upload-Post mismo — no bloquea YouTube, es
un dato adicional para si se planea publicar en X/Threads vía Upload-Post.

---

## 3. Tabla de provisión de cuentas propias obligatorias

Fuente: `SYSTEMS_MATRIX_HERMES.md §7` (command-center, solo lectura).
Verificado por **presencia/ausencia de nombre de variable** (sin imprimir
valores) en `~/.secrets/credenciales/credenciales/.env` y
`~/repos/hermes-agent/.env` (`~/.hermes/.env` no existe). Cruzado también
contra `reports/connection-matrix-2026-08-05.md` (F2).

| Servicio | ¿Existe en vault/hermes-agent? | Estado | Pendiente de Cano |
|---|---|---|---|
| ElevenLabs | ✓ `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID_ALFONSO` | provisto | — |
| Apify | ✓ `APIFY_API_KEY` + `APIFY_KEY_1..7` | provisto (confirmado F2) | — |
| Supabase | ✓ `SUPABASE_PAT`, `SUPABASE_ORION_*`, `SUPABASE_NISSAN_*`, `SUPABASE_WORLDVIBE_*`, `SUPABASE_DB_DIRECT_URL` | provisto (multi-proyecto) | — |
| HeyGen | ✓ `HEYGEN_API_KEY`, `HEYGEN_N8N_CRED_ID` | provisto | — |
| Notion cloud | ✓ `NOTION_TOKEN`, `NOTION_WORKSPACE`, `NOTION_PAGE_ID` + 3 DB IDs | provisto | — |
| UploadPost | ✓ `UPLOADPOST_API_KEY`, `UPLOADPOST_TOKEN_2` | provisto y validado en vivo (§2) | — |
| YouTube OAuth por canal | parcial — `YOUTUBE_CLIENT_ID/SECRET_{CANO,ANIMALS,MOTIVE}` en vault + tokens reales sólo para 2/8 (§1) | parcial | correr los 3 comandos de §1, provisionar client_secret nuevo para los 3 restantes |
| Higgsfield | ✗ ninguna variable `HIGGSFIELD_*` | **suspendida** (confirmado, memoria previa + `connection-matrix-2026-08-05.md`: "cuenta suspendida") | reactivar cuenta con el proveedor antes de poder generar la API key |
| Shopify | ✗ ninguna variable `SHOPIFY_*` en ningún archivo revisado | falta por completo | crear app/tienda, generar Admin API token, agregar a vault |
| Meta Ads | ✗ ninguna variable `META_*` (ver §4) | falta por completo / deferred | crear Meta App, aprobación explícita antes de invocar (marcado `DEFERRED` en `docs/SANTMUN_REFERENCE_MAP.md`) |
| Gamma | ✗ ninguna variable `GAMMA_*` en vault de esta máquina | falta a nivel vault (el MCP Gamma de esta sesión de Claude es una conexión del lado de Claude.ai, no una credencial provista en esta máquina) | decidir si se necesita API key propia además del MCP, y agregarla al vault si sí |
| Canva | ✗ ninguna variable `CANVA_*` | falta a nivel vault (mismo caso que Gamma: hay MCP conectado en esta sesión, no hay credencial en el vault de la máquina) | igual que Gamma |
| Vercel | ✗ ninguna variable `VERCEL_*` | falta a nivel vault (MCP conectado en sesión, sin credencial en vault) | igual que Gamma/Canva |
| Adobe | ✗ ninguna variable `ADOBE_*` | falta a nivel vault (MCP conectado en sesión, sin credencial en vault) | igual que Gamma/Canva/Vercel |

**Resumen: 6/14 servicios completamente provistos (ElevenLabs, Apify, Supabase, HeyGen, Notion, UploadPost) · 1/14 parcial (YouTube, 2 de 8 canales) · 7/14 sin ninguna credencial en el vault de esta máquina (Higgsfield, Shopify, Meta, Gamma, Canva, Vercel, Adobe).**

Nota sobre Gamma/Canva/Vercel/Adobe: los 4 tienen MCP conectado y utilizable
en esta sesión de Claude (herramientas `mcp__claude_ai_Gamma__*`,
`mcp__claude_ai_Canva__*`, `mcp__claude_ai_Vercel__*`,
`mcp__claude_ai_Adobe_for_creativity__*`), pero eso es una integración del
lado de la cuenta de Claude.ai del operador, no una credencial que viva en
`~/.secrets` o en el `.env` de hermes-agent en esta máquina — por eso siguen
marcados "falta a nivel vault": si algún agente corriendo por fuera de esta
sesión de Claude.ai necesita hablarles directo, no tiene con qué.

---

## 4. Meta App — pendiente confirmado

- `~/repos/cano-ai-command-center/.env` (299 líneas): **no contiene ninguna
  línea `META_APP_ID` ni `META_APP_SECRET`** — ni vacías ni comentadas, están
  simplemente ausentes del archivo tal cual está hoy. Esto difiere levemente
  de la premisa de la tarea (que decía "F1 las dejó vacías"): el estado
  observado ahora es *ausentes*, no *presentes-con-valor-vacío*. El resultado
  práctico es el mismo — Meta Ads no está provisionado.
- `docs/SANTMUN_REFERENCE_MAP.md` (este repo, F7) confirma explícitamente:
  `meta-ads-skills` / `meta-ads-launch` están marcados 🚫 `DEFERRED` —
  "Automatización Meta Ads ... requiere aprobación explícita. **Prohibido
  invocar.**"
- `reports/connection-matrix-2026-08-05.md` (F2) no tiene ninguna fila
  `META_*` — consistente con que la variable nunca se agregó en ningún `.env`
  auditado.
- No se hizo nada más: queda documentado como pendiente de decisión/aprobación
  de Cano.

---

## Bloqueos

- Ningún bloqueo técnico en la validación misma (todo corrió con endpoints
  gratuitos, sin gasto).
- Los 6 pasos de remediación de YouTube (3 reauth + 3 provisión nueva) y los 7
  servicios sin vault requieren que Cano abra navegador / cree cuentas — nada
  de eso se ejecutó, por diseño de esta fase.
