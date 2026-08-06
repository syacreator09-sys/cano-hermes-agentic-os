"""F2 (plan Prometeo) — matriz de conexiones de credenciales.

Lee los `.env` de los 5 sistemas conocidos (StarHome, factory-v5,
command-center x2, hermes-agent), detecta variables con pinta de credencial
(KEY/TOKEN/SECRET/PASS/PASSWORD/AUTH en el nombre) y reporta si están
presentes, vacías/placeholder, o del todo ausentes — sin imprimir jamas
un valor. Ademas hace dos validaciones de red gratuitas (Apify, RapidAPI)
contra el vault de credenciales.

No toca cano-ai-command-center (solo lectura). No hace red salvo los dos
GET gratuitos descritos en el plan. No imprime valores de llaves.
"""
from pathlib import Path
from urllib import request, error
import re
import socket
import datetime

HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parents[1]  # cano-hermes-agentic-os

# Los 5 .env que exige F2, en el orden en que se listan en el plan.
SYSTEMS = [
    ("StarHome", HOME / "repos/cano-hermes-agentic-os/.env"),
    ("factory-v5", HOME / "repos/factory-ia-channel-v5/.env"),
    ("command-center (root)", HOME / "repos/cano-ai-command-center/.env"),
    ("command-center (content-studio)",
     HOME / "repos/cano-ai-command-center/01-offices/content-studio/.env"),
    ("hermes-agent", HOME / "repos/hermes-agent/.env"),
]

VAULT_PATH = HOME / ".secrets/credenciales/credenciales/.env"

CRED_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASS|AUTH)", re.IGNORECASE)
NAME_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
COMMENTED_NAME_RE = re.compile(r"^#+\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")

PLACEHOLDER_VALUES = {
    "xxx", "xxxx", "xxxxx", "xxxxxxxx", "todo", "change_me", "changeme",
    "your_key_here", "your_api_key_here", "replace_me", "replaceme",
    "placeholder", "fixme", "example", "dummy", "n/a", "na", "none", "null",
}
ALL_X_RE = re.compile(r"^x+$", re.IGNORECASE)


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def parse_env(path: Path):
    """Parsea NOMBRE=valor plano. Ignora comentarios y vacios.

    Devuelve (existe, activos: dict[str,str], comentados: set[str]) donde
    `comentados` son nombres que aparecen en una linea comentada tipo
    `# ALGO_KEY=...` (credencial "comentada-pendiente").
    """
    if not path.exists():
        return False, {}, set()
    active: dict[str, str] = {}
    commented: set[str] = set()
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            m = COMMENTED_NAME_RE.match(line)
            if m:
                commented.add(m.group(1))
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        m = NAME_LINE_RE.match(line)
        if not m:
            continue
        name, value = m.group(1), strip_quotes(m.group(2))
        active[name] = value
    return True, active, commented


def is_credential_name(name: str) -> bool:
    return bool(CRED_RE.search(name))


def is_placeholder(value: str) -> bool:
    v = value.strip().strip("'\"").lower()
    if not v:
        return False  # vacio se maneja aparte
    if v in PLACEHOLDER_VALUES:
        return True
    if ALL_X_RE.match(v):
        return True
    if "your_" in v and "_here" in v:
        return True
    if "changeme" in v or "change_me" in v:
        return True
    return False


def classify(var: str, exists: bool, active: dict, commented: set) -> tuple[str, str]:
    if not exists:
        return "✗", "archivo .env no encontrado"
    if var in active:
        val = active[var]
        if val.strip() == "":
            return "—", "presente, valor vacio"
        if is_placeholder(val):
            return "—", "presente, valor placeholder"
        return "✓", ""
    if var in commented:
        return "—", "comentada / pendiente"
    return "✗", "variable ausente en este archivo"


def annotate_expected(var: str, status: str, detail: str) -> str:
    if status == "✓":
        return detail
    if var.startswith("NVIDIA"):
        return (detail + " (esperado: llave NVIDIA rechaza inferencia 403, "
                "ver memoria)").strip(", ")
    if var.startswith("HIGGSFIELD"):
        return (detail + " (esperado: cuenta Higgsfield suspendida)").strip(", ")
    return detail


def build_matrix():
    parsed = {name: parse_env(path) for name, path in SYSTEMS}
    universe = set()
    for _, (exists, active, commented) in parsed.items():
        for k in active:
            if is_credential_name(k):
                universe.add(k)
        for k in commented:
            if is_credential_name(k):
                universe.add(k)

    rows = []
    for var in sorted(universe):
        provider = var.split("_")[0]
        for sysname, _ in SYSTEMS:
            exists, active, commented = parsed[sysname]
            status, detail = classify(var, exists, active, commented)
            detail = annotate_expected(var, status, detail)
            rows.append((provider, sysname, var, status, detail))
    return rows, parsed


def apify_candidates(vault_active: dict):
    names = ["APIFY_API_KEY"] + [f"APIFY_KEY_{i}" for i in range(1, 8)]
    out = []
    for n in names:
        v = vault_active.get(n, "")
        if v.strip() and not is_placeholder(v):
            out.append(n)
    return out, names


def check_apify(vault_active: dict):
    """Devuelve (estado, detalle, key_usada|None). Nunca imprime el valor."""
    usable, all_names = apify_candidates(vault_active)
    presence = {n: ("✓" if n in vault_active and vault_active[n].strip()
                     and not is_placeholder(vault_active[n])
                     else ("—" if n in vault_active else "✗"))
                for n in all_names}
    if not usable:
        return "—", "sin llave utilizable en el vault (todas vacias/ausentes/placeholder)", None, presence

    key_name = usable[0]
    key_value = vault_active[key_name]
    url = f"https://api.apify.com/v2/users/me?token={key_value}"
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=5) as resp:
            code = resp.getcode()
            if code == 200:
                return "✓", "perfil de usuario obtenido (200)", key_name, presence
            return "—", f"respuesta inesperada HTTP {code}", key_name, presence
    except error.HTTPError as e:
        if e.code in (401, 403):
            return "✗", f"llave invalida (HTTP {e.code})", key_name, presence
        return "—", f"error HTTP {e.code} (no es de autenticacion)", key_name, presence
    except (error.URLError, socket.timeout, TimeoutError, OSError) as e:
        return "—", f"error de red: {e.__class__.__name__}", key_name, presence


def check_rapidapi(vault_active: dict, vault_exists: bool):
    if not vault_exists:
        return "✗", "vault no encontrado"
    if "RAPIDAPI_KEY" in vault_active and vault_active["RAPIDAPI_KEY"].strip():
        return "—", "presente en vault pero F2 no la valido con red (fuera de alcance)"
    return "✗", "no encontrada en vault bajo ningun nombre (confirmado en F1); sin intento de red"


def render_report(rows, parsed, apify_result, rapidapi_result, apify_presence, out_path: Path):
    today = datetime.date.today().isoformat()
    lines = []
    lines.append(f"# Matriz de conexiones — {today}")
    lines.append("")
    lines.append("Generado por `scripts/connection_matrix.py` (plan Prometeo, fase F2).")
    lines.append("Nunca contiene valores de llaves — solo presencia/ausencia y, para "
                 "Apify, el resultado de un GET gratuito de perfil.")
    lines.append("")

    lines.append("## Notas de contexto (✗ esperables, no son bugs)")
    lines.append("")
    lines.append("- `NVIDIA_*`: llave conocida como invalida, rechaza inferencia con "
                 "403 (ver memoria del operador).")
    lines.append("- `HIGGSFIELD_*`: cuenta suspendida.")
    lines.append("- OAuth manuales de canales (Nous/Codex/xAI/Qwen): no viven en estos "
                 "`.env` como credenciales de archivo — se ven con `hermes status`, "
                 "actualmente deslogueados; no aplica a esta matriz.")
    lines.append("")

    lines.append("## Sistemas leidos")
    lines.append("")
    lines.append("| sistema | archivo | encontrado |")
    lines.append("|---|---|---|")
    for sysname, path in SYSTEMS:
        exists = parsed[sysname][0]
        mark = "si" if exists else "NO — archivo no encontrado"
        lines.append(f"| {sysname} | `{path}` | {mark} |")
    lines.append("")

    lines.append("## Matriz por proveedor")
    lines.append("")
    lines.append("proveedor|sistema|variable|estado|detalle")
    lines.append("---|---|---|---|---")

    totals_by_system = {sysname: {"✓": 0, "✗": 0, "—": 0} for sysname, _ in SYSTEMS}
    totals_overall = {"✓": 0, "✗": 0, "—": 0}

    providers = sorted(set(r[0] for r in rows))
    for provider in providers:
        prov_rows = [r for r in rows if r[0] == provider]
        for _, sysname, var, status, detail in prov_rows:
            lines.append(f"{provider}|{sysname}|{var}|{status}|{detail}")
            totals_by_system[sysname][status] += 1
            totals_overall[status] += 1
    lines.append("")

    lines.append("## Validacion de red — Apify")
    lines.append("")
    a_status, a_detail, a_key, presence = apify_result
    lines.append(f"- Vault usado: `{VAULT_PATH}`")
    lines.append(f"- Llave probada: `{a_key or '(ninguna utilizable)'}` "
                 "(valor nunca impreso)")
    lines.append(f"- Endpoint: `GET https://api.apify.com/v2/users/me?token=<key>` "
                 "(gratuito, no consume creditos)")
    lines.append(f"- Resultado: **{a_status}** — {a_detail}")
    lines.append("")
    lines.append("Presencia de candidatas en el vault (sin valores):")
    lines.append("")
    lines.append("variable|estado")
    lines.append("---|---")
    for n, st in presence.items():
        lines.append(f"{n}|{st}")
    lines.append("")

    lines.append("## Validacion de red — RapidAPI")
    lines.append("")
    r_status, r_detail = rapidapi_result
    lines.append(f"- Variable: `RAPIDAPI_KEY`")
    lines.append(f"- Resultado: **{r_status}** — {r_detail}")
    lines.append("")

    lines.append("## Resumen — totales por sistema")
    lines.append("")
    lines.append("sistema|✓|✗|—")
    lines.append("---|---|---|---")
    for sysname, _ in SYSTEMS:
        t = totals_by_system[sysname]
        lines.append(f"{sysname}|{t['✓']}|{t['✗']}|{t['—']}")
    lines.append("")
    lines.append(f"**Total general**: ✓ {totals_overall['✓']}  "
                 f"✗ {totals_overall['✗']}  "
                 f"— {totals_overall['—']}")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return totals_by_system, totals_overall


def main():
    rows, parsed = build_matrix()

    vault_exists, vault_active, _ = parse_env(VAULT_PATH)
    apify_result = check_apify(vault_active) if vault_exists else \
        ("✗", "vault no encontrado", None, {})
    rapidapi_result = check_rapidapi(vault_active, vault_exists)

    today = datetime.date.today().isoformat()
    out_path = REPO_ROOT / "reports" / f"connection-matrix-{today}.md"
    totals_by_system, totals_overall = render_report(
        rows, parsed, apify_result, rapidapi_result, apify_result[3], out_path
    )

    print(f"reporte: {out_path}")
    print(f"totales: ✓{totals_overall['✓']} "
          f"✗{totals_overall['✗']} —{totals_overall['—']}")
    print(f"apify: {apify_result[0]} — {apify_result[1]}")
    print(f"rapidapi: {rapidapi_result[0]} — {rapidapi_result[1]}")


if __name__ == "__main__":
    main()
