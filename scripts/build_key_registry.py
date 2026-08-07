"""C0 (plan de conexiones) -- registro canónico de llaves del vault.

Lee los NOMBRES de variable del vault de credenciales
(`~/.secrets/credenciales/credenciales/.env`, 283 líneas hoy) y construye
`config/key_registry.yaml` + `docs/KEY_REGISTRY.md`: un registro con dueño
(dominio), uso, riesgo y estado de rotación por llave. Antes de este script
no existía ningún inventario -- "conectado" solo significaba "el nombre
existe en un archivo".

REGLA ABSOLUTA: este módulo nunca lee, guarda ni imprime el *valor* de una
llave. Los nombres se extraen línea por línea con el mismo patrón seguro
usado en el resto de la sesión (`^[A-Z_][A-Z0-9_]*=`, ancla de inicio de
línea -- ignora deliberadamente `export FOO=` y nombres comentados: el vault
real no usa ninguno de los dos, verificado antes de escribir este script).
Los "consumidores" que detecta son `archivo:línea`, nunca el contenido de
esa línea más allá de la llamada `os.getenv(...)` / `process.env.X` en sí.

## Deduplicación (283 líneas -> N nombres únicos)

El vault de hoy tiene 283 líneas `NOMBRE=` pero 10 nombres declarados dos
veces (`BASEROW_DB_PASS`, `BASEROW_SECRET_KEY`, `FORMBRICKS_DB_PASS`,
`FORMBRICKS_SECRET`, `LISTMONK_DB_PASS`, `METABASE_DB_PASS`,
`MINIO_PASSWORD`, `MINIO_USER`, `PLAUSIBLE_DB_PASS`,
`REDIS_AGENTS_PASSWORD`) -- artefacto de la fusión por USB. Un `.env` real
solo puede tener un valor activo por nombre (la segunda declaración pisa a
la primera al cargarlo), así que el registro es por *nombre único* --
273 hoy -- no por línea. `--check` reporta el conteo de líneas y el de
nombres únicos por separado para que el drift sea visible.

## Cómo se detectan consumidores

Un "consumidor real" es un match de alguno de estos patrones EXACTOS
(no substring) sobre archivos fuente propios editables:

  - Python:  `os.(getenv|environ.get|environ[)('NOMBRE'` / `("NOMBRE"`
  - JS/TS:   `process.env.NOMBRE` (word boundary)

Se escanea una sola vez por archivo (no una pasada por llave x archivo) y
solo se retiene el hallazgo si el nombre capturado está en el vault --
evita construir un índice de cada variable de entorno que aparezca en
código de terceros. Deliberadamente NO sigue accesos indirectos (p.ej.
`os.environ.get(name)` con `name` como variable, o listas de nombres tipo
`EXECUTOR_SECRET_ALLOWLIST` en `subprocess_executor.py`) -- por eso muchas
llaves con uso real en Hermes igual salen "sin consumidor detectado": el
propio plan de conexiones documenta este hueco (42/44 llaves del USB sin
consumidor por búsqueda exacta) y corregirlo no es tarea de C0.

Directorios de vendor/build (`node_modules`, `.venv`, `venv`, `dist`,
`build`, `.git`, `__pycache__`, `.next`, `.pytest_cache`, `.mypy_cache`,
`.ruff_cache`, `site-packages`) se excluyen del escaneo -- son dependencias
de terceros, no código propio. Única excepción explícita del plan: si un
symlink dentro de un repo escaneado (incluido bajo `.venv`) resuelve a una
ruta que contiene `cano-ai-command-center` (una copia/instalación editable
de Command Center vendida dentro de otro repo), SÍ se sigue y sus hallazgos
cuentan para el dominio del repo que lo contiene (p.ej. si aparece bajo
`factory-ia-channel-v5/`, cuenta como `factory-v5`). Hoy no existe ningún
symlink así en los repos reales (verificado), así que esta rama no dispara,
pero queda implementada para cuando exista.

## Regla de clasificación por dominio

1. Si hay consumidor real en `cano-hermes-agentic-os` o `hermes-agent` ->
   `starhome` (máxima prioridad -- son los repos que este plan gobierna).
2. Si no, si hay consumidor real en `factory-ia-channel-v5` (incluida la
   excepción de symlink de arriba) -> `factory-v5`.
3. Si no, si hay consumidor real en otro repo propio editable de la lista
   (`ugc-commerce-studio`, `amazon-fba-product-hunter`,
   `cano-investment-intelligence`) -> `otro-proyecto` (es un proyecto real
   de Cano, solo que no es Hermes/StarHome ni Factory V5).
4. Si no hay ningún consumidor propio, se mira el *nombre*: familias que
   son infraestructura autohospedada en los VPS de Cano (almacenamiento de
   objetos, analítica, formularios, firma electrónica, wiki, mesa de
   soporte -- servicios que corren en VPS1/VPS2, no APIs de un producto
   puntual) -> `vps-infra`. La lista exacta, tomada del plan: MinIO,
   Metabase, Plausible, Listmonk, Formbricks, DocSpring, VPS1_*, VPS2_*,
   JWT_* (firma interna de esos servicios), BookStack, Chatwoot.
5. Familias de SaaS/API atadas a un producto o cliente puntual (no son
   "infraestructura del servidor", son integraciones de negocio) pero sin
   consumidor propio detectado -> `otro-proyecto`: Cal.com (agenda),
   Retell (agente de voz), Evolution API (WhatsApp), Stripe *sin
   consumidor* (el plan lo pide así explícitamente -- Stripe con
   consumidor real ya habría caído en la regla 3).
6. Cualquier llave que no matchee nada de lo anterior -> `otro-proyecto`
   con `uso` anotado "sin clasificar, revisar con Cano".

## Reglas de riesgo (heurística, del propio plan)

`alto` si el nombre contiene SECRET/PASSWORD/PASS/PRIVATE (revisado en ese
orden de prioridad); si no, `medio` si contiene KEY/TOKEN/AUTH; si no,
`bajo` (URL/ID/EMAIL/USER/MODEL/etc.).

## Re-ejecución segura

Si `config/key_registry.yaml` ya existe, cada llave que YA tenía entrada
conserva esa entrada **completa tal cual** (dominio/uso/riesgo/
rotacion_pendiente/rotacion_motivo/proveedor/validacion -- todo lo que un
humano pudo haber curado a mano) y solo se le recalcula `consumidores`
escaneando los repos de nuevo. Las llaves nuevas del vault que no tenían
entrada se calculan con la heurística completa. Las entradas del YAML
cuyo nombre ya no está en el vault se eliminan del YAML escrito (drift:
"entrada sin llave") -- se listan en stdout, nunca se pierden en silencio.

Flags:
  --check        no escribe nada; reporta drift (llaves sin entrada,
                  entradas sin llave) y sale con código 1 si hay drift.
  --vault PATH   vault alternativo (pruebas).
  --repos-root PATH  directorio que contiene los repos consumidores, en vez
                  de ~/repos (pruebas).
  --registry PATH   ruta alternativa a config/key_registry.yaml (pruebas).
  --docs PATH       ruta alternativa a docs/KEY_REGISTRY.md (pruebas).
  --no-docs         no regenerar el markdown (por defecto sí se regenera).
"""
from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable
from pathlib import Path

import yaml

HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parents[1]  # cano-hermes-agentic-os

DEFAULT_VAULT_PATH = HOME / ".secrets/credenciales/credenciales/.env"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "config/key_registry.yaml"
DEFAULT_DOCS_PATH = REPO_ROOT / "docs/KEY_REGISTRY.md"

# Repos propios editables a escanear en busca de consumidores reales.
# El nombre es el que se usa en `consumidores` (relpath prefijado con esto).
CONSUMER_REPO_NAMES = [
    "cano-hermes-agentic-os",
    "factory-ia-channel-v5",
    "hermes-agent",
    "ugc-commerce-studio",
    "amazon-fba-product-hunter",
    "cano-investment-intelligence",
]

STARHOME_REPOS = {"cano-hermes-agentic-os", "hermes-agent"}
FACTORY_REPOS = {"factory-ia-channel-v5"}
OTRO_PROYECTO_REPOS = {
    "ugc-commerce-studio",
    "amazon-fba-product-hunter",
    "cano-investment-intelligence",
}

COMMAND_CENTER_MARKER = "cano-ai-command-center"

EXCLUDE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".pytest_cache", ".mypy_cache", ".ruff_cache", "site-packages",
    "egg-info",
}

PY_EXTS = {".py"}
JS_EXTS = {".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs"}
SCAN_EXTS = PY_EXTS | JS_EXTS

PY_CONSUMER_RE = re.compile(
    r"os\.(?:getenv|environ\.get|environ\[)\(?\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]"
)
JS_CONSUMER_RE = re.compile(
    r"process\.env\.([A-Za-z_][A-Za-z0-9_]*)\b"
)

# Nombre del vault -> ("=", nombre) : nunca captura el valor.
VAULT_NAME_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)=")

# --- riesgo -------------------------------------------------------------
RISK_ALTO_RE = re.compile(r"SECRET|PASSWORD|PASS|PRIVATE")
RISK_MEDIO_RE = re.compile(r"KEY|TOKEN|AUTH")

# --- dominio: familias de infraestructura autohospedada (VPS) -----------
VPS_INFRA_PREFIXES = (
    "MINIO_", "METABASE_", "PLAUSIBLE_", "LISTMONK_", "FORMBRICKS_",
    "DOCSPRING_", "VPS1_", "VPS2_", "JWT_", "BOOKSTACK_", "CHATWOOT_",
)

# --- dominio: SaaS de negocio puntual, sin consumidor propio ------------
OTRO_PROYECTO_SIN_CONSUMIDOR_PREFIXES = (
    "CAL_COM_", "CAL_EVENT_TYPE_ID", "RETELL_", "EVOLUTION_", "STRIPE_",
)

SUFFIX_LABELS = [
    ("_API_KEY", "clave de API"),
    ("_API_TOKEN", "token de API"),
    ("_API_URL", "URL de API"),
    ("_API_SECRET", "secreto de API"),
    ("_SECRET_KEY", "clave secreta"),
    ("_ACCESS_KEY", "clave de acceso"),
    ("_PUBLISHABLE_KEY", "clave pública"),
    ("_PUBLIC_KEY", "clave pública"),
    ("_SECRET", "secreto"),
    ("_TOKEN", "token"),
    ("_KEY", "clave"),
    ("_URL", "URL"),
    ("_PASSWORD", "contraseña"),
    ("_PASS", "contraseña"),
    ("_USERNAME", "usuario"),
    ("_USER", "usuario"),
    ("_EMAIL", "email"),
    ("_ID", "identificador"),
    ("_MODEL", "modelo"),
    ("_PATH", "ruta de archivo"),
    ("_DIR", "directorio"),
    ("_ALGORITHM", "algoritmo"),
]
# más largos primero para no cortar "_API_KEY" como "_KEY"
SUFFIX_LABELS.sort(key=lambda pair: -len(pair[0]))

ROTATION_PENDING = {
    "KIMI_API_KEY": (
        "expuesta en transcript de sesión "
        "(F11, K9, K16 del plan Prometeo/HERMES-KICKOFF)"
    ),
    "NVIDIA_NIM_API_KEY": (
        "expuesta en transcript de sesión "
        "(F11, K9, K16 del plan Prometeo/HERMES-KICKOFF)"
    ),
}

PRESERVED_ON_RERUN = True  # documental; ver docstring "Re-ejecución segura"


# =========================================================================
# 1. Vault: solo nombres
# =========================================================================

def read_vault_key_names(vault_path: Path) -> tuple[list[str], list[str]]:
    """Devuelve (nombres_únicos_ordenados, nombres_en_orden_de_línea).

    Nunca toca el valor: cada línea se recorta en el primer `=`.
    """
    if not vault_path.exists():
        raise FileNotFoundError(f"vault no encontrado: {vault_path}")
    raw_names: list[str] = []
    for line in vault_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = VAULT_NAME_RE.match(line)
        if m:
            raw_names.append(m.group(1))
    unique = sorted(set(raw_names))
    return unique, raw_names


# =========================================================================
# 2. Escaneo de consumidores
# =========================================================================

def _should_follow_symlink_dir(path: Path) -> bool:
    """Solo True si el symlink resuelve a una copia de command-center."""
    try:
        resolved = path.resolve()
    except OSError:
        return False
    return COMMAND_CENTER_MARKER in str(resolved)


def _iter_source_files(repo_root: Path) -> Iterable[Path]:
    if not repo_root.exists():
        return
    stack = [repo_root]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            name = entry.name
            if entry.is_dir():
                if name in EXCLUDE_DIRS or name.endswith(".egg-info"):
                    continue
                if entry.is_symlink():
                    if _should_follow_symlink_dir(entry):
                        stack.append(entry)
                    continue
                stack.append(entry)
            elif entry.is_file() and entry.suffix in SCAN_EXTS:
                yield entry


def scan_repo_consumers(
    repo_name: str, repo_root: Path, vault_names: set[str]
) -> dict[str, list[str]]:
    """Escanea un repo; devuelve {NOMBRE: ["repo/relpath:línea", ...]}."""
    hits: dict[str, list[str]] = {}
    for file_path in _iter_source_files(repo_root):
        pattern = PY_CONSUMER_RE if file_path.suffix in PY_EXTS else JS_CONSUMER_RE
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for match in pattern.finditer(line):
                name = match.group(1)
                if name not in vault_names:
                    continue
                try:
                    relpath = file_path.relative_to(repo_root)
                except ValueError:
                    relpath = file_path
                location = f"{repo_name}/{relpath}:{lineno}"
                hits.setdefault(name, []).append(location)
    return hits


def scan_all_consumers(
    repos_root: Path, vault_names: set[str]
) -> dict[str, list[str]]:
    """Escanea todos los repos consumidores; fusiona resultados por nombre."""
    merged: dict[str, list[str]] = {}
    for repo_name in CONSUMER_REPO_NAMES:
        repo_path = repos_root / repo_name
        repo_hits = scan_repo_consumers(repo_name, repo_path, vault_names)
        for name, locations in repo_hits.items():
            merged.setdefault(name, []).extend(locations)
    for locations in merged.values():
        locations.sort()
    return merged


def consumer_repos(locations: list[str]) -> set[str]:
    return {loc.split("/", 1)[0] for loc in locations}


# =========================================================================
# 3. Heurísticas: proveedor / uso / riesgo / dominio
# =========================================================================

def _strip_trailing_numeric_variant(name: str) -> str:
    """APIFY_KEY_1 -> APIFY_KEY (variantes numeradas de la misma llave)."""
    return re.sub(r"_\d+$", "", name) or name


def derive_provider(name: str) -> str:
    base = _strip_trailing_numeric_variant(name)
    for suffix, _label in SUFFIX_LABELS:
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    words = [w for w in base.split("_") if w]
    if not words:
        return name
    parts = []
    for w in words:
        if len(w) <= 4 and w.isupper():
            parts.append(w)  # deja siglas cortas (CF, HF, N8N, VPS1) tal cual
        else:
            parts.append(w.capitalize())
    return " ".join(parts)


def derive_kind_label(name: str) -> str:
    base = _strip_trailing_numeric_variant(name)
    for suffix, label in SUFFIX_LABELS:
        if base.endswith(suffix):
            return label
    return "variable de configuración"


def derive_riesgo(name: str) -> str:
    if RISK_ALTO_RE.search(name):
        return "alto"
    if RISK_MEDIO_RE.search(name):
        return "medio"
    return "bajo"


def derive_dominio_y_uso_nota(name: str, locations: list[str]) -> tuple[str, str]:
    """Devuelve (dominio, nota_extra_para_uso) aplicando la regla del docstring."""
    if locations:
        repos = consumer_repos(locations)
        if repos & STARHOME_REPOS:
            return "starhome", ""
        if repos & FACTORY_REPOS:
            return "factory-v5", ""
        if repos & OTRO_PROYECTO_REPOS:
            return "otro-proyecto", ""
        # no debería llegar aquí si locations viene de scan_all_consumers,
        # pero por robustez cae al mismo lugar que "sin consumidor".
    if name.startswith(VPS_INFRA_PREFIXES):
        return "vps-infra", ""
    if name.startswith(OTRO_PROYECTO_SIN_CONSUMIDOR_PREFIXES):
        return "otro-proyecto", ""
    return "otro-proyecto", "sin clasificar, revisar"


def build_uso(name: str, provider: str, locations: list[str], nota: str) -> str:
    kind = derive_kind_label(name)
    uso = f"{kind} de {provider}".strip()
    if locations:
        first = locations[0]
        extra = f" (+{len(locations) - 1} más)" if len(locations) > 1 else ""
        uso += f"; consumida en {first}{extra}"
    elif nota:
        # catch-all: ni consumidor propio ni patrón de nombre reconocido
        uso += f" -- sin consumidor detectado ni patrón reconocido, {nota} con Cano"
    else:
        # clasificada por patrón de nombre (vps-infra / SaaS de negocio) pero
        # sin consumidor propio -- igual queda pendiente de revisión humana
        uso += " -- sin consumidor detectado, revisar con Cano"
    return uso


def build_heuristic_entry(name: str, locations: list[str]) -> dict:
    provider = derive_provider(name)
    dominio, nota = derive_dominio_y_uso_nota(name, locations)
    riesgo = derive_riesgo(name)
    rotacion_motivo = ROTATION_PENDING.get(name, "")
    return {
        "nombre": name,
        "proveedor": provider,
        "dominio": dominio,
        "uso": build_uso(name, provider, locations, nota),
        "consumidores": list(locations),
        "validacion": "presence-only",
        "riesgo": riesgo,
        "rotacion_pendiente": name in ROTATION_PENDING,
        "rotacion_motivo": rotacion_motivo,
    }


# =========================================================================
# 4. Construcción del registro (con preservación en reruns)
# =========================================================================

def load_existing_registry(registry_path: Path) -> dict[str, dict]:
    if not registry_path.exists():
        return {}
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    entries = data.get("llaves", [])
    return {entry["nombre"]: entry for entry in entries}


def build_registry(
    vault_path: Path,
    repos_root: Path,
    registry_path: Path,
) -> dict:
    """Calcula el registro completo. No escribe nada (side-effect free)."""
    unique_names, raw_names = read_vault_key_names(vault_path)
    vault_name_set = set(unique_names)

    consumers_by_name = scan_all_consumers(repos_root, vault_name_set)
    existing = load_existing_registry(registry_path)

    entries: list[dict] = []
    for name in unique_names:
        locations = consumers_by_name.get(name, [])
        if name in existing:
            entry = dict(existing[name])
            entry["consumidores"] = list(locations)
            entries.append(entry)
        else:
            entries.append(build_heuristic_entry(name, locations))

    entries.sort(key=lambda e: e["nombre"])

    stale = sorted(set(existing) - vault_name_set)
    missing_before = sorted(vault_name_set - set(existing))

    return {
        "entries": entries,
        "vault_line_count": len(raw_names),
        "vault_unique_count": len(unique_names),
        "duplicated_names": sorted(
            n for n in set(raw_names) if raw_names.count(n) > 1
        ),
        "stale_entries": stale,
        "new_entries": missing_before,
    }


# =========================================================================
# 5. Salida: YAML + Markdown
# =========================================================================

def write_yaml(entries: list[dict], registry_path: Path) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "generado_por": "scripts/build_key_registry.py",
            "fuente": "~/.secrets/credenciales/credenciales/.env (solo nombres)",
            "nota": "Ningún valor de llave vive en este archivo.",
        },
        "llaves": entries,
    }
    registry_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )


DOMAIN_ORDER = ["starhome", "factory-v5", "otro-proyecto", "vps-infra"]
DOMAIN_TITLES = {
    "starhome": "StarHome / Hermes",
    "factory-v5": "Factory V5",
    "vps-infra": "Infraestructura VPS (autohospedada)",
    "otro-proyecto": "Otro proyecto",
}


def render_docs(entries: list[dict], vault_line_count: int, vault_unique_count: int) -> str:
    lines: list[str] = []
    lines.append("# Registro de llaves (`config/key_registry.yaml`)")
    lines.append("")
    lines.append(
        "Generado por `scripts/build_key_registry.py` a partir de los "
        "NOMBRES del vault (`~/.secrets/credenciales/credenciales/.env`). "
        "Ningún valor de llave aparece en este documento."
    )
    lines.append("")
    lines.append(
        f"Vault: {vault_line_count} líneas `NOMBRE=`, "
        f"{vault_unique_count} nombres únicos "
        f"({vault_line_count - vault_unique_count} declarados dos veces "
        "por la fusión USB)."
    )
    lines.append("")

    by_domain: dict[str, list[dict]] = {}
    for e in entries:
        by_domain.setdefault(e["dominio"], []).append(e)

    domains_present = [d for d in DOMAIN_ORDER if d in by_domain]
    domains_present += sorted(d for d in by_domain if d not in DOMAIN_ORDER)

    for domain in domains_present:
        rows = sorted(by_domain[domain], key=lambda e: e["nombre"])
        lines.append(f"## {DOMAIN_TITLES.get(domain, domain)} ({len(rows)})")
        lines.append("")
        lines.append("| nombre | proveedor | uso | riesgo | rotación pendiente |")
        lines.append("|---|---|---|---|---|")
        for e in rows:
            uso = e["uso"].replace("|", "\\|")
            rot = "sí" if e.get("rotacion_pendiente") else "no"
            lines.append(
                f"| `{e['nombre']}` | {e['proveedor']} | {uso} | "
                f"{e['riesgo']} | {rot} |"
            )
        lines.append("")

    lines.append("## Totales")
    lines.append("")
    lines.append(f"- Total de llaves: {len(entries)}")
    for domain in domains_present:
        lines.append(f"- {DOMAIN_TITLES.get(domain, domain)}: {len(by_domain[domain])}")
    sin_consumidor = [e for e in entries if not e.get("consumidores")]
    lines.append(f"- Sin consumidor detectado: {len(sin_consumidor)}")
    lines.append("")

    rotacion = [e for e in entries if e.get("rotacion_pendiente")]
    lines.append(f"## Rotación pendiente ({len(rotacion)})")
    lines.append("")
    if rotacion:
        for e in rotacion:
            lines.append(f"- `{e['nombre']}` -- {e.get('rotacion_motivo', '')}")
    else:
        lines.append("Ninguna.")
    lines.append("")

    return "\n".join(lines)


def write_docs(entries: list[dict], docs_path: Path, vault_line_count: int, vault_unique_count: int) -> None:
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(
        render_docs(entries, vault_line_count, vault_unique_count), encoding="utf-8"
    )


# =========================================================================
# 6. CLI
# =========================================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH)
    parser.add_argument("--repos-root", type=Path, default=HOME / "repos")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--docs", type=Path, default=DEFAULT_DOCS_PATH)
    parser.add_argument("--no-docs", action="store_true")
    args = parser.parse_args(argv)

    result = build_registry(args.vault, args.repos_root, args.registry)
    entries = result["entries"]

    if args.check:
        drift = result["new_entries"] or result["stale_entries"]
        print(
            f"vault: {result['vault_line_count']} líneas, "
            f"{result['vault_unique_count']} nombres únicos"
        )
        print(f"registro actual: {len(load_existing_registry(args.registry))} entradas")
        if result["new_entries"]:
            print(f"llaves nuevas sin entrada ({len(result['new_entries'])}):")
            for n in result["new_entries"]:
                print(f"  + {n}")
        if result["stale_entries"]:
            print(f"entradas sin llave en el vault ({len(result['stale_entries'])}):")
            for n in result["stale_entries"]:
                print(f"  - {n}")
        if not drift:
            print("sin drift: el YAML coincide con el vault.")
        return 1 if drift else 0

    write_yaml(entries, args.registry)
    if not args.no_docs:
        write_docs(entries, args.docs, result["vault_line_count"], result["vault_unique_count"])

    print(
        f"escrito {args.registry} -- {len(entries)} llaves "
        f"({result['vault_line_count']} líneas de vault, "
        f"{result['vault_unique_count']} nombres únicos)"
    )
    if result["new_entries"]:
        print(f"  nuevas (heurística completa): {len(result['new_entries'])}")
    if result["stale_entries"]:
        print(f"  eliminadas (ya no están en el vault): {len(result['stale_entries'])}")
        for n in result["stale_entries"]:
            print(f"    - {n}")
    if not args.no_docs:
        print(f"escrito {args.docs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
