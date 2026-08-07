"""Plan POTENCIA P4-D -- clasificador ESCALAR/MANTENER/MATAR real por
canal, orientado a monetización (watch time de 28 días, la señal que
YouTube Partner Program realmente exige -- 4000 horas/12 meses).

Verificado en vivo contra Baserow real: hoy solo hay 1 día de historia
(P4-A escribió por primera vez hoy), así que los 8 canales reales
reportan honestamente "sin_datos_suficientes" -- correcto, no un bug.
Este archivo prueba la lógica de clasificación en sí con historia
simulada (nunca la Baserow real, `monitoring.fetch_metric_rows` siempre
mockeado)."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from cano_hermes.orchestration import dashboards


def _row(oficina: str, metrica: str, valor: float, fecha: str) -> dict:
    return {"oficina": oficina, "metrica": metrica, "valor": valor, "fecha": fecha}


class WatchTimeTrendParsingTests(unittest.TestCase):
    def test_extracts_only_watch_min_28d_metric(self):
        rows = [
            _row("canal-a", "yt_watch_min_28d", 100.0, "2026-08-01"),
            _row("canal-a", "yt_views_28d", 5000.0, "2026-08-01"),  # otra metrica, ignorada
        ]
        trend = dashboards._watch_time_trend_by_channel(rows)
        self.assertEqual(trend["canal-a"], [("2026-08-01", 100.0)])

    def test_sorts_by_date(self):
        rows = [
            _row("canal-a", "yt_watch_min_28d", 200.0, "2026-08-03"),
            _row("canal-a", "yt_watch_min_28d", 100.0, "2026-08-01"),
            _row("canal-a", "yt_watch_min_28d", 150.0, "2026-08-02"),
        ]
        trend = dashboards._watch_time_trend_by_channel(rows)
        self.assertEqual([p[0] for p in trend["canal-a"]], ["2026-08-01", "2026-08-02", "2026-08-03"])


class ClassificationTests(unittest.TestCase):
    def _rows_for(self, canal: str, values_by_day: list[tuple[str, float]]) -> list[dict]:
        return [_row(canal, "yt_watch_min_28d", v, d) for d, v in values_by_day]

    def _classify(self, rows: list[dict], *, min_days: int = 7) -> dict:
        with patch("cano_hermes.orchestration.dashboards.monitoring.fetch_metric_rows", return_value={"status": "ok", "rows": rows}):
            return dashboards.channel_performance_classification(min_days=min_days)

    def test_insufficient_history_is_honest_not_fabricated(self):
        rows = self._rows_for("canal-a", [("2026-08-01", 100.0), ("2026-08-02", 110.0)])
        result = self._classify(rows)
        self.assertEqual(result["channels"]["canal-a"]["classification"], "sin_datos_suficientes")
        self.assertEqual(result["channels"]["canal-a"]["distinct_days"], 2)

    def test_growing_watch_time_classifies_escalar(self):
        days = [(f"2026-08-{d:02d}", 100.0 + d * 20) for d in range(1, 8)]  # +140% en 7 dias
        result = self._classify(self._rows_for("canal-a", days))
        self.assertEqual(result["channels"]["canal-a"]["classification"], "ESCALAR")

    def test_declining_watch_time_classifies_matar(self):
        days = [(f"2026-08-{d:02d}", 200.0 - d * 20) for d in range(1, 8)]  # baja fuerte
        result = self._classify(self._rows_for("canal-a", days))
        self.assertEqual(result["channels"]["canal-a"]["classification"], "MATAR")

    def test_flat_watch_time_classifies_mantener(self):
        days = [(f"2026-08-{d:02d}", 100.0 + (d % 2)) for d in range(1, 8)]  # ruido minimo
        result = self._classify(self._rows_for("canal-a", days))
        self.assertEqual(result["channels"]["canal-a"]["classification"], "MANTENER")

    def test_multiple_channels_classified_independently(self):
        rows = (
            self._rows_for("canal-escala", [(f"2026-08-{d:02d}", 100.0 + d * 30) for d in range(1, 8)])
            + self._rows_for("canal-nuevo", [("2026-08-01", 50.0)])
        )
        result = self._classify(rows)
        self.assertEqual(result["channels"]["canal-escala"]["classification"], "ESCALAR")
        self.assertEqual(result["channels"]["canal-nuevo"]["classification"], "sin_datos_suficientes")

    def test_no_token_degrades_honestly(self):
        with patch("cano_hermes.orchestration.dashboards.monitoring.fetch_metric_rows", return_value={"status": "sin_token", "detail": "x"}):
            result = dashboards.channel_performance_classification()
        self.assertEqual(result["status"], "sin_token")
        self.assertEqual(result["channels"], {})


if __name__ == "__main__":
    unittest.main()
