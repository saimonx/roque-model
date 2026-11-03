"""Generate the two Grafana dashboards (Spanish and English) from one definition.

Grafana cannot translate a dashboard, so we keep ONE list of panels with the
texts in both languages and write two JSON files that Grafana loads at start
(infra/grafana/provisioning/dashboards/dashboards.yml). Editing a panel here
and re-running this script keeps both languages identical.

The panels read CrateDB, where QuantumLeap stores every change of the FIWARE
entities (see fiware.py): table `etweatherobserved` for the two weather
stations and `etweatherforecast` for our night forecast.

Usage:
    .venv/bin/python -m roque_forecast.dashboards
"""

import json

from roque_forecast import config
from roque_forecast.fiware import FORECAST_ID, NOT_ID

OUT_DIR = config.PROJECT_DIR / "infra" / "grafana" / "dashboards"
DATASOURCE = {"type": "grafana-postgresql-datasource", "uid": "cratedb"}
OBSERVED = "doc.etweatherobserved"
FORECAST = "doc.etweatherforecast"

# Same colours as the figures and the web page (colour-blind-safe palette, fixed order).
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GOOD, WARNING, CRITICAL = "#0ca30c", "#fab219", "#d03b3b"

TEXT = {
    "title": {"es": "RoqueModel — meteo y pronóstico de la noche",
              "en": "RoqueModel — weather and night forecast"},
    "about": {
        "es": "**Proyecto independiente, no afiliado a GRANTECAN ni a ningún observatorio.** Datos reales y públicos: "
              "estación meteorológica del NOT, pronóstico ECMWF IFS (Open-Meteo, CC BY 4.0). "
              "Pronóstico de la noche: dos modelos propios, cúpula cerrada hora a hora y seeing (ver el README). "
              "Flujo: NGSI-v2 → Orion → QuantumLeap → CrateDB → Grafana.",
        "en": "**Independent project, not affiliated with GRANTECAN or any observatory.** Real, public data: "
              "NOT weather station, ECMWF IFS forecast (Open-Meteo, CC BY 4.0). "
              "Night forecast: two models of our own, dome closed hour by hour and seeing (see the README). "
              "Flow: NGSI-v2 → Orion → QuantumLeap → CrateDB → Grafana.",
    },
    "closure": {"es": "Horas de cúpula cerrada previstas", "en": "Expected hours with the dome closed"},
    "seeing": {"es": "Seeing previsto", "en": "Forecast seeing"},
    "lost": {"es": "Horas observables previstas", "en": "Expected observable hours"},
    "mode": {"es": "Tipo de pronóstico", "en": "Forecast type"},
    "rh_now": {"es": "Humedad NOT ahora", "en": "NOT humidity now"},
    "wind_now": {"es": "Viento NOT ahora", "en": "NOT wind now"},
    "humidity": {"es": "Humedad relativa (%) — la cúpula se cierra al 90 %",
                 "en": "Relative humidity (%) — the dome closes at 90 %"},
    "wind": {"es": "Viento (m/s)", "en": "Wind (m/s)"},
    "temp": {"es": "Temperatura (°C, NOT)", "en": "Temperature (°C, NOT)"},
    "fc_history": {"es": "Pronósticos emitidos: horas de cúpula cerrada",
                   "en": "Issued forecasts: hours with the dome closed"},
    "seeing_history": {"es": "Pronósticos emitidos: seeing (″)", "en": "Issued forecasts: seeing (″)"},
    "not_wind": {"es": "NOT", "en": "NOT"},
    "temperature": {"es": "temperatura", "en": "temperature"},
    "provisional": {"es": "provisional (solo pronóstico)", "en": "provisional (forecast only)"},
    "final": {"es": "definitivo (con la estación)", "en": "final (with the station)"},
}


def latest(column: str, table: str, entity_id: str) -> str:
    return (f"SELECT {column} AS value FROM {table} WHERE entity_id = '{entity_id}' "
            f"AND {column} IS NOT NULL ORDER BY time_index DESC LIMIT 1")


def series(column: str, name: str, table: str, entity_id: str) -> str:
    return (f"SELECT time_index AS \"time\", {column} AS \"{name}\" FROM {table} "
            f"WHERE entity_id = '{entity_id}' AND $__timeFilter(time_index) AND {column} IS NOT NULL ORDER BY 1")


def target(sql: str, ref: str = "A", fmt: str = "table") -> dict:
    return {"refId": ref, "datasource": DATASOURCE, "format": fmt, "rawQuery": True, "editorMode": "code",
            "rawSql": sql}


def steps(*pairs) -> dict:
    """Threshold steps: (colour, from-value) pairs; the first applies from minus infinity."""
    return {"mode": "absolute", "steps": [{"color": c, "value": v} for c, v in pairs]}


def stat(pid: int, title: str, sql: str, x: int, unit: str, thresholds: dict, decimals: int = 1,
         mappings: list | None = None) -> dict:
    return {
        "id": pid, "type": "stat", "title": title, "datasource": DATASOURCE,
        "gridPos": {"x": x, "y": 3, "w": 4, "h": 5},
        "targets": [target(sql)],
        "fieldConfig": {"defaults": {"unit": unit, "decimals": decimals, "thresholds": thresholds,
                                     "color": {"mode": "thresholds"}, "mappings": mappings or []},
                        "overrides": []},
        "options": {"colorMode": "background", "graphMode": "none", "textMode": "value",
                    # "/.*/" also shows text values (the forecast type), not only numbers
                    "reduceOptions": {"calcs": ["lastNotNull"], "fields": "/.*/", "values": False}},
    }


def timeseries(pid: int, title: str, sqls: list[tuple[str, str]], grid: dict, unit: str,
               threshold: float | None = None, points: bool = False) -> dict:
    """Line chart; `sqls` = [(sql, colour)]. An optional dashed threshold line (e.g. 90 % humidity)."""
    overrides = [{"matcher": {"id": "byFrameRefID", "options": chr(65 + i)},
                  "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": colour}}]}
                 for i, (_, colour) in enumerate(sqls)]
    # insertNulls: break the line where data are missing for > 30 min instead of drawing across the gap.
    custom = {"lineWidth": 2, "fillOpacity": 0, "showPoints": "always" if points else "never", "pointSize": 8,
              "insertNulls": 1800000, "spanNulls": False}
    defaults = {"unit": unit, "custom": custom}
    if threshold is not None:
        custom["thresholdsStyle"] = {"mode": "dashed"}
        defaults["thresholds"] = steps(("transparent", None), (CRITICAL, threshold))
    return {
        "id": pid, "type": "timeseries", "title": title, "datasource": DATASOURCE, "gridPos": grid,
        "targets": [target(sql, chr(65 + i), "time_series") for i, (sql, _) in enumerate(sqls)],
        "fieldConfig": {"defaults": defaults, "overrides": overrides},
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}, "tooltip": {"mode": "multi"}},
    }


def dashboard(lang: str) -> dict:
    t = {k: v[lang] for k, v in TEXT.items()}
    mode_map = [{"type": "value", "options": {
        "provisional": {"text": t["provisional"], "color": WARNING},
        "final": {"text": t["final"], "color": GOOD}}}]
    panels = [
        {"id": 1, "type": "text", "title": "", "gridPos": {"x": 0, "y": 0, "w": 24, "h": 3},
         "options": {"mode": "markdown", "content": t["about"]}},
        stat(2, t["closure"], latest("domeclosedhours", FORECAST, FORECAST_ID), 0, "h",
             steps((GOOD, None), (WARNING, 1), (CRITICAL, 4)), 1),
        stat(3, t["seeing"], latest("seeingforecast", FORECAST, FORECAST_ID), 4, "none",
             steps((GOOD, None), (WARNING, 0.9), (CRITICAL, 1.2)), 2),
        stat(4, t["lost"], latest("openhoursforecast", FORECAST, FORECAST_ID), 8, "h",
             steps((CRITICAL, None), (WARNING, 4), (GOOD, 7)), 1),
        stat(5, t["mode"], latest("forecastmode", FORECAST, FORECAST_ID), 12, "none",
             steps((BLUE, None)), 0, mode_map),
        stat(6, t["rh_now"], latest("relativehumidity * 100", OBSERVED, NOT_ID), 16, "percent",
             steps((GOOD, None), (WARNING, 80), (CRITICAL, 90)), 0),
        # Gusts of 22.2 m/s (80 km/h) close the dome.
        stat(7, t["wind_now"], latest("windspeed", OBSERVED, NOT_ID), 20, "velocityms",
             steps((GOOD, None), (WARNING, 15), (CRITICAL, 22.2)), 1),
        timeseries(8, t["humidity"], [
            (series("relativehumidity * 100", "NOT", OBSERVED, NOT_ID), ORANGE),
        ], {"x": 0, "y": 8, "w": 24, "h": 8}, "percent", threshold=90),
        timeseries(9, t["wind"], [
            (series("windspeed", t["not_wind"], OBSERVED, NOT_ID), ORANGE),
        ], {"x": 0, "y": 16, "w": 12, "h": 8}, "velocityms"),
        timeseries(10, t["temp"], [
            (series("temperature", t["temperature"], OBSERVED, NOT_ID), ORANGE),
        ], {"x": 12, "y": 16, "w": 12, "h": 8}, "celsius"),
        timeseries(11, t["fc_history"], [
            (series("domeclosedhours", "h", FORECAST, FORECAST_ID), BLUE),
        ], {"x": 0, "y": 24, "w": 12, "h": 7}, "h", points=True),
        timeseries(12, t["seeing_history"], [
            (series("seeingforecast", "seeing", FORECAST, FORECAST_ID), BLUE),
        ], {"x": 12, "y": 24, "w": 12, "h": 7}, "none", points=True),
    ]
    return {
        "uid": f"roque-night-{lang}", "title": t["title"], "tags": ["roque", "fiware", lang],
        "timezone": "utc", "refresh": "5m", "schemaVersion": 39, "editable": False,
        "time": {"from": "now-7d", "to": "now"}, "panels": panels,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for lang in ("es", "en"):
        path = OUT_DIR / f"roque-night-{lang}.json"
        path.write_text(json.dumps(dashboard(lang), indent=1, ensure_ascii=False), encoding="utf-8")
        print("written", path.relative_to(config.PROJECT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
