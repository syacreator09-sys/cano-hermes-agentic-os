#!/usr/bin/env python3
"""K16 — valida que el entorno de smoke test no gasta dinero real.

Uso:
    cd /home/cano/repos/cano-hermes-agentic-os
    HERMES_ENV_FILE=.env.smoke-test python scripts/validate_smoke_test_env.py

Salida: 0 si todo OK, 1 si hay alguna credencial live o el modo no es dry_run.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def load_smoke_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            env[key] = value
    return env


def check_dry_run(env: dict[str, str]) -> list[str]:
    errors: list[str] = []
    mode = env.get("HERMES_EXECUTION_MODE", "")
    if mode != "dry_run":
        errors.append(f"HERMES_EXECUTION_MODE='{mode}' (esperado: dry_run)")
    return errors


def check_zero_budget(env: dict[str, str]) -> list[str]:
    errors: list[str] = []
    try:
        budget = float(env.get("HERMES_DEFAULT_DAILY_BUDGET_USD", "5.0"))
    except ValueError:
        budget = 5.0
    if budget != 0.0:
        errors.append(f"HERMES_DEFAULT_DAILY_BUDGET_USD={budget} (esperado: 0.0)")
    return errors


def check_approval_flags(env: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for key in ("HERMES_REQUIRE_APPROVAL_FOR_PAID_API", "HERMES_REQUIRE_APPROVAL_FOR_WRITES"):
        if env.get(key, "").lower() != "true":
            errors.append(f"{key}='{env.get(key)}' (esperado: true)")
    return errors


def check_no_live_stripe(env: dict[str, str]) -> list[str]:
    errors: list[str] = []
    live_patterns = [
        ("STRIPE_PUBLISHABLE_KEY_LIVE", r"^pk_live_"),
        ("STRIPE_SECRET_KEY_LIVE", r"^sk_live_"),
        ("STRIPE_SECRET_KEY", r"^sk_live_"),
    ]
    for key, pattern in live_patterns:
        value = env.get(key, "")
        if value and re.search(pattern, value):
            errors.append(f"{key} contiene clave LIVE de Stripe (patron: {pattern})")
    return errors


def check_no_twilio_prod(env: dict[str, str]) -> list[str]:
    errors: list[str] = []
    prod_sid = env.get("TWILIO_ACCOUNT_SID", "")
    # Los SID de produccion empiezan con AC; los de test con AC tambien,
    # pero el test SID conocido es el placeholder de TWILIO_TEST_ACCOUNT_SID
    test_sid = env.get("TWILIO_TEST_ACCOUNT_SID", "")
    if prod_sid and prod_sid != test_sid:
        errors.append(f"TWILIO_ACCOUNT_SID='{prod_sid}' no coincide con TWILIO_TEST_ACCOUNT_SID")
    return errors


def check_separate_database(env: dict[str, str]) -> list[str]:
    errors: list[str] = []
    db_url = env.get("HERMES_DATABASE_URL", "")
    if "smoke" not in db_url.lower():
        errors.append(f"HERMES_DATABASE_URL='{db_url}' no contiene 'smoke' (riesgo de pisar produccion)")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env_path = root / ".env.smoke-test"
    if not env_path.exists():
        print(f"ERROR: no se encuentra {env_path}")
        return 1

    env = load_smoke_env(env_path)
    all_errors: list[str] = []
    all_errors.extend(check_dry_run(env))
    all_errors.extend(check_zero_budget(env))
    all_errors.extend(check_approval_flags(env))
    all_errors.extend(check_no_live_stripe(env))
    all_errors.extend(check_no_twilio_prod(env))
    all_errors.extend(check_separate_database(env))

    if all_errors:
        print(f"FAIL: {len(all_errors)} problema(s) en .env.smoke-test:")
        for e in all_errors:
            print(f"  - {e}")
        return 1

    print("OK: entorno de smoke test verificado — sin gasto real posible.")
    print(f"  Modo: {env.get('HERMES_EXECUTION_MODE')}")
    print(f"  Budget: {env.get('HERMES_DEFAULT_DAILY_BUDGET_USD')} USD")
    print(f"  DB: {env.get('HERMES_DATABASE_URL')}")
    print(f"  Artefactos: {env.get('HERMES_ARTIFACT_PATH')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
