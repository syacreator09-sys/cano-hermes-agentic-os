# fba-hunter launcher — notas (F7)

**Generado:** 2026-08-05 · **Fuente:** `~/repos/cano-ai-command-center/CLAUDE-CODE-LAUNCHERS/fba-hunter/` (repo externo, **solo lectura**, nunca se edita) — archivos leídos: `README.md`, `START.md`, `CLAUDE.md`, índice de `knowledge/` (14-21 archivos según versión).

## Qué es (y qué NO es)

El launcher `fba-hunter` de command-center **no es un motor**, es un paquete
de prompts/knowledge-base para que un agente Claude Code actúe como
"analista senior de productos Amazon FBA". Trae:

- `CLAUDE.md` — rol del agente + estado del sistema + comandos.
- `START.md` — guía de arranque en 1 minuto.
- `README.md` — índice de la knowledge base.
- `knowledge/*.md` (14-21 archivos) — metodología, reglas de producto, fees
  FBA, marcas seguras/restringidas, proveedores, legal, buy box, reverse
  sourcing, riesgo de mercado gris, etc.

**No trae código ejecutable propio.** Todos sus comandos apuntan a un
proyecto Python completo en una ruta separada:

```
D:\cano-ai-command-center\03-projects\amazon-fba-product-hunter\
```

(ruta Windows original del propio launcher; en esta máquina Linux esa ruta
no existe dentro de command-center).

## Cómo se invoca (según el launcher)

```bash
python -X utf8 scripts/scan_supplier.py --supplier contarmarket --category shave --limit 20
python -X utf8 scripts/analyze_product.py --supplier-url "<url>" --amazon-price 19.99
python -X utf8 scripts/reverse_scan.py --category shave --limit 15
streamlit run dashboard/app.py   # → http://localhost:8501
```

8 agentes internos declarados en el `CLAUDE.md` del launcher:
`FBACalculatorAgent`, `ProfitEngineAgent`, `ScorerAgent`, `RiskFilterAgent`,
`PriceValidatorAgent`, `BuyBoxAnalysisAgent`, `GreyMarketDetector`,
`OrchestratorAgent`. Collectors: ContarMarket (JSON público, sin login),
Wholesale Ninjas (Shopify), gstack browse (Amazon USA con cookies USD),
ReverseSourcingAgent.

Reglas de producto documentadas (2026): precio mínimo Amazon $15 USD, ventas
≥300/mes, BSR <50,000, reviews de competidores <400, multiplicador
precio/costo ≥2.5x, margen neto objetivo 25%+, descarte duro <12% margen,
Amazon como seller = descarte automático, marcas P&G (Gillette) = descarte
automático.

## Relación con `amazon-fba-product-hunter` (repo propio, F14)

**No confundir los dos.** Son cosas distintas:

| | `CLAUDE-CODE-LAUNCHERS/fba-hunter/` (este doc) | `~/repos/amazon-fba-product-hunter` |
|---|---|---|
| Qué es | Launcher ligero: prompts + knowledge base, sin código propio | Repo completo, propio, editable, con código real |
| Dónde vive | Dentro de command-center (solo lectura) | `~/repos/` (ya clonado, propio) |
| Contenido | `CLAUDE.md`, `START.md`, `README.md`, `knowledge/*.md` | `src/`, `scripts/`, `dashboard/`, `tests/`, `docker-compose.yml`, `.env.example`, `requirements.txt`, `knowledge/` (14 archivos, casi idéntico al del launcher) |
| Estado verificado | N/A (es solo documentación) | Auditado 2026-05-21 en su propio `CLAUDE.md`: "19/19 agentes OK, 7/7 tests pasando" (estado histórico documentado en el propio repo, no re-verificado en esta fase) |
| Quién lo maneja | Nadie todavía — es referencia | **F14** (`office-market-intel`) — no tocar en F7 |

El launcher de command-center parece ser una versión anterior/espejo de la
knowledge base que hoy vive completa (con código) en el repo propio. La
tabla `SYSTEMS_MATRIX_HERMES.md` de command-center (`.command-center/
hermes-remote/SYSTEMS_MATRIX_HERMES.md`, sección 1) confirma esta relación:
lista `fba-hunter` launcher como "research Amazon (solo investigación, sin
comisión)" con conexión "según su propio README" y portabilidad "Portable",
separado de la fila `amazon-fba-product-hunter` ("Hunter Amazon FBA
completo", cuenta propia, repo aparte).

## Para F14

Cuando F14 construya `office-market-intel`, el trabajo real debe apoyarse en
`~/repos/amazon-fba-product-hunter` (código, tests, dashboard reales), no en
el launcher de command-center. El launcher puede servir como prompt/rol de
referencia rápida si se quiere replicar el mismo tono de "analista senior",
pero no aporta capacidad que el repo completo no tenga ya.

## Nota de precios/margen (advertencia del propio launcher)

El propio `README.md` del launcher marca una advertencia sin resolver: un
resultado "APROBADO" (BIC Comfort 3, 4ct) usó un precio Amazon de $28.80 que
el mismo documento señala como probablemente incorrecto (~$7.99 real para un
4-pack), lo que cambiaría el resultado a DESCARTADO. Es una advertencia
documentada en la fuente, no un hallazgo nuevo de esta fase — se preserva
aquí porque cualquier fase futura que reuse estos datos de ejemplo debe
tratarlos como no verificados.
