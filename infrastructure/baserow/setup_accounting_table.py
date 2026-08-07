#!/usr/bin/env python3
"""K18 (plan HERMES-KICKOFF) -- one-shot Baserow bootstrap for the
`contabilidad` table (unified business accounting: CASS / Cano Digital /
LUZYA / otro).

Modeled directly on `setup_content_table.py` (K17), same
register-then-JWT approach, for the exact same reason K17 hit: the K17
management token (`BASEROW_CONTENT_TOKEN`) is a database-scoped REST
*row* token (Token-auth), never a management-API token (JWT-only
endpoints -- `/api/database/tables/...`, `/api/database/fields/...`).
Confirmed live before writing this script, not assumed:

    curl -H "Authorization: Token $BASEROW_CONTENT_TOKEN" \
         http://localhost:8085/api/database/tables/database/34/
    -> 401 "Authentication credentials were not provided."

And the K17 registration flow never persisted its account password
anywhere (same as F11 before it, deliberately -- see setup_content_table
.py's own docstring), so there is no way to log back in as that account
and add a table to *its* workspace either. The reusable part is the
MECHANISM (register a throwaway user, own workspace, database-scoped
token minted at the end) -- not a shared workspace. So `contabilidad`
gets its own workspace ("StarHome K18 Accounting"), exactly like
`contenido` got its own ("StarHome K17 Content") for the same reason.
This is confirmed-before-assumed, per the K18 task brief.

Writes the new token straight into the vault .env
(~/.secrets/credenciales/credenciales/.env) as BASEROW_ACCOUNTING_TOKEN=...
-- never printed to stdout/stderr -- unsupervised run, same as K17.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://localhost:8085"
_suffix = __import__("secrets").token_hex(3)
EMAIL = f"starhome-k18+{_suffix}@starhome.local"
PASSWORD = "StarHome-K18-" + __import__("secrets").token_urlsafe(18)
NAME = "StarHome K18 Accounting"
VAULT_ENV_PATH = Path.home() / ".secrets/credenciales/credenciales/.env"


def call(method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    url = f"{BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"JWT {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} -> {e.code}: {e.read().decode()[:500]}") from e


def register() -> str:
    resp = call("POST", "/api/user/", body={
        "name": "StarHome K18", "email": EMAIL, "password": PASSWORD,
        "language": "en", "authenticate": True,
    })
    print(f"[setup_accounting_table] usuario registrado ({EMAIL})", file=sys.stderr)
    return resp["token"] if "token" in resp else resp["access_token"]


def main() -> None:
    token = register()

    ws = call("POST", "/api/workspaces/", token=token, body={"name": NAME})
    workspace_id = ws["id"]
    print(f"[setup_accounting_table] workspace {workspace_id}", file=sys.stderr)

    app = call("POST", f"/api/applications/workspace/{workspace_id}/", token=token, body={
        "name": NAME, "type": "database",
    })
    database_id = app["id"]
    print(f"[setup_accounting_table] database {database_id}", file=sys.stderr)

    # K18 mandate's exact column list: negocio, tipo, monto, moneda,
    # categoria, fecha, origen, referencia, cierre_mensual.
    fields = [
        ("negocio", "single_select", {"select_options": [
            {"value": v, "color": c} for v, c in [
                ("CASS", "blue"), ("Cano Digital", "green"),
                ("LUZYA", "orange"), ("otro", "light-gray"),
            ]
        ]}),
        ("tipo", "single_select", {"select_options": [
            {"value": "ingreso", "color": "green"},
            {"value": "gasto", "color": "red"},
        ]}),
        ("monto", "number", {"number_decimal_places": 4, "number_negative": False}),
        ("moneda", "text", {}),
        ("categoria", "text", {}),
        ("fecha", "date", {"date_include_time": True}),
        ("origen", "single_select", {"select_options": [
            {"value": "agente", "color": "blue"},
            {"value": "manual", "color": "light-gray"},
        ]}),
        ("referencia", "text", {}),
        ("cierre_mensual", "boolean", {}),
    ]

    table = call("POST", f"/api/database/tables/database/{database_id}/", token=token, body={
        "name": "contabilidad",
    })
    table_id = table["id"]
    print(f"[setup_accounting_table] tabla contabilidad -> id {table_id}", file=sys.stderr)

    existing_fields = call("GET", f"/api/database/fields/table/{table_id}/", token=token)
    primary = next(f for f in existing_fields if f.get("primary"))
    first_name, first_type, first_kwargs = fields[0]
    call("PATCH", f"/api/database/fields/{primary['id']}/", token=token, body={
        "name": first_name, "type": first_type, **first_kwargs,
    })
    for f in existing_fields:
        if not f.get("primary") and f["name"] in ("Notes", "Active"):
            call("DELETE", f"/api/database/fields/{f['id']}/", token=token)

    for field_name, field_type, kwargs in fields[1:]:
        call("POST", f"/api/database/fields/table/{table_id}/", token=token, body={
            "name": field_name, "type": field_type, **kwargs,
        })

    token_resp = call("POST", "/api/database/tokens/", token=token, body={
        "name": "k18-accounting", "workspace": workspace_id,
    })
    api_token_key = token_resp.get("key")

    with open("baserow_accounting_api_token.txt", "w") as fh:
        fh.write(api_token_key + "\n")
    os.chmod("baserow_accounting_api_token.txt", 0o600)

    if VAULT_ENV_PATH.exists():
        existing = VAULT_ENV_PATH.read_text(encoding="utf-8")
        if "BASEROW_ACCOUNTING_TOKEN=" not in existing:
            with open(VAULT_ENV_PATH, "a", encoding="utf-8") as fh:
                if not existing.endswith("\n"):
                    fh.write("\n")
                fh.write(
                    "# K18 (plan HERMES-KICKOFF) -- token de la API DB de Baserow self-hosted "
                    f"local (localhost:8085), workspace/database \"StarHome K18 Accounting\" "
                    f"(id {workspace_id}/{database_id}), tabla contabilidad (id {table_id}). "
                    "Generado por infrastructure/baserow/setup_accounting_table.py.\n"
                )
                fh.write(f"BASEROW_ACCOUNTING_TOKEN={api_token_key}\n")
            print("[setup_accounting_table] BASEROW_ACCOUNTING_TOKEN escrito en el vault", file=sys.stderr)
        else:
            print("[setup_accounting_table] BASEROW_ACCOUNTING_TOKEN ya existia en el vault -- no sobreescrito", file=sys.stderr)

    print(json.dumps({
        "workspace_id": workspace_id,
        "database_id": database_id,
        "table_id": table_id,
        "table_name": "contabilidad",
        "token_name": token_resp.get("name"),
        "token_written_to": [
            "infrastructure/baserow/baserow_accounting_api_token.txt (0600, gitignored)",
            "~/.secrets/credenciales/credenciales/.env (BASEROW_ACCOUNTING_TOKEN)",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
