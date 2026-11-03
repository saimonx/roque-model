"""The public Grafana dashboard (Grafana Cloud), in Spanish, like the web page.

The local dashboards (dashboards.py) read CrateDB through FIWARE, which only runs
on the Mac. This one reads the same JSON the web page reads, published every hour
on GitHub Pages (site/data/tonight.json), with the Infinity data source. So it works
with the Mac switched off, and anyone can open it through its public link.

In Grafana Cloud it needs an Infinity data source with uid `roquemodel-pages`
allowed to read https://saimonx.github.io. The JSON written here is uploaded with
Grafana's API (POST /api/dashboards/db) and shared publicly from the dashboard's
"Share externally" option.

Usage:
    .venv/bin/python -m roque_forecast.cloud_dashboard   # writes infra/grafana/cloud/roquemodel.json
"""

import json

from roque_forecast import config
from roque_forecast.dashboards import AQUA, BLUE, CRITICAL, GOOD, ORANGE, WARNING

OUT_FILE = config.PROJECT_DIR / "infra" / "grafana" / "cloud" / "roquemodel.json"
DATASOURCE = {"type": "yesoreyeram-infinity-datasource", "uid": "roquemodel-pages"}
DATA_URL = "https://saimonx.github.io/roque-model/data/tonight.json"
WEB_URL = "https://saimonx.github.io/roque-model/"
GREY = "#8e8d87"


def query(ref: str, root: str, columns: list[tuple[str, str, str]]) -> dict:
    """One Infinity query: the rows under `root` in tonight.json, with (selector, name, type) columns.

    The "backend" parser runs on Grafana's server, which public dashboards need.
    """
    return {"refId": ref, "datasource": DATASOURCE, "type": "json", "source": "url", "format": "table",
            "parser": "backend", "url": DATA_URL, "url_options": {"method": "GET"}, "root_selector": root,
            "columns": [{"selector": s, "text": name, "type": kind} for s, name, kind in columns]}


def kmh(target: dict, field: str, name: str) -> dict:
    """Add to an Infinity query a column `name` = `field` × 3.6 (m/s to km/h, as on the web page)."""
    return {**target, "computed_columns": [{"selector": f"{field} * 3.6", "text": name, "type": "number"}]}


def hide(field: str) -> list[dict]:
    """Transformation that drops `field` (the m/s column once km/h is computed)."""
    return [{"id": "organize", "options": {"excludeByName": {field: True}}}]


def thresholds(steps: list[tuple[float | None, str]], show: bool = False) -> dict:
    out = {"thresholds": {"mode": "absolute", "steps": [{"value": v, "color": c} for v, c in steps]}}
    if show:
        out["custom"] = {"thresholdsStyle": {"mode": "dashed"}}
    return out


def series(pid: int, title: str, description: str, targets: list[dict], grid: dict, unit: str,
           colors: dict[str, str], *, bars: bool = False, limits: list[tuple[float | None, str]] | None = None,
           minimum: float | None = None, maximum: float | None = None, transformations: list | None = None,
           last_24h: bool = False) -> dict:
    """A time series panel; `colors` gives each field its fixed colour (same as the web page)."""
    defaults = {"unit": unit, "custom": {"drawStyle": "bars" if bars else "line", "lineWidth": 2,
                                         "fillOpacity": 80 if bars else 0, "showPoints": "never",
                                         "spanNulls": 3_600_000 if not bars else False}}
    if minimum is not None:
        defaults["min"] = minimum
    if maximum is not None:
        defaults["max"] = maximum
    if limits:
        defaults["thresholds"] = thresholds(limits)["thresholds"]
        defaults["custom"]["thresholdsStyle"] = {"mode": "dashed"}
    overrides = [{"matcher": {"id": "byName", "options": name},
                  "properties": [{"id": "color", "value": {"mode": "fixed", "fixedColor": color}}]}
                 for name, color in colors.items()]
    panel = {"id": pid, "type": "timeseries", "title": title, "description": description, "datasource": DATASOURCE,
            "gridPos": grid, "targets": targets, "transformations": transformations or [],
            "fieldConfig": {"defaults": defaults, "overrides": overrides},
            "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                        "tooltip": {"mode": "multi", "sort": "none"}}}
    if last_24h:
        panel["timeFrom"] = "24h"
    return panel


def stat(pid: int, title: str, description: str, target: dict, grid: dict, unit: str, steps: list,
         decimals: int = 0, mappings: list | None = None) -> dict:
    return {"id": pid, "type": "stat", "title": title, "description": description, "datasource": DATASOURCE,
            "gridPos": grid, "targets": [target],
            "fieldConfig": {"defaults": {"unit": unit, "decimals": decimals, "mappings": mappings or [],
                                         **thresholds(steps)}, "overrides": []},
            "options": {"colorMode": "background", "graphMode": "none", "textMode": "value",
                        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "/.*/", "values": False}}}


# Time range of the forecast panels: 19:00 to 07:00 (Canary time) of the night that is running
# or comes next. Grafana date maths: "now-7h/d" is the day of 7 hours ago, so the range only
# jumps to the next night after 07:00 (the night always ends before then). In "from" it rounds
# to the start of that day (+19h = 19:00); in "to" it rounds to its end (+7h = 07:00 next day).
# Nights are longest in winter (about 19:45 to 06:20), so in summer the edges stay empty for a
# while. The station panels set their own range (the last 24 hours).
NIGHT_RANGE = {"from": "now-7h/d+19h", "to": "now-7h/d+7h"}


def dashboard() -> dict:
    hours = query("A", "hours", [("local", "Hora", "string"), ("p_closed", "RoqueModel", "number")])
    raw = query("A", "hours", [("local", "Hora", "string"), ("raw_closed", "Solo la previsión", "boolean")])
    fc = lambda cols: query("A", "hourly", [("t", "Hora", "timestamp"), *cols])
    st = lambda cols: query("A", "station_24h", [("t", "Hora", "timestamp"), *cols])
    one = lambda root, sel, name, kind="number": query("A", root, [(sel, name, kind)])

    about = (f"**RoqueModel**: probabilidad, hora a hora, de que la cúpula esté cerrada esta noche en el "
             f"Observatorio del Roque de los Muchachos (La Palma), por humedad, viento o hielo. "
             f"Explicación completa del modelo en la [web del proyecto]({WEB_URL}). "
             f"Se actualiza cada hora (GitHub Actions). **Proyecto independiente, no afiliado a GRANTECAN ni a "
             f"ningún observatorio.** Datos reales y públicos: estación del NOT y previsiones ECMWF y NOAA GFS vía "
             f"Open-Meteo (CC BY 4.0). Horas en hora canaria.")
    level_colors = [(None, GOOD), (0.2, WARNING), (0.5, CRITICAL)]
    mode_map = [{"type": "value", "options": {
        "provisional": {"text": "Provisional", "color": WARNING, "index": 0},
        "final": {"text": "Definitivo", "color": GOOD, "index": 1}}}]

    panels = [
        {"id": 1, "type": "text", "title": "", "gridPos": {"x": 0, "y": 0, "w": 24, "h": 3},
         "options": {"mode": "markdown", "content": about}},
        stat(2, "Horas que se podrá observar", "Horas de noche menos las horas de cúpula cerrada previstas por RoqueModel.",
             one("forecast", "open_h", "Horas"), {"x": 0, "y": 3, "w": 6, "h": 4}, "suffix: h", [(None, CRITICAL), (3, WARNING), (6, GOOD)]),
        stat(3, "Horas de cúpula cerrada previstas", "Suma de las probabilidades de todas las horas de la noche.",
             one("forecast", "closed_h", "Horas"), {"x": 6, "y": 3, "w": 6, "h": 4}, "suffix: h", [(None, GOOD), (2, WARNING), (5, CRITICAL)], 1),
        stat(4, "Modelo actual", "Provisional antes de que empiece la noche (sin la estación de la cumbre); definitivo desde su inicio.",
             one("", "mode", "Modelo", "string"), {"x": 12, "y": 3, "w": 6, "h": 4}, "none", [(None, BLUE)], mappings=mode_map),
        stat(5, "Horas de noche astronómica", "Duración de la noche astronómica de esta noche.",
             one("night", "length_h", "Horas"), {"x": 18, "y": 3, "w": 6, "h": 4}, "suffix: h", [(None, BLUE)], 1),

        # One bar per night hour (local time), coloured by level like the web page.
        {"id": 6, "type": "barchart", "title": "RoqueModel: probabilidad de cúpula cerrada por hora",
         "description": "Verde: menos del 20 %. Amarillo: del 20 al 50 %. Rojo: más del 50 %.",
         "datasource": DATASOURCE, "gridPos": {"x": 0, "y": 7, "w": 16, "h": 9}, "targets": [hours],
         "fieldConfig": {"defaults": {"unit": "percentunit", "min": 0, "max": 1, "decimals": 0,
                                      "color": {"mode": "thresholds"}, **thresholds(level_colors),
                                      "custom": {"fillOpacity": 90, "lineWidth": 0}}, "overrides": []},
         "options": {"xField": "Hora", "showValue": "always", "barWidth": 0.85, "groupWidth": 0.7,
                     "orientation": "vertical", "colorByField": "RoqueModel",
                     "legend": {"showLegend": False}, "tooltip": {"mode": "single"}}},
        {"id": 7, "type": "table", "title": "Solo la previsión del tiempo: cerrar o abrir",
         "description": "Las reglas de cierre (humedad ≥ 90 %, viento ≥ 80 km/h o hielo) aplicadas a la previsión tal cual.",
         "datasource": DATASOURCE, "gridPos": {"x": 16, "y": 7, "w": 8, "h": 9}, "targets": [raw],
         "fieldConfig": {"defaults": {"custom": {"align": "center"}}, "overrides": [
             {"matcher": {"id": "byName", "options": "Solo la previsión"}, "properties": [
                 {"id": "mappings", "value": [{"type": "value", "options": {
                     "true": {"text": "cerrar", "color": CRITICAL}, "false": {"text": "abrir", "color": GOOD}}}]},
                 {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}}]}]},
         "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}}},

        series(8, "Previsión: humedad (%)", "Humedad prevista en la cumbre. La cúpula se cierra al 90 %.",
               [fc([("rh", "Humedad", "number")])], {"x": 0, "y": 16, "w": 8, "h": 8}, "percent",
               {"Humedad": BLUE}, limits=[(None, "transparent"), (90, CRITICAL)], minimum=0, maximum=100),
        series(9, "Previsión: viento a 750 hPa (km/h)", "Viento previsto a la altura de la cumbre (GFS). Límite: 80 km/h.",
               [kmh(fc([("wind750", "wind750", "number")]), "wind750", "Viento")], {"x": 8, "y": 16, "w": 8, "h": 8}, "velocitykmh",
               {"Viento": AQUA}, limits=[(None, "transparent"), (80, CRITICAL)], minimum=0,
               transformations=hide("wind750")),
        series(10, "Previsión: temperatura y punto de rocío (°C)", "Si se juntan, hay riesgo de condensación; bajo 0 °C, de hielo.",
               [fc([("temp", "Temperatura", "number"), ("dew", "Punto de rocío", "number")])],
               {"x": 16, "y": 16, "w": 8, "h": 8}, "celsius", {"Temperatura": ORANGE, "Punto de rocío": BLUE}),
        series(11, "Previsión: nubes (%)", "Nubosidad total prevista.",
               [fc([("cloud", "Nubes", "number")])], {"x": 0, "y": 24, "w": 8, "h": 7}, "percent", {"Nubes": GREY},
               minimum=0, maximum=100),
        series(12, "Previsión: lluvia (mm)", "Precipitación prevista por hora.",
               [fc([("precip", "Lluvia", "number")])], {"x": 8, "y": 24, "w": 8, "h": 7}, "lengthmm", {"Lluvia": BLUE},
               bars=True, minimum=0),
        series(13, "Previsión: presión (hPa)", "Presión prevista en la cumbre.",
               [fc([("pressure", "Presión", "number")])], {"x": 16, "y": 24, "w": 8, "h": 7}, "pressurehpa", {"Presión": GREY}),

        series(14, "Estación del NOT, últimas 24 h: humedad (%)", "Medida real en la cumbre. La cúpula se cierra al 90 %.",
               [st([("rh", "Humedad", "number")])], {"x": 0, "y": 31, "w": 8, "h": 8}, "percent", {"Humedad": BLUE},
               limits=[(None, "transparent"), (90, CRITICAL)], minimum=0, maximum=100, last_24h=True),
        series(15, "Estación del NOT, últimas 24 h: viento (km/h)", "Medida real en la cumbre. Límite: 80 km/h.",
               [kmh(st([("wind", "wind", "number")]), "wind", "Viento")], {"x": 8, "y": 31, "w": 8, "h": 8}, "velocitykmh", {"Viento": AQUA},
               limits=[(None, "transparent"), (80, CRITICAL)], minimum=0, transformations=hide("wind"), last_24h=True),
        series(16, "Previsto frente a medido: humedad, últimas 24 h (%)",
               "La previsión mira un punto más bajo y húmedo que la cumbre: por eso cierra de más.",
               [query("A", "forecast_vs_measured", [("t", "Hora", "timestamp"), ("forecast", "Previsto", "number"),
                                                    ("measured", "Medido (NOT)", "number")])],
               {"x": 16, "y": 31, "w": 8, "h": 8}, "percent", {"Previsto": GREY, "Medido (NOT)": ORANGE},
               limits=[(None, "transparent"), (90, CRITICAL)], minimum=0, maximum=100, last_24h=True),
    ]
    return {
        "uid": "roquemodel-public", "title": "RoqueModel — previsión de cierre de cúpula esta noche",
        "tags": ["roquemodel", "public"], "timezone": "Atlantic/Canary", "refresh": "1h", "schemaVersion": 39,
        "editable": False, "graphTooltip": 1, "time": NIGHT_RANGE, "panels": panels,
    }


def main() -> int:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(dashboard(), indent=1, ensure_ascii=False), encoding="utf-8")
    print("written", OUT_FILE.relative_to(config.PROJECT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
