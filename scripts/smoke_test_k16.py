#!/usr/bin/env python3
"""K16 — smoke test end-to-end del ciclo orden -> dispatch.

Verifica que con el entorno .env.smoke-test se puede:
  1. Crear una orden via POST /api/orders
  2. Despacharla via POST /api/orders/{id}/dispatch
  3. Confirmar que no se genera gasto real (modo dry_run, budget 0)

Uso:
    cd /home/cano/repos/cano-hermes-agentic-os
    HERMES_ENV_FILE=.env.smoke-test python scripts/smoke_test_k16.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Cargar el env de smoke test ANTES de importar cano_hermes
root = Path(__file__).resolve().parents[1]
env_path = root / ".env.smoke-test"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key, value)

# Forzar la DB de smoke test para no tocar produccion
os.environ["HERMES_DATABASE_URL"] = f"sqlite:///{tempfile.gettempdir()}/hermes-k16-smoke.db"

from cano_hermes.api.app import app  # noqa: E402
from cano_hermes.bridge.kanban_bridge import BridgeSubmission  # noqa: E402
from cano_hermes.config import settings  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


def main() -> int:
    print("=" * 60)
    print("K16 Smoke Test — Ciclo Orden -> Dispatch")
    print("=" * 60)

    # Verificar modo seguro
    print(f"\n1. Execution mode: {settings.execution_mode}")
    if settings.execution_mode != "dry_run":
        print("   ERROR: no esta en dry_run. ABORTANDO.")
        return 1
    print("   OK — modo simulado, sin subprocess reales.")

    print(f"\n2. Daily budget: ${settings.default_daily_budget_usd}")
    if settings.default_daily_budget_usd != 0.0:
        print("   WARN: budget no es cero.")
    else:
        print("   OK — presupuesto diario es $0.")

    client = TestClient(app)

    # 3. Crear orden
    print("\n3. Creando orden de prueba...")
    response = client.post(
        "/api/orders",
        json={
            "objective": "[K16 smoke test] verificar ciclo orden->dispatch sin gasto",
            "source": "cli",
            "budget": {"max_cost_usd": 0.0},
        },
    )
    if response.status_code != 201:
        print(f"   ERROR: POST /api/orders -> {response.status_code}: {response.text}")
        return 1
    order = response.json()
    order_id = order["id"]
    print(f"   OK — orden creada: {order_id}")
    print(f"   Estado inicial: {order['status']}")

    # 4. Despachar orden (mock del bridge para no depender de hermes CLI)
    print("\n4. Despachando orden...")
    with patch("cano_hermes.api.app.kanban_bridge.submit_order_to_kanban") as fake_submit:
        fake_submit.return_value = BridgeSubmission(
            kanban_task_id=f"kt-smoke-{order_id}",
            board="starhome",
            command=["hermes", "kanban", "--board", "starhome", "create", "smoke"],
        )
        dispatch_response = client.post(f"/api/orders/{order_id}/dispatch")

    if dispatch_response.status_code != 200:
        print(f"   ERROR: dispatch -> {dispatch_response.status_code}: {dispatch_response.text}")
        return 1
    dispatched = dispatch_response.json()
    print(f"   OK — orden despachada")
    print(f"   Estado final: {dispatched['status']}")
    print(f"   Kanban task: {dispatched['bridge_link']['kanban_task_id']}")

    # 5. Verificar que no hay gasto
    print("\n5. Verificando que no hay gasto real...")
    from cano_hermes.governance.budget import BudgetService  # noqa: E402
    from cano_hermes.storage.sqlite import SQLiteStore  # noqa: E402

    store = SQLiteStore(settings.database_url)
    budget = BudgetService(store)
    ledger = budget.ledger_for()
    print(f"   Gasto del dia: ${ledger.spent_usd:.2f}")
    print(f"   Presupuesto restante: ${ledger.remaining_usd:.2f}")
    if ledger.spent_usd > 0:
        print("   ERROR: se registro algun gasto. Revisar configuracion.")
        return 1
    print("   OK — cero gasto registrado.")

    print("\n" + "=" * 60)
    print("K16 Smoke Test: PASADO")
    print("=" * 60)
    print("\nResumen:")
    print(f"  - Orden creada: {order_id}")
    print(f"  - Despachada a kanban: {dispatched['bridge_link']['kanban_task_id']}")
    print(f"  - Modo: {settings.execution_mode}")
    print(f"  - Gasto real: $0.00")
    print("\nEl entorno esta listo para smoke tests sin riesgo de cargo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
