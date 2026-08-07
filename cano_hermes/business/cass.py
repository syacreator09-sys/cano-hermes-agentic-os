"""K19 (plan HERMES-KICKOFF) -- `GET /api/dashboard/business/cass`: the
first real *business* view (as opposed to K14/K17/K18's *operational*
views), linking everything already connected about the CASS business into
one 100%-read-only page. Explicitly the template for Cano Digital and
LUZYA -- see the "REPLICATION TEMPLATE" section at the bottom of this
docstring; do not build those views yet (K19's mandate is CASS only),
just keep this module shaped so copying it is mechanical when Cano asks.

Five sources, three different honesty levels (documented here instead of
papered over):

  1. **Shopify** ("CASS Beauty Clinic", `fss1nv-s1.myshopify.com`) --
     connected via a Claude.ai MCP session (`mcp__claude_ai_Shopify__*`),
     structurally uncallable from this backend process (confirmed
     repeatedly: K11, K15, `docs/OPERATIONS.md`'s "MCP de Claude.ai"
     section). Never attempts an HTTP call to Shopify -- goes through
     `integrations.native_tool_bridge.request_job` instead, K15's
     `PENDING_NATIVE_TOOL` pattern, finally wired here (K15 only
     documented it and named this exact use case as the first consumer).
  2. **Meta/Facebook** ("CASS Medicina Estética") -- same case, same
     bridge. The connected Facebook MCP surface here is Ads/Marketing API
     (`ads_get_user_pages`, `ads_get_pages_for_business`, ...), not a
     generic Page-reader -- documented honestly in `META_JOB_PURPOSE`
     rather than assuming a tool that may not exist; a resolving session
     picks whatever real read tool is available at the time.
  3. **YouTube** (`cass-healt` channel) -- real, live network access.
     `integrations.youtube.channel_snapshot` refreshes the stored OAuth
     token (F12) and calls `channels.list(mine=true)`, both read-only
     (see that module's docstring for exactly which two endpoints it
     touches and why neither is a write). Confirmed live while building
     this module: "cass healt&beauty", @casshealtbeauty, 33 subs / 107
     videos / 19657 views (2026-08-06) -- real numbers, not a fixture.
  4. **Contenido** (K17's Baserow `contenido` table) -- reuses
     `orchestration.dashboards.content_dashboard` (already does the
     Baserow polling + factory-v5/ugc-discovered/upload_log joins) rather
     than re-fetching Baserow here, then filters its rows down to ones
     that mention "cass" in `canal`/`oficina_productora`. K17 left this
     table empty in production (confirmed live, 0 real rows) -- filtering
     an empty list is still an empty list, reported as
     `"vacio"`/`has_data: false`, never an error.
  5. **Contabilidad** (K18's Baserow `contabilidad` table) -- reuses
     `orchestration.dashboards.accounting_dashboard` the same way, then
     slices its `business_ledger` down to `negocio == "CASS"` -- "CASS" is
     already one of `finance.accounting.NEGOCIOS`'s four canonical
     values, so no new naming convention is introduced here; this is the
     first view to actually filter *by* it.

--------------------------------------------------------------------------
REPLICATION TEMPLATE -- how to build `business/cano_digital.py` or
`business/luzya.py` from this file:

  KEEP THE SAME (structure, not values):
    - the 5-source shape: Shopify/Meta as `PENDING_NATIVE_TOOL` jobs via
      `native_tool_bridge.request_job`, YouTube as a real
      `integrations.youtube.channel_snapshot` call, contenido/contabilidad
      as *filters over* `dashboards.content_dashboard`/
      `accounting_dashboard` (never re-fetch Baserow directly here).
    - the route/HTML pair in `api/app.py` (`GET /api/dashboard/
      business/<negocio>` + `/dashboard/business/<negocio>` HTML view),
      copied from `dashboard_business_cass`/`_business_cass_html` below.
    - the zero-write guarantee: no code path in the new module may issue
      an HTTP write (POST/PUT/PATCH/DELETE) to Shopify or Meta -- if that
      business has no Shopify/Meta at all, just omit those two sources
      rather than stub a fake job.

  CHANGE PER BUSINESS:
    - `NEGOCIO` -- must be one of `finance.accounting.NEGOCIOS`
      ("Cano Digital", "LUZYA" are already valid; a genuinely new negocio
      needs that frozenset extended first, or `accounting_dashboard`'s
      filter silently returns nothing).
    - `YOUTUBE_CHANNEL_SLUG` -- Cano Digital's real, F12-confirmed slug is
      `cano-digital-ia` (token file already on this host, same layout as
      `cass-healt`: `~/.secrets/credenciales/credenciales/youtube-tokens/
      cano-digital-ia/youtube_token.json`); LUZYA has no confirmed channel
      slug yet as of K19 -- check `youtube-tokens/INDEX.md` again before
      assuming one.
    - `CONTENT_KEYWORDS` -- the substring(s) K17's `contenido` rows would
      carry for that negocio's `canal`/`oficina_productora` (e.g.
      "cano-digital", "luzya") -- there is no guaranteed naming
      convention yet since the table is empty in production; pick
      something defensible and say so in the new module's docstring, same
      as this one does for "cass".
    - `SHOPIFY_STORE_DOMAIN`/`META_PAGE_NAME` -- or omit entirely if that
      business has no such connected store/page (do not invent one).
--------------------------------------------------------------------------
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from cano_hermes.finance import accounting
from cano_hermes.governance.budget import BudgetService
from cano_hermes.integrations import native_tool_bridge, youtube
from cano_hermes.orchestration import dashboards
from cano_hermes.storage.sqlite import SQLiteStore

NEGOCIO = "CASS"
assert NEGOCIO in accounting.NEGOCIOS  # keeps this module honest if NEGOCIOS ever changes

SHOPIFY_STORE_DOMAIN = "fss1nv-s1.myshopify.com"
SHOPIFY_STORE_NAME = "CASS Beauty Clinic"
META_PAGE_NAME = "CASS Medicina Estética"
YOUTUBE_CHANNEL_SLUG = "cass-healt"
CONTENT_KEYWORDS = ("cass",)

SHOPIFY_JOB_ID = "cass-shopify-status"
META_JOB_ID = "cass-meta-status"

SHOPIFY_JOB_PURPOSE = (
    f"Ventas y catálogo de la tienda Shopify '{SHOPIFY_STORE_NAME}' ({SHOPIFY_STORE_DOMAIN}) "
    "para GET /api/dashboard/business/cass (K19)."
)
META_JOB_PURPOSE = (
    f"Métricas básicas de la página Meta/Facebook '{META_PAGE_NAME}' para GET /api/dashboard/"
    "business/cass (K19). El MCP claude_ai_Facebook conectado hoy expone superficie de Ads/"
    "Marketing API (ads_get_user_pages, ads_get_pages_for_business, ...), no un lector genérico "
    "de Página -- una sesión resolviendo este job debe usar el tool de lectura más cercano "
    "disponible en ese momento, documentado aquí en vez de asumir uno que puede no existir."
)


def _mentions_business(value: str | None, keywords: tuple[str, ...] = CONTENT_KEYWORDS) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(keyword in lowered for keyword in keywords)


def shopify_status(*, jobs_dir: Path | None = None) -> dict[str, Any]:
    """Always `PENDING_NATIVE_TOOL`/`RESOLVED_NATIVE_TOOL` -- NEVER makes
    an HTTP call. See module docstring, source 1."""
    return native_tool_bridge.request_job(
        SHOPIFY_JOB_ID,
        mcp_tools=[
            "mcp__claude_ai_Shopify__get-shop-info",
            "mcp__claude_ai_Shopify__list-orders",
            "mcp__claude_ai_Shopify__search_products",
        ],
        params={"shop_domain": SHOPIFY_STORE_DOMAIN, "shop_name": SHOPIFY_STORE_NAME},
        purpose=SHOPIFY_JOB_PURPOSE,
        jobs_dir=jobs_dir,
    )


def meta_status(*, jobs_dir: Path | None = None) -> dict[str, Any]:
    """Always `PENDING_NATIVE_TOOL`/`RESOLVED_NATIVE_TOOL` -- NEVER makes
    an HTTP call. See module docstring, source 2."""
    return native_tool_bridge.request_job(
        META_JOB_ID,
        mcp_tools=[
            "mcp__claude_ai_Facebook__ads_get_user_pages",
            "mcp__claude_ai_Facebook__ads_get_pages_for_business",
        ],
        params={"page_name": META_PAGE_NAME},
        purpose=META_JOB_PURPOSE,
        jobs_dir=jobs_dir,
    )


def youtube_status(*, channel: str = YOUTUBE_CHANNEL_SLUG, token_path_override: Path | None = None) -> dict[str, Any]:
    """Real read-only YouTube channel snapshot, or an explicit
    sin_token/error status. See `integrations.youtube.channel_snapshot`."""
    return youtube.channel_snapshot(channel, token_path_override=token_path_override)


def content_status(store: SQLiteStore) -> dict[str, Any]:
    """Filters K17's already-aggregated `content_dashboard` down to rows
    whose `canal`/`oficina_productora` mention CASS. Never re-fetches
    Baserow directly (reuses `dashboards.content_dashboard`'s single
    fetch)."""
    full = dashboards.content_dashboard(store)
    baserow = full["baserow_contenido"]
    rows = [
        row for row in baserow["rows"]
        if _mentions_business(row.get("canal")) or _mentions_business(row.get("oficina_productora"))
    ]
    return {
        "status": baserow["status"],
        "detail": baserow.get("detail"),
        "rows": rows,
        "count": len(rows),
        "has_data": bool(rows),
        "note": (
            "tabla Baserow `contenido` (K17) filtrada por canal/oficina_productora que "
            f"mencionen {CONTENT_KEYWORDS} -- K17 la dejó en 0 filas reales en producción; "
            "vacía aquí no es un error, es el estado real hoy."
        ),
    }


def accounting_status(store: SQLiteStore, budget: BudgetService, *, business_rows: list[dict] | None = None) -> dict[str, Any]:
    """Filters K18's already-aggregated `accounting_dashboard` down to
    `negocio == "CASS"`. Never re-fetches Baserow directly (reuses
    `dashboards.accounting_dashboard`'s single fetch)."""
    full = dashboards.accounting_dashboard(store, budget, business_rows=business_rows)
    business_ledger = full["business_ledger"]
    cash_position = business_ledger["cash_position"]["by_negocio"].get(NEGOCIO)
    movements = [row for row in business_ledger["by_negocio_and_month"] if row["negocio"] == NEGOCIO]
    return {
        "status": business_ledger["baserow_status"],
        "detail": business_ledger["baserow_detail"],
        "cash_position": cash_position,
        "movements_by_month": movements,
        "has_data": cash_position is not None,
    }


def cass_dashboard(
    store: SQLiteStore, budget: BudgetService, *,
    jobs_dir: Path | None = None, youtube_token_path_override: Path | None = None,
    accounting_business_rows: list[dict] | None = None,
) -> dict[str, Any]:
    """`GET /api/dashboard/business/cass`'s data (K19): all 5 sources,
    every one degrading to an explicit status instead of raising --
    exactly the "a GET against this module is never the cause of a 500"
    contract every other dashboard function in this codebase already
    follows (see `orchestration.dashboards`'s own module docstring)."""
    generated_at = dt.datetime.now(dt.UTC)

    return {
        "generated_at": generated_at.isoformat(),
        "negocio": NEGOCIO,
        "shopify": shopify_status(jobs_dir=jobs_dir),
        "meta": meta_status(jobs_dir=jobs_dir),
        "youtube": youtube_status(token_path_override=youtube_token_path_override),
        "content": content_status(store),
        "accounting": accounting_status(store, budget, business_rows=accounting_business_rows),
    }
