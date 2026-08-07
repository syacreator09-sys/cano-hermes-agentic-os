#!/usr/bin/env python3
"""K17 (plan HERMES-KICKOFF) -- one-shot Baserow bootstrap for the
`contenido` table (content control matrix).

Modeled directly on `setup_schema.py` (F11), same stdlib-only /
register-then-JWT approach, for one reason: F11's own database-scoped
token (`BASEROW_TOKEN`, workspace 29 / database 34 "StarHome Prometeo")
only has REST *row* access (`/api/database/rows/...`), never the
management API (`/api/database/tables/...`, `/api/database/fields/...`)
that table/field creation requires -- confirmed live: `GET
/api/database/tables/database/34/` with `Authorization: Token
<BASEROW_TOKEN>` returns 401 "Authentication credentials were not
provided" (database tokens are Token-auth only, management endpoints are
JWT-only). And the F11 setup user's password was never persisted anywhere
(setup_schema.py's own docstring says so) and this repo does not spend
effort resetting it via Django-internals in the Baserow container, which
would be resetting infra invisible to the API this repo depends on --
registering a second dedicated user and giving it its OWN workspace is
the same "good enough for a one-shot bootstrap" tradeoff F11 already
accepted, not a new pattern.

So `contenido` lives in a separate workspace/database ("StarHome K17
Content") from `solicitudes`/`gastos`/`productos_ugc`/`metricas_diarias`,
with its OWN database-scoped token -- `cano_hermes/content/dedup.py` reads
that token under a different vault key (`BASEROW_CONTENT_TOKEN`) than
`monitoring.py`'s `BASEROW_TOKEN`. Confirmed live that this is harmless:
Baserow tokens are scoped per-workspace, so this doesn't touch or
widen access to the F11 tables at all.

Writes the new token straight into the vault .env
(~/.secrets/credenciales/credenciales/.env) as BASEROW_CONTENT_TOKEN=...
-- never printed to stdout/stderr -- because this whole run is
unsupervised (no human in the loop to move a file into place, unlike
F11's original "print the id, caller moves the token by hand" flow).
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
EMAIL = f"starhome-k17+{_suffix}@starhome.local"
PASSWORD = "StarHome-K17-" + __import__("secrets").token_urlsafe(18)
NAME = "StarHome K17 Content"
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
        "name": "StarHome K17", "email": EMAIL, "password": PASSWORD,
        "language": "en", "authenticate": True,
    })
    print(f"[setup_content_table] usuario registrado ({EMAIL})", file=sys.stderr)
    return resp["token"] if "token" in resp else resp["access_token"]


def main() -> None:
    token = register()

    ws = call("POST", "/api/workspaces/", token=token, body={"name": NAME})
    workspace_id = ws["id"]
    print(f"[setup_content_table] workspace {workspace_id}", file=sys.stderr)

    app = call("POST", f"/api/applications/workspace/{workspace_id}/", token=token, body={
        "name": NAME, "type": "database",
    })
    database_id = app["id"]
    print(f"[setup_content_table] database {database_id}", file=sys.stderr)

    # K17 mandate's exact column list: canal, oficina productora, estado
    # (idea->brief->producido->draft->aprobado->publicado), video_id (real,
    # required only when estado=publicado -- enforced in
    # cano_hermes/content/dedup.py, NOT here: Baserow single_select/text
    # fields have no cross-field conditional-required constraint, so the
    # hard rule lives in the one place that already validates before
    # writing), costo, link_artifact, fecha, dedup_key.
    fields = [
        ("canal", "text", {}),
        ("oficina_productora", "text", {}),
        ("estado", "single_select", {"select_options": [
            {"value": v, "color": c} for v, c in [
                ("idea", "light-gray"), ("brief", "light-blue"),
                ("producido", "blue"), ("draft", "orange"),
                ("aprobado", "yellow"), ("publicado", "green"),
            ]
        ]}),
        ("video_id", "text", {}),
        ("costo_usd", "number", {"number_decimal_places": 4, "number_negative": False}),
        ("link_artifact", "text", {}),
        ("fecha", "date", {"date_include_time": True}),
        ("dedup_key", "text", {}),
    ]

    table = call("POST", f"/api/database/tables/database/{database_id}/", token=token, body={
        "name": "contenido",
    })
    table_id = table["id"]
    print(f"[setup_content_table] tabla contenido -> id {table_id}", file=sys.stderr)

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
        "name": "k17-content-matrix", "workspace": workspace_id,
    })
    api_token_key = token_resp.get("key")

    with open("baserow_content_api_token.txt", "w") as fh:
        fh.write(api_token_key + "\n")
    os.chmod("baserow_content_api_token.txt", 0o600)

    # Unsupervised run (no human to move the token into the vault by hand,
    # unlike F11's original flow) -- append straight to the vault .env
    # every other Baserow credential in this repo already reads from
    # (monitoring.VAULT_ENV_PATH). Never printed.
    if VAULT_ENV_PATH.exists():
        existing = VAULT_ENV_PATH.read_text(encoding="utf-8")
        if "BASEROW_CONTENT_TOKEN=" not in existing:
            with open(VAULT_ENV_PATH, "a", encoding="utf-8") as fh:
                if not existing.endswith("\n"):
                    fh.write("\n")
                fh.write(
                    "# K17 (plan HERMES-KICKOFF) -- token de la API DB de Baserow self-hosted "
                    f"local (localhost:8085), workspace/database \"StarHome K17 Content\" "
                    f"(id {workspace_id}/{database_id}), tabla contenido (id {table_id}). "
                    "Generado por infrastructure/baserow/setup_content_table.py.\n"
                )
                fh.write(f"BASEROW_CONTENT_TOKEN={api_token_key}\n")
            print("[setup_content_table] BASEROW_CONTENT_TOKEN escrito en el vault", file=sys.stderr)
        else:
            print("[setup_content_table] BASEROW_CONTENT_TOKEN ya existia en el vault -- no sobreescrito", file=sys.stderr)

    print(json.dumps({
        "workspace_id": workspace_id,
        "database_id": database_id,
        "table_id": table_id,
        "table_name": "contenido",
        "token_name": token_resp.get("name"),
        "token_written_to": [
            "infrastructure/baserow/baserow_content_api_token.txt (0600, gitignored)",
            "~/.secrets/credenciales/credenciales/.env (BASEROW_CONTENT_TOKEN)",
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
