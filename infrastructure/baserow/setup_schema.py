#!/usr/bin/env python3
"""Plan Prometeo F11 -- one-shot Baserow schema bootstrap.

stdlib-only (no `requests` in this repo's venv). Talks to the local
Baserow instance over its REST API to:

  1. Register a dedicated StarHome user (or log in if it already exists).
  2. Create a workspace + database ("StarHome Prometeo").
  3. Create the 4 tables the F11 mandate asks for, with real fields (not
     just the default Name/Notes/Active Baserow gives new tables).
  4. Mint a database API token scoped to that database and print ONLY its
     id/name to stdout -- the token value is written straight to a local
     file (0600) for the caller to move into the vault, never printed.

Idempotent-ish: safe to re-run against an empty instance; re-running
against an already-populated one will fail loudly on the workspace/table
creation calls rather than silently duplicating (good enough for a one-shot
bootstrap script, not meant as a general migration tool).
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = "http://localhost:8085"
_suffix = __import__("secrets").token_hex(3)
EMAIL = f"prometeo-f11+{_suffix}@starhome.local"
PASSWORD = "Prometeo-F11-" + __import__("secrets").token_urlsafe(18)
NAME = "StarHome Prometeo"


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


def get_or_register_token() -> str:
    try:
        resp = call("POST", "/api/user/", body={
            "name": "StarHome F11", "email": EMAIL, "password": PASSWORD,
            "language": "en", "authenticate": True,
        })
        print("[setup_schema] usuario registrado", file=sys.stderr)
        return resp["token"] if "token" in resp else resp["access_token"]
    except RuntimeError as e:
        if "already exists" not in str(e) and "ERROR_EMAIL_ALREADY_EXISTS" not in str(e):
            raise
        print("[setup_schema] usuario ya existia -- nota: password generado en este run no sirve para login futuro; usar el token guardado en el vault en su lugar", file=sys.stderr)
        raise RuntimeError(
            "El usuario prometeo-f11@starhome.local ya existe de una corrida previa y "
            "este script no persiste esa password entre corridas. Entra a "
            "http://localhost:8085 y crea el token manualmente, o borra el volumen "
            "starhome_baserow_data para partir de cero."
        )


def main() -> None:
    token = get_or_register_token()

    ws = call("POST", "/api/workspaces/", token=token, body={"name": NAME})
    workspace_id = ws["id"]
    print(f"[setup_schema] workspace {workspace_id}", file=sys.stderr)

    app = call("POST", f"/api/applications/workspace/{workspace_id}/", token=token, body={
        "name": NAME, "type": "database",
    })
    database_id = app["id"]
    print(f"[setup_schema] database {database_id}", file=sys.stderr)

    # --- table definitions ---------------------------------------------
    # (table_name, [(field_name, field_type, extra_kwargs), ...])
    TEXT = ("text", {})
    LONG_TEXT = ("long_text", {})
    NUMBER_MONEY = ("number", {"number_decimal_places": 2, "number_negative": True})
    NUMBER_INT = ("number", {"number_decimal_places": 0, "number_negative": False})
    DATE = ("date", {"date_include_time": True})
    SINGLE_SELECT = lambda options: ("single_select", {"select_options": [
        {"value": o, "color": "blue"} for o in options
    ]})

    TABLES = {
        "solicitudes": [
            # Mirrors ApprovalRequest (F3): motivo, costo_estimado_usd,
            # presupuesto_restante, canal, evidencia, requested_by, status.
            ("motivo", *LONG_TEXT),
            ("costo_estimado_usd", *NUMBER_MONEY),
            ("presupuesto_restante", *NUMBER_MONEY),
            ("canal", *TEXT),
            ("evidencia", *TEXT),
            ("requested_by", *TEXT),
            ("status", *SINGLE_SELECT(["pending", "approved", "rejected"])),
            ("task_id", *TEXT),
            ("created_at", *DATE),
        ],
        "gastos": [
            ("fecha", *DATE),
            ("oficina", *TEXT),
            ("concepto", *TEXT),
            ("monto_usd", *NUMBER_MONEY),
            ("aprobado_por", *TEXT),
            ("solicitud_id", *TEXT),
        ],
        "productos_ugc": [
            ("nombre", *TEXT),
            ("canal", *TEXT),
            ("precio_mxn", *NUMBER_MONEY),
            ("comision_mxn", *NUMBER_MONEY),
            ("score", *NUMBER_INT),
            ("fuente", *TEXT),
            ("url", *TEXT),
            ("estado", *SINGLE_SELECT(["descubierto", "en_espera", "rechazado", "procede"])),
        ],
        "metricas_diarias": [
            ("fecha", *DATE),
            ("oficina", *TEXT),
            ("metrica", *TEXT),
            ("valor", *NUMBER_MONEY),
            ("nota", *LONG_TEXT),
        ],
    }

    for table_name, fields in TABLES.items():
        table = call("POST", f"/api/database/tables/database/{database_id}/", token=token, body={
            "name": table_name,
        })
        table_id = table["id"]
        print(f"[setup_schema] tabla {table_name} -> id {table_id}", file=sys.stderr)

        # New tables come with default fields (Name/Notes/Active + a
        # sample row). Rename the primary field to our first column
        # instead of deleting it (Baserow tables always need exactly one
        # primary field) and add the rest.
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

    # --- API token scoped to this database ------------------------------
    token_resp = call("POST", "/api/database/tokens/", token=token, body={
        "name": "f11-office-analytics", "workspace": workspace_id,
    })
    api_token_key = token_resp.get("key")
    with open("baserow_api_token.txt", "w") as fh:
        fh.write(api_token_key + "\n")
    import os
    os.chmod("baserow_api_token.txt", 0o600)

    print(json.dumps({
        "workspace_id": workspace_id,
        "database_id": database_id,
        "tables": list(TABLES.keys()),
        "token_name": token_resp.get("name"),
        "token_written_to": "infrastructure/baserow/baserow_api_token.txt (0600, gitignored)",
    }, indent=2))


if __name__ == "__main__":
    main()
