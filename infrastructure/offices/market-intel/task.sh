#!/usr/bin/env bash
# office-market-intel step 1 (K9) -- first real (non-design-only) cycle of
# the 5th office designed in docs/MARKET_INTEL_OFFICE_DESIGN.md (Prometeo
# F14). Reads three read-only, already-real signals and writes one
# synthesis -- it never trades, never buys, never publishes, never calls a
# BrokerPort (hard rule, see design doc sec. 0/4/5).
#
# CERO trading real, CERO compra real, CERO credencial de broker: this
# container's environment never carries ALPACA_*/IBKR_*/BINANCE_* or any
# UPLOAD_POST_*/TIKTOK_*/META_* var -- verify with `docker compose config`.
#
# Sources (all mounted :ro):
#   - amazon-fba-product-hunter/reports/*.md -- real, static FBA scoring
#     reports already on disk (scorer_agent.py's own output, not re-run
#     here: this office reads results, it does not re-score).
#   - cano-investment-intelligence/docs/reports/*.md -- latest audit/status
#     doc (the live council API is NOT started from this office -- F14
#     documented that investment-intelligence's own compose has no
#     mem_limit/cpus/profiles yet, so it stays deferred; see design doc
#     sec. 6 "Hallazgo F14").
#   - office-ugc's own trend signal is out of scope for this container (it
#     already lives in office-ugc, per design doc sec. 1); no duplicate
#     read here.
#
# Output: a synthesis to /office/output, analogous to what a future
# reports/daily/market-intel-daily-<date>.md would contain -- written
# locally only. Writing to Baserow's `productos_ugc` table (design doc
# sec. 2, rule 1) needs a BASEROW_API_TOKEN this office is not yet
# allowlisted for -- left as a documented gate, not faked.
set -uo pipefail

FBA_REPO="/home/cano/repos/amazon-fba-product-hunter"
INVEST_REPO="/home/cano/repos/cano-investment-intelligence"
OUT="/office/output/market-intel-daily-$(date +%s).md"

echo "== office-market-intel: read-only synthesis (no trading, no buying, no BrokerPort) =="

{
  echo "# market-intel-daily (office-market-intel, K9 real run)"
  echo "generated_at: $(date -u +%FT%TZ)"
  echo
  echo "## Señal 1: producto físico (amazon-fba-product-hunter, solo lectura)"
  if [ -d "$FBA_REPO/reports" ]; then
      LATEST_FBA_REPORT="$(ls -t "$FBA_REPO"/reports/*.md 2>/dev/null | head -1)"
      if [ -n "${LATEST_FBA_REPORT:-}" ]; then
          echo "fuente: ${LATEST_FBA_REPORT}"
          grep -E '^\| (APROBAD|DESCARTAD|PENDIENTE)' "$LATEST_FBA_REPORT" 2>/dev/null || echo "(sin tabla resumen reconocible en el reporte)"
      else
          echo "no hay reportes en ${FBA_REPO}/reports -- nada que sintetizar."
      fi
  else
      echo "amazon-fba-product-hunter no montado en este contenedor."
  fi

  echo
  echo "## Señal 2: inteligencia financiera (cano-investment-intelligence, solo lectura, council OFFLINE -- no se levanta el servicio aquí)"
  if [ -d "$INVEST_REPO/docs/reports" ]; then
      LATEST_INVEST_DOC="$(ls -t "$INVEST_REPO"/docs/reports/*.md 2>/dev/null | head -1)"
      if [ -n "${LATEST_INVEST_DOC:-}" ]; then
          echo "fuente: ${LATEST_INVEST_DOC}"
          head -5 "$LATEST_INVEST_DOC"
      else
          echo "no hay docs/reports en ${INVEST_REPO} -- nada que sintetizar."
      fi
  else
      echo "cano-investment-intelligence no montado en este contenedor."
  fi

  echo
  echo "## Señal 3: tendencia/contenido (office-ugc)"
  echo "fuera de alcance de este contenedor -- ya vive en office-ugc (RAPIDAPI_KEY/APIFY_API_KEY), sin duplicar aquí (design doc sec. 1)."

  echo
  echo "## Cruce (regla 1 del diseño): fba_score >= 70 + tendencia activa -> candidato a Baserow productos_ugc"
  echo "NO ejecutado en este ciclo: requiere BASEROW_API_TOKEN, no allowlisted todavía para esta oficina (gate documentado, no simulado)."
  echo
  echo "## Regla dura"
  echo "Esta oficina NUNCA coloca órdenes, ejecuta trades, compra inventario ni publica. Ningún BrokerPort ni credencial equivalente existe en este contenedor."
} | tee "$OUT"

echo
echo "office-market-intel: synthesis written to ${OUT}"
exit 0
