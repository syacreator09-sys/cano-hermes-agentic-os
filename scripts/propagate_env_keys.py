"""C2 (plan de conexiones) -- propagación y saneamiento de `.env` por repo.

Con el registro canónico de C0 (`config/key_registry.yaml`) ya se sabe, por
llave, qué repo(s) la consumen de verdad (`consumidores`, poblado por
`scripts/build_key_registry.py` escaneando código fuente). Este script cierra
el hueco: copia del vault al `.env` de cada repo consumidor las llaves que le
faltan, y sanea placeholders detectados en valores ya presentes -- sin tocar
jamás un valor ya escrito por un humano.

REGLA ABSOLUTA (igual que `build_key_registry.py`): este módulo nunca
imprime, loguea ni guarda el *valor* de ninguna llave, en ningún modo,
incluido `--dry-run`. Solo nombres, repos y conteos.

## Universo de trabajo

Solo se opera sobre llaves cuya entrada en el registro tiene `consumidores`
no vacío -- es decir, con evidencia real de uso en código propio. Llaves sin
consumidor detectado (~42 de las 273) no se propagan a ningún repo: no hay
base para decidir a dónde irían. El repo consumidor se deriva de cada
ubicación `repo/relpath:línea` con `consumer_repos()` (import de
`build_key_registry`, no reimplementado).

Solo los 6 repos de `CONSUMER_REPO_NAMES` (import de `build_key_registry`,
misma lista canónica de C0) son editables. `cano-ai-command-center` nunca
puede aparecer aquí -- no está en esa lista y `build_key_registry.py` nunca
lo escanea, así que estructuralmente no puede tener `consumidores` que lo
mencionen. Se filtra de todas formas de forma defensiva.

## Tres operaciones, tres reglas distintas

1. **Llave ausente en el `.env` del repo** -> se copia del vault tal cual
   (mismo texto después del primer `=`, sin re-formatear comillas ni
   recortar espacios) como línea nueva al final del archivo. Si la llave
   tampoco está en el vault (no debería pasar -- el nombre viene del
   registro, que a su vez viene del vault -- pero se comprueba por si el
   registro quedó desincronizado de un `--vault`/`--registry` distintos en
   pruebas), se reporta y se omite: nunca se inventa un valor.
2. **Llave ya presente en el `.env` del repo, con o sin valor** -> NUNCA se
   toca. Ni para "arreglar" un placeholder -- eso es la operación 3, aparte,
   con su propio criterio.
3. **Saneo de placeholders** (`is_placeholder()` de `scripts/validators`):
   para cada llave ya presente en un `.env` de repo cuyo valor es un
   placeholder, se reporta como candidata. Se sobrescribe (solo esa línea,
   solo ese valor) SI Y SOLO SI el vault tiene, para ese mismo nombre, un
   valor utilizable (no vacío, no placeholder). Esta es la interpretación de
   "sanear placeholders" que usa este script: un placeholder con vault
   real disponible es, en la práctica, una llave que "falta" (el repo no
   tiene un valor que sirva); un placeholder sin contraparte utilizable en
   el vault se deja intacto y se reporta para que un humano decida --
   sobrescribir con OTRO placeholder o con vacío no mejora nada, y el script
   no inventa valores.

   Nota de criterio (para quien audite esta decisión más tarde): esto NO es
   "cualquier valor detectado como placeholder se sanea" -- eso arriesgaría
   pisar un valor real pero con pinta rara (p.ej. una URL corta) si
   `is_placeholder()` diera un falso positivo. Al exigir además un valor
   real en el vault como reemplazo, el peor caso de un falso positivo es
   "se sobrescribió un valor real con el mismo valor real que ya estaba en
   el vault" -- no una pérdida de dato, porque el vault es la fuente de
   verdad de la que ese repo debería estar tomando la llave de todos modos.

## Creación de `.env`

`ugc-commerce-studio` y `cano-investment-intelligence` no tienen `.env` hoy.
Solo se crea uno (vacío, permisos `0600`, ANTES de escribir ninguna línea)
si el registro detectó al menos una llave real que propagarle -- nunca se
crea un `.env` vacío "por si acaso".

## Seguridad de escritura

Antes de escribir cualquier cambio en el `.env` de un repo se corre
`git check-ignore` sobre esa ruta (con `cwd` en el repo). Si el archivo NO
sale como ignorado, la escritura de ESE repo se aborta por completo (no se
toca el archivo) y se reporta como error crítico -- nunca debe quedar un
`.env` con secretos fuera de `.gitignore`. Al terminar de escribir, se
verifica (y corrige si hace falta) que el archivo quede en permisos `0600`.

## Modo por defecto: dry-run

Sin flags el script es de solo lectura (`--dry-run` implícito) -- reporta el
plan completo (qué se agregaría, qué se sanearía, qué `.env` se crearían)
sin escribir nada. `--apply` es el único flag que escribe de verdad.

Flags:
  --apply            escribe los cambios. Sin este flag, dry-run.
  --dry-run          equivalente explícito al comportamiento por defecto.
  --vault PATH        vault alternativo (pruebas). Default: vault real.
  --registry PATH      registro alternativo (pruebas). Default: config/key_registry.yaml.
  --repos-root PATH    directorio que contiene los repos consumidores (pruebas). Default: ~/repos.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

HOME = Path.home()
REPO_ROOT = Path(__file__).resolve().parents[1]  # cano-hermes-agentic-os
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_key_registry import CONSUMER_REPO_NAMES, consumer_repos
from scripts.validators import is_placeholder, strip_quotes

DEFAULT_VAULT_PATH = HOME / ".secrets/credenciales/credenciales/.env"
DEFAULT_REGISTRY_PATH = REPO_ROOT / "config/key_registry.yaml"
DEFAULT_REPOS_ROOT = HOME / "repos"

# Mismo patrón que build_key_registry.VAULT_NAME_RE pero capturando también
# el valor (tal cual, sin strip) -- nunca se reformatea lo que viene del vault.
VAULT_LINE_RE = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")

# Parseo del .env de un repo consumidor: nombre + valor, tolera "export " y
# espacios alrededor del "=" (mismo criterio que scripts/connection_matrix.py
# NAME_LINE_RE, reimplementado aquí en vez de importado para no acoplar este
# script -- de escritura -- al de auditoría de solo lectura).
REPO_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


# =========================================================================
# 1. Lectura: vault (nombre + valor tal cual) y .env de repo
# =========================================================================

def read_vault_entries(vault_path: Path) -> dict[str, str]:
    """{NOMBRE: valor_tal_cual}. Última declaración gana (igual que un
    loader de .env real) -- el vault tiene 10 nombres duplicados por la
    fusión USB (ver build_key_registry.py)."""
    if not vault_path.exists():
        raise FileNotFoundError(f"vault no encontrado: {vault_path}")
    entries: dict[str, str] = {}
    for line in vault_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = VAULT_LINE_RE.match(line)
        if m:
            entries[m.group(1)] = m.group(2)
    return entries


@dataclass
class RepoEnv:
    exists: bool
    lines: list[str] = field(default_factory=list)
    active: dict[str, str] = field(default_factory=dict)
    line_index: dict[str, int] = field(default_factory=dict)


def read_repo_env(env_path: Path) -> RepoEnv:
    if not env_path.exists():
        return RepoEnv(exists=False)
    lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
    active: dict[str, str] = {}
    line_index: dict[str, int] = {}
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        body = line[len("export "):].strip() if line.startswith("export ") else line
        m = REPO_LINE_RE.match(body)
        if not m:
            continue
        name, value = m.group(1), m.group(2)
        active[name] = strip_quotes(value)
        line_index[name] = i  # última ocurrencia gana, igual que un loader real
    return RepoEnv(exists=True, lines=lines, active=active, line_index=line_index)


# =========================================================================
# 2. Universo: qué llave necesita cada repo (desde el registro)
# =========================================================================

def load_registry_entries(registry_path: Path) -> list[dict]:
    if not registry_path.exists():
        raise FileNotFoundError(f"registro no encontrado: {registry_path}")
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    return data.get("llaves", [])


def needed_keys_by_repo(entries: list[dict]) -> dict[str, set[str]]:
    """{repo: {NOMBRE, ...}} -- solo entradas con consumidores reales,
    solo repos de CONSUMER_REPO_NAMES (filtro defensivo, ver docstring)."""
    needed: dict[str, set[str]] = {}
    for entry in entries:
        consumidores = entry.get("consumidores") or []
        if not consumidores:
            continue
        for repo in consumer_repos(consumidores):
            if repo not in CONSUMER_REPO_NAMES:
                continue  # nunca debería pasar; command-center nunca puede llegar aquí
            needed.setdefault(repo, set()).add(entry["nombre"])
    return needed


# =========================================================================
# 3. Plan por repo (side-effect free -- usado también por --dry-run)
# =========================================================================

@dataclass
class RepoPlan:
    repo: str
    env_path: Path
    env_existed: bool
    repo_missing_on_disk: bool = False
    to_add: list[str] = field(default_factory=list)
    to_sanitize: list[str] = field(default_factory=list)
    placeholder_unfixable: list[str] = field(default_factory=list)
    missing_from_vault: list[str] = field(default_factory=list)

    @property
    def has_writes(self) -> bool:
        return bool(self.to_add or self.to_sanitize)


def plan_repo(
    repo: str, repos_root: Path, needed: set[str], vault_entries: dict[str, str]
) -> RepoPlan:
    repo_root = repos_root / repo
    env_path = repo_root / ".env"
    if not repo_root.exists():
        return RepoPlan(repo, env_path, env_existed=False, repo_missing_on_disk=True)

    repo_env = read_repo_env(env_path)
    plan = RepoPlan(repo, env_path, env_existed=repo_env.exists)

    for name in sorted(needed):
        vault_value = vault_entries.get(name)
        if name in repo_env.active:
            repo_value = repo_env.active[name]
            if is_placeholder(repo_value):
                if vault_value is not None and vault_value.strip() and not is_placeholder(vault_value):
                    plan.to_sanitize.append(name)
                else:
                    plan.placeholder_unfixable.append(name)
            continue  # regla 2: presente (con o sin valor) -> nunca se toca más allá del saneo
        if vault_value is None:
            plan.missing_from_vault.append(name)
        else:
            plan.to_add.append(name)
    return plan


def plan_all(
    registry_path: Path, vault_path: Path, repos_root: Path
) -> list[RepoPlan]:
    entries = load_registry_entries(registry_path)
    vault_entries = read_vault_entries(vault_path)
    needed = needed_keys_by_repo(entries)
    plans = []
    for repo in CONSUMER_REPO_NAMES:
        repo_needed = needed.get(repo)
        if not repo_needed:
            continue  # nada que propagar -> ni se toca ni se crea el .env (ver docstring)
        plans.append(plan_repo(repo, repos_root, repo_needed, vault_entries))
    return plans


# =========================================================================
# 4. Aplicación (solo con --apply)
# =========================================================================

@dataclass
class ApplyResult:
    repo: str
    added: int = 0
    sanitized: int = 0
    created_env: bool = False
    critical_error: str = ""


def _git_check_ignore(repo_root: Path, env_path: Path) -> tuple[bool, str]:
    """(ignorado, error). `ignorado=False` con `error` vacío significa que
    git respondió pero NO reporta el archivo como ignorado -- caso que debe
    abortar la escritura. `error` no vacío significa que el propio comando
    falló (repo sin .git, git no disponible, etc.) -- también aborta."""
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", str(env_path)],
            cwd=repo_root,
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"no se pudo ejecutar git check-ignore: {exc.__class__.__name__}"
    if proc.returncode == 0:
        return True, ""
    if proc.returncode == 1:
        return False, ""
    return False, f"git check-ignore salió con código {proc.returncode}"


def apply_plan(plan: RepoPlan, repos_root: Path, vault_entries: dict[str, str]) -> ApplyResult:
    res = ApplyResult(repo=plan.repo)
    if plan.repo_missing_on_disk:
        res.critical_error = "repo no encontrado en disco"
        return res
    if not plan.has_writes:
        return res

    repo_root = repos_root / plan.repo
    ignored, err = _git_check_ignore(repo_root, plan.env_path)
    if err:
        res.critical_error = f"git check-ignore falló: {err}"
        return res
    if not ignored:
        res.critical_error = ".env NO está en .gitignore -- escritura abortada"
        return res

    created = False
    if not plan.env_path.exists():
        plan.env_path.touch()
        plan.env_path.chmod(0o600)
        created = True

    repo_env = read_repo_env(plan.env_path)
    lines = list(repo_env.lines)

    for name in plan.to_sanitize:
        idx = repo_env.line_index[name]
        lines[idx] = f"{name}={vault_entries[name]}"

    for name in plan.to_add:
        lines.append(f"{name}={vault_entries[name]}")

    plan.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    plan.env_path.chmod(0o600)

    res.added = len(plan.to_add)
    res.sanitized = len(plan.to_sanitize)
    res.created_env = created
    return res


# =========================================================================
# 5. Reporte (nombres y conteos -- nunca valores)
# =========================================================================

def render_report(plans: list[RepoPlan], mode: str) -> str:
    lines = [f"## Propagación de llaves ({mode})", ""]
    if not plans:
        lines.append("Ningún repo tiene llaves pendientes de propagar según el registro.")
        return "\n".join(lines)

    for plan in plans:
        lines.append(f"### {plan.repo}")
        if plan.repo_missing_on_disk:
            lines.append("  ! repo no encontrado en disco -- omitido")
            lines.append("")
            continue
        lines.append(f"  .env existe: {'sí' if plan.env_existed else 'no (se crearía)'}")
        lines.append(f"  a agregar ({len(plan.to_add)}): {', '.join(plan.to_add) or '-'}")
        lines.append(
            f"  placeholders a sanear con valor real del vault "
            f"({len(plan.to_sanitize)}): {', '.join(plan.to_sanitize) or '-'}"
        )
        lines.append(
            f"  placeholders sin valor real en el vault, requieren atención manual "
            f"({len(plan.placeholder_unfixable)}): {', '.join(plan.placeholder_unfixable) or '-'}"
        )
        if plan.missing_from_vault:
            lines.append(
                f"  ! necesarias pero ausentes del vault ({len(plan.missing_from_vault)}): "
                f"{', '.join(plan.missing_from_vault)}"
            )
        lines.append("")
    return "\n".join(lines)


def render_summary(results: list[ApplyResult]) -> str:
    lines = ["## Resumen de aplicación", ""]
    total_added = sum(r.added for r in results)
    total_sanitized = sum(r.sanitized for r in results)
    total_created = sum(1 for r in results if r.created_env)
    errors = [r for r in results if r.critical_error]
    for r in results:
        if r.critical_error:
            lines.append(f"  ! {r.repo}: ERROR CRÍTICO -- {r.critical_error}")
        else:
            lines.append(
                f"  {r.repo}: +{r.added} agregadas, {r.sanitized} saneadas, "
                f"env creado: {'sí' if r.created_env else 'no'}"
            )
    lines.append("")
    lines.append(f"Total agregadas: {total_added}")
    lines.append(f"Total saneadas: {total_sanitized}")
    lines.append(f".env creados: {total_created}")
    lines.append(f"Errores críticos: {len(errors)}")
    return "\n".join(lines)


# =========================================================================
# 6. CLI
# =========================================================================

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--repos-root", type=Path, default=DEFAULT_REPOS_ROOT)
    args = parser.parse_args(argv)

    mode = "apply" if args.apply else "dry-run"

    plans = plan_all(args.registry, args.vault, args.repos_root)
    print(render_report(plans, mode))

    if not args.apply:
        return 0

    vault_entries = read_vault_entries(args.vault)
    results = [apply_plan(p, args.repos_root, vault_entries) for p in plans]
    print(render_summary(results))
    return 1 if any(r.critical_error for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
