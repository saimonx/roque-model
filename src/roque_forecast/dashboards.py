"""Generate the local Grafana dashboard (Spanish, like the web page) for the FIWARE stack.

Grafana loads the JSON file at start (infra/grafana/provisioning/dashboards/dashboards.yml);
edit the panels here and re-run this script instead of editing the JSON.

The panels read CrateDB, where QuantumLeap stores every change of the FIWARE entities
(see fiware.py): table `etweatherobserved` for the NOT weather station (the GTC station
is not stored) and `etweatherforecast` for RoqueModel's night forecast.

Usage:
    .venv/bin/python -m roque_forecast.dashboards
"""

import json

from roque_forecast import config
from roque_forecast.fiware import FORECAST_ID, NOT_ID

OUT_DIR = config.PROJECT_DIR / "infra" / "grafana" / "dashboards"
DASHBOARD_FILE = OUT_DIR / "roquemodel.json"
DATASOURCE = {"type": "grafana-postgresql-datasource", "uid": "cratedb"}
OBSERVED = "doc.etweatherobserved"
FORECAST = "doc.etweatherforecast"

# Same colours as the figures and the web page (colour-blind-safe palette, fixed order).
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GOOD, WARNING, CRITICAL = "#0ca30c", "#fab219", "#d03b3b"

TEXT = {
    "title": "RoqueModel — meteo y pronóstico de la noche",
    "about": ("**Proyecto independiente, no afiliado a GRANTECAN ni a ningún observatorio.** Datos reales y públicos: "
              "estación meteorológica del NOT y previsiones ECMWF y NOAA GFS (Open-Meteo, CC BY 4.0). "
              "Pronóstico de la noche: RoqueModel (cúpula cerrada hora a hora) y el seeing previsto "
              "(ver docs/DETALLES_TECNICOS.md). Flujo: NGSI-v2 → Orion → QuantumLeap → CrateDB → Grafana."),
    "closure": "Horas de cúpula cerrada previstas",
    "seeing": "Seeing previsto",
    "lost": "Horas observables previstas",
    "mode": "Tipo de pronóstico",
    "rh_now": "Humedad NOT ahora",
    "wind_now": "Viento NOT ahora",
    "humidity": "Humedad relativa (%) — la cúpula se cierra al 90 %",
    "wind": "Viento (km/h) — la cúpula se cierra a 80 km/h",
    "temp": "Temperatura (°C, NOT)",
    "fc_history": "Pronósticos emitidos: horas de cúpula cerrada",
    "seeing_history": "Pronósticos emitidos: seeing (″)",
    "provisional": "provisional (solo pronóstico)",
    "final": "definitivo (con la estación)",
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


def dashboard() -> dict:
    t = TEXT
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
        # Wind is stored in m/s (the FIWARE data model); shown in km/h like the web page.
        # 80 km/h (22.2 m/s) closes the dome.
        stat(7, t["wind_now"], latest("windspeed * 3.6", OBSERVED, NOT_ID), 20, "velocitykmh",
             steps((GOOD, None), (WARNING, 54), (CRITICAL, 80)), 0),
        timeseries(8, t["humidity"], [
            (series("relativehumidity * 100", "NOT", OBSERVED, NOT_ID), ORANGE),
        ], {"x": 0, "y": 8, "w": 24, "h": 8}, "percent", threshold=90),
        timeseries(9, t["wind"], [
            (series("windspeed * 3.6", "NOT", OBSERVED, NOT_ID), ORANGE),
        ], {"x": 0, "y": 16, "w": 12, "h": 8}, "velocitykmh", threshold=80),
        timeseries(10, t["temp"], [
            (series("temperature", "temperatura", OBSERVED, NOT_ID), ORANGE),
        ], {"x": 12, "y": 16, "w": 12, "h": 8}, "celsius"),
        timeseries(11, t["fc_history"], [
            (series("domeclosedhours", "h", FORECAST, FORECAST_ID), BLUE),
        ], {"x": 0, "y": 24, "w": 12, "h": 7}, "h", points=True),
        timeseries(12, t["seeing_history"], [
            (series("seeingforecast", "seeing", FORECAST, FORECAST_ID), BLUE),
        ], {"x": 12, "y": 24, "w": 12, "h": 7}, "none", points=True),
    ]
    return {
        "uid": "roquemodel", "title": t["title"], "tags": ["roquemodel", "fiware"],
        "timezone": "utc", "refresh": "5m", "schemaVersion": 39, "editable": False,
        "time": {"from": "now-7d", "to": "now"}, "panels": panels,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_FILE.write_text(json.dumps(dashboard(), indent=1, ensure_ascii=False), encoding="utf-8")
    print("written", DASHBOARD_FILE.relative_to(config.PROJECT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
