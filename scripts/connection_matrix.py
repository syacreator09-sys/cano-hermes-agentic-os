"""F2 (plan Prometeo) / C1 (plan de conexiones) — matriz de conexiones de credenciales.

Lee los `.env` de los 5 sistemas conocidos (StarHome, factory-v5, command-center x2,
hermes-agent) + el vault de credenciales (fuente de verdad, 6º "sistema" desde C1),
detecta variables con pinta de credencial (KEY/TOKEN/SECRET/PASS/PASSWORD/AUTH en el
nombre) y reporta si están presentes, vacías/placeholder, o del todo ausentes — sin
imprimir jamas un valor.

Además corre el registro de validadores en vivo de `scripts/validators/registry.py`
(paquete nuevo de C1): ~35 proveedores, cada uno con endpoint documentado como gratis
y sin cuota, con concurrencia limitada y timeout de 5s -- nunca un valor de llave sale
de aquí, solo status/detalle/latencia/cuota.

No toca cano-ai-command-center (solo lectura). No hace red salvo los GETs gratuitos
descritos en `scripts/validators/registry.py`. No imprime valores de llaves.

F13 (plan Prometeo) añadió `compute_and_render()` + `--json`: el resto del módulo
(parseo, matriz, reporte markdown) es exactamente el de F2, sin tocar. C1 (plan de
conexiones) refactorizó los validadores hardcodeados (`check_apify`/`check_rapidapi`,
firmas heterogéneas) a `scripts/validators/registry.py`'s `VALIDATORS` dict con firma
común -- ver ese módulo para el detalle de cada endpoint.
"""
import argparse
import datetime
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parents[1]  # cano-hermes-agentic-os
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validators import is_placeholder, strip_quotes
from scripts.validators.registry import VALIDATORS

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

# C1: el vault se suma como 6º "sistema" -- es la fuente de verdad de credenciales,
# no se "audita" contra nada (no hay ningún otro sistema con más autoridad), pero
# debe aparecer en el reporte para que se vea, por comparación con los otros 5, qué
# le falta propagar a cada repo (eso es tarea de C2). `ALL_SYSTEMS` es lo que usan
# `build_matrix()`/`render_report()`; `SYSTEMS` se deja intacto porque es lo que
# describe el docstring original de F2 (los 5 `.env` de repos).
VAULT_SYSTEM = ("Vault (fuente de verdad)", VAULT_PATH)
ALL_SYSTEMS = SYSTEMS + [VAULT_SYSTEM]

MAX_VALIDATOR_WORKERS = 8
VALIDATOR_TIMEOUT_S = 5  # aplicado dentro de cada validador (scripts/validators.http_get)

CRED_RE = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASS|AUTH)", re.IGNORECASE)
NAME_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")
COMMENTED_NAME_RE = re.compile(r"^#+\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


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
    parsed = {name: parse_env(path) for name, path in ALL_SYSTEMS}
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
        for sysname, _ in ALL_SYSTEMS:
            exists, active, commented = parsed[sysname]
            status, detail = classify(var, exists, active, commented)
            detail = annotate_expected(var, status, detail)
            rows.append((provider, sysname, var, status, detail))
    return rows, parsed


def run_validators(vault_active: dict) -> dict[str, dict]:
    """Corre `VALIDATORS` (scripts/validators/registry.py) con concurrencia limitada
    (`ThreadPoolExecutor`, max 8) -- cada validador ya trae su propio timeout de 5s y
    nunca levanta (contrato del paquete), pero esta función igual envuelve el `.result()`
    en un `try` para que un bug real en un validador de terceros no tumbe la corrida
    completa de la matriz."""
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=MAX_VALIDATOR_WORKERS) as pool:
        futures = {pool.submit(fn, vault_active): name for name, fn in VALIDATORS.items()}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as exc:  # noqa: BLE001 -- último cinturón de seguridad
                results[name] = {
                    "status": "—",
                    "detail": f"validador levantó excepción inesperada: {exc.__class__.__name__}",
                    "latency_ms": None,
                    "quota": None,
                }
    return results


def render_report(rows, parsed, validator_results: dict[str, dict], out_path: Path):
    today = datetime.date.today().isoformat()
    lines = []
    lines.append(f"# Matriz de conexiones — {today}")
    lines.append("")
    lines.append("Generado por `scripts/connection_matrix.py` (plan de conexiones, fase C1, "
                 "sobre la base de F2/F13 del plan Prometeo).")
    lines.append("Nunca contiene valores de llaves — solo presencia/ausencia y, para los "
                 "proveedores en `live-free`, el resultado de un GET gratuito de "
                 "perfil/cuota/whoami.")
    lines.append("")

    lines.append("## Notas de contexto (✗ esperables, no son bugs)")
    lines.append("")
    lines.append("- `NVIDIA_*`: llave conocida como invalida, rechaza inferencia con "
                 "403 (ver memoria del operador) — el validador en vivo lo confirma.")
    lines.append("- `HIGGSFIELD_*`: cuenta suspendida — validador en `policy-skip`.")
    lines.append("- `KIE_*`/`MODAL_*`: `policy-skip` explícito — ver motivo en la tabla "
                 "de validadores.")
    lines.append("- **Vault**: es la fuente de verdad de credenciales, no se \"audita\" "
                 "contra nada — aparece para mostrar qué variables existen ahí y, por "
                 "comparación con cada repo, cuáles faltan propagar (tarea de C2).")
    lines.append("- OAuth manuales de canales (Nous/Codex/xAI/Qwen): no viven en estos "
                 "`.env` como credenciales de archivo — se ven con `hermes status`, "
                 "actualmente deslogueados; no aplica a esta matriz.")
    lines.append("")

    lines.append("## Sistemas leidos")
    lines.append("")
    lines.append("| sistema | archivo | encontrado |")
    lines.append("|---|---|---|")
    for sysname, path in ALL_SYSTEMS:
        exists = parsed[sysname][0]
        mark = "si" if exists else "NO — archivo no encontrado"
        lines.append(f"| {sysname} | `{path}` | {mark} |")
    lines.append("")

    lines.append("## Matriz por proveedor (presencia, sin red)")
    lines.append("")
    lines.append("proveedor|sistema|variable|estado|detalle")
    lines.append("---|---|---|---|---")

    totals_by_system = {sysname: {"✓": 0, "✗": 0, "—": 0} for sysname, _ in ALL_SYSTEMS}
    totals_overall = {"✓": 0, "✗": 0, "—": 0}

    providers = sorted(set(r[0] for r in rows))
    for provider in providers:
        prov_rows = [r for r in rows if r[0] == provider]
        for _, sysname, var, status, detail in prov_rows:
            lines.append(f"{provider}|{sysname}|{var}|{status}|{detail}")
            totals_by_system[sysname][status] += 1
            totals_overall[status] += 1
    lines.append("")

    lines.append("## Validadores en vivo (scripts/validators/registry.py, fase C1)")
    lines.append("")
    lines.append("Cada fila corre contra el vault (`~/.secrets/credenciales/credenciales/.env`), "
                 "nunca contra los `.env` de repo. Ver el docstring de cada `validate_*` en "
                 "`scripts/validators/registry.py` para la URL exacta y por qué es gratis. "
                 "`policy-skip` no es un fallo: es una decisión explícita de no arriesgar "
                 "gasto (ver detalle).")
    lines.append("")
    lines.append("proveedor|estado|detalle|latencia_ms|cuota")
    lines.append("---|---|---|---|---")

    live_totals = {"✓": 0, "✗": 0, "—": 0, "policy-skip": 0}
    for provider in sorted(validator_results):
        r = validator_results[provider]
        live_totals[r["status"]] = live_totals.get(r["status"], 0) + 1
        latency_str = str(r["latency_ms"]) if r.get("latency_ms") is not None else ""
        quota_str = json.dumps(r["quota"], ensure_ascii=False) if r.get("quota") else ""
        detail = str(r["detail"]).replace("|", "/").replace("\n", " ")
        lines.append(f"{provider}|{r['status']}|{detail}|{latency_str}|{quota_str}")
    lines.append("")
    lines.append(
        f"**Total validadores**: ✓ {live_totals['✓']}  ✗ {live_totals['✗']}  "
        f"— {live_totals['—']}  policy-skip {live_totals['policy-skip']}"
    )
    lines.append("")

    lines.append("## Resumen — totales por sistema (presencia)")
    lines.append("")
    lines.append("sistema|✓|✗|—")
    lines.append("---|---|---|---")
    for sysname, _ in ALL_SYSTEMS:
        t = totals_by_system[sysname]
        lines.append(f"{sysname}|{t['✓']}|{t['✗']}|{t['—']}")
    lines.append("")
    lines.append(f"**Total general (presencia)**: ✓ {totals_overall['✓']}  "
                 f"✗ {totals_overall['✗']}  "
                 f"— {totals_overall['—']}")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return totals_by_system, totals_overall, live_totals


def compute_and_render() -> dict:
    """Runs the full audit (presencia F2 + validadores en vivo C1), writes the
    markdown report (unchanged shape for the presence section) plus a JSON mirror
    next to it, and returns the same summary dict as a Python object -- the shared
    entry point for the CLI, `daily_cycle.py`, and `GET /api/dashboard`."""
    rows, parsed = build_matrix()

    vault_exists, vault_active, _ = parse_env(VAULT_PATH)
    if vault_exists:
        validator_results = run_validators(vault_active)
    else:
        validator_results = {
            name: {"status": "✗", "detail": "vault no encontrado", "latency_ms": None, "quota": None}
            for name in VALIDATORS
        }

    today = datetime.date.today().isoformat()
    out_path = REPO_ROOT / "reports" / f"connection-matrix-{today}.md"
    totals_by_system, totals_overall, live_totals = render_report(
        rows, parsed, validator_results, out_path
    )

    # Compatibilidad retro: `daily_cycle.py:192-193` y `cano_hermes/api/app.py:520-525`
    # leen `summary["apify"]`/`summary["rapidapi"]` con la forma exacta
    # `{"status": .., "detail": ..}` desde F13 -- se preserva sin cambios aunque el
    # detalle ahora venga del registry unificado.
    def _legacy(name: str) -> dict:
        r = validator_results.get(name)
        if r is None:
            return {"status": "✗", "detail": "validador no registrado"}
        return {"status": r["status"], "detail": r["detail"]}

    summary = {
        "date": today,
        "report_path": str(out_path),
        "systems": {
            sysname: {
                "found": parsed[sysname][0],
                "counts": totals_by_system[sysname],
            }
            for sysname, _ in ALL_SYSTEMS
        },
        "totals": totals_overall,
        "validators": validator_results,
        "validators_totals": live_totals,
        "apify": _legacy("apify"),
        "rapidapi": _legacy("rapidapi"),
    }

    json_path = out_path.with_suffix(".json")
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary["json_path"] = str(json_path)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true",
        help="ademas del reporte markdown de siempre, imprime el resumen en JSON a stdout",
    )
    args = parser.parse_args()

    summary = compute_and_render()

    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return

    print(f"reporte: {summary['report_path']}")
    print(f"totales (presencia): ✓{summary['totals']['✓']} "
          f"✗{summary['totals']['✗']} —{summary['totals']['—']}")
    vt = summary["validators_totals"]
    print(f"validadores en vivo: ✓{vt['✓']} ✗{vt['✗']} —{vt['—']} policy-skip{vt['policy-skip']}")
    print(f"apify: {summary['apify']['status']} — {summary['apify']['detail']}")
    print(f"rapidapi: {summary['rapidapi']['status']} — {summary['rapidapi']['detail']}")


if __name__ == "__main__":
    main()
