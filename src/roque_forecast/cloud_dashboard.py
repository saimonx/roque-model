"""The public Grafana dashboards (Grafana Cloud), in Spanish and in English, like the web page.

It reads FIWARE, the platform the hourly forecast publishes to (infra/cloud/, a small
cloud server), through the Infinity data source:
- the current state from Orion: tonight's WeatherForecast entity, with its hour-by-hour
  tables (RoqueModel, the forecast alone, the weather forecast, forecast against measured);
- the history from QuantumLeap: the NOT station's last 24 h (WeatherObserved).
So FIWARE sits between RoqueModel and Grafana, as on the GTC's own platform, and anyone
can open the dashboard through its public link.

In Grafana Cloud it needs an Infinity data source with uid `roquemodel-fiware` allowed
to read the FIWARE server. The JSON written here is uploaded with Grafana's API
(POST /api/dashboards/db) and shared publicly from the dashboard's "Share externally" option.

Usage:
    .venv/bin/python -m roque_forecast.cloud_dashboard   # writes infra/grafana/cloud/roquemodel{,_en}.json
"""

import json

from roque_forecast import config
from roque_forecast.dashboards import AQUA, BLUE, CRITICAL, GOOD, ORANGE, WARNING
from roque_forecast.fiware import FORECAST_ID, NOT_ID

OUT_FILE = config.PROJECT_DIR / "infra" / "grafana" / "cloud" / "roquemodel.json"
DATASOURCE = {"type": "yesoreyeram-infinity-datasource", "uid": "roquemodel-fiware"}
FIWARE_URL = "https://178-105-253-255.sslip.io"
FORECAST_URL = f"{FIWARE_URL}/orion/v2/entities/{FORECAST_ID}?options=keyValues"
STATION_HISTORY_URL = f"{FIWARE_URL}/ql/v2/entities/{NOT_ID}?lastN=200"
WEB_URL = "https://saimonx.github.io/roque-model/"
GREY = "#8e8d87"


def query(ref: str, root: str, columns: list[tuple[str, str, str]], url: str = FORECAST_URL) -> dict:
    """One Infinity query: the rows under `root` (a JSONata expression) of a FIWARE answer, with
    (selector, name, type) columns. By default, tonight's forecast entity in Orion.

    The "backend" parser runs on Grafana's server, which public dashboards need.
    """
    return {"refId": ref, "datasource": DATASOURCE, "type": "json", "source": "url", "format": "table",
            "parser": "backend", "url": url, "url_options": {"method": "GET"}, "root_selector": root,
            "columns": [{"selector": s, "text": name, "type": kind} for s, name, kind in columns]}


def station(attr: str, scale: float) -> str:
    """JSONata: QuantumLeap's history answer (one list of times, one list per attribute) as rows
    {t, v}, with the value multiplied by `scale` (humidity is stored as a fraction, wind in m/s)."""
    return (f'($i := index; $v := attributes[attrName="{attr}"].values; '
            f'$map($i, function($t, $k) {{ {{"t": $t, "v": $v[$k] * {scale}}} }}))')


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


# Every text of the dashboard, in Spanish and English (two public dashboards, one per language,
# like the web page's ES · EN switch). Field names are texts too: they label legends and tooltips.
TEXTS = {
    "es": {
        "uid": "roquemodel-public", "web": WEB_URL, "title": "RoqueModel — previsión de cierre de cúpula esta noche",
        "about": ("**RoqueModel**: probabilidad, hora a hora, de que la cúpula esté cerrada esta noche en el "
                  "Observatorio del Roque de los Muchachos (La Palma), por humedad, viento o hielo. "
                  "Explicación completa del modelo en la [web del proyecto]({web}). "
                  "Se actualiza cada hora (GitHub Actions) y estos datos llegan a través de FIWARE (Orion y QuantumLeap). "
                  "**Proyecto independiente, no afiliado a GRANTECAN ni a "
                  "ningún observatorio.** Datos reales y públicos: estación del NOT y previsiones ECMWF y NOAA GFS vía "
                  "Open-Meteo (CC BY 4.0). Horas en hora canaria."),
        "hour": "Hora", "hours": "Horas", "model": "Modelo", "alone": "Solo la previsión",
        "provisional": "Provisional", "final": "Definitivo", "close": "cerrar", "open": "abrir",
        "humidity": "Humedad", "wind": "Viento", "temp": "Temperatura", "dew": "Punto de rocío", "cloud": "Nubes",
        "rain": "Lluvia", "pressure": "Presión", "forecast": "Previsto", "measured": "Medido (NOT)",
        "p2": ("Horas que se podrá observar", "Horas de noche menos las horas de cúpula cerrada previstas por RoqueModel."),
        "p3": ("Horas de cúpula cerrada previstas", "Suma de las probabilidades de todas las horas de la noche."),
        "p4": ("Modelo actual", "Provisional antes de que empiece la noche (sin la estación de la cumbre); definitivo desde su inicio."),
        "p5": ("Horas de noche astronómica", "Duración de la noche astronómica de esta noche."),
        "p6": ("RoqueModel: probabilidad de cúpula cerrada por hora", "Verde: menos del 20 %. Amarillo: del 20 al 50 %. Rojo: más del 50 %."),
        "p7": ("Solo la previsión del tiempo: cerrar o abrir",
               "Las reglas de cierre (humedad ≥ 90 %, viento ≥ 80 km/h o hielo) aplicadas a la previsión tal cual."),
        "p8": ("Previsión: humedad (%)", "Humedad prevista en la cumbre. La cúpula se cierra al 90 %."),
        "p9": ("Previsión: viento a 750 hPa (km/h)", "Viento previsto a la altura de la cumbre (GFS). Límite: 80 km/h."),
        "p10": ("Previsión: temperatura y punto de rocío (°C)", "Si se juntan, hay riesgo de condensación; bajo 0 °C, de hielo."),
        "p11": ("Previsión: nubes (%)", "Nubosidad total prevista."),
        "p12": ("Previsión: lluvia (mm)", "Precipitación prevista por hora."),
        "p13": ("Previsión: presión (hPa)", "Presión prevista en la cumbre."),
        "p14": ("Estación del NOT, últimas 24 h: humedad (%)", "Medida real en la cumbre. La cúpula se cierra al 90 %."),
        "p15": ("Estación del NOT, últimas 24 h: viento (km/h)", "Medida real en la cumbre. Límite: 80 km/h."),
        "p16": ("Previsto frente a medido: humedad, últimas 24 h (%)",
                "La previsión mira un punto más bajo y húmedo que la cumbre: por eso cierra de más."),
    },
    "en": {
        "uid": "roquemodel-public-en", "web": WEB_URL + "?lang=en", "title": "RoqueModel — tonight's dome-closure forecast",
        "about": ("**RoqueModel**: hour-by-hour probability that the dome is closed tonight at the "
                  "Roque de los Muchachos Observatory (La Palma), because of humidity, wind or ice. "
                  "Full explanation of the model on the [project's website]({web}). "
                  "Updated every hour (GitHub Actions); these data arrive through FIWARE (Orion and QuantumLeap). "
                  "**Independent project, not affiliated with GRANTECAN or any observatory.** "
                  "Real, public data: NOT weather station and ECMWF and NOAA GFS forecasts via "
                  "Open-Meteo (CC BY 4.0). Times in Canary time."),
        "hour": "Hour", "hours": "Hours", "model": "Model", "alone": "Forecast alone",
        "provisional": "Provisional", "final": "Final", "close": "close", "open": "open",
        "humidity": "Humidity", "wind": "Wind", "temp": "Temperature", "dew": "Dew point", "cloud": "Cloud",
        "rain": "Rain", "pressure": "Pressure", "forecast": "Forecast", "measured": "Measured (NOT)",
        "p2": ("Hours available for observing", "Night hours minus the dome-closed hours forecast by RoqueModel."),
        "p3": ("Forecast dome-closed hours", "Sum of the probabilities of all the hours of the night."),
        "p4": ("Current model", "Provisional before the night starts (without the summit station); final from its start."),
        "p5": ("Astronomical night hours", "Length of tonight's astronomical night."),
        "p6": ("RoqueModel: probability of the dome being closed, by hour", "Green: under 20%. Yellow: 20 to 50%. Red: over 50%."),
        "p7": ("Weather forecast alone: close or open",
               "The closing rules (humidity ≥ 90%, wind ≥ 80 km/h or ice) applied to the forecast as it is."),
        "p8": ("Forecast: humidity (%)", "Forecast humidity at the summit. The dome closes at 90%."),
        "p9": ("Forecast: wind at 750 hPa (km/h)", "Forecast wind at summit height (GFS). Limit: 80 km/h."),
        "p10": ("Forecast: temperature and dew point (°C)", "If they meet, there is a risk of condensation; below 0 °C, of ice."),
        "p11": ("Forecast: cloud (%)", "Total forecast cloud cover."),
        "p12": ("Forecast: rain (mm)", "Forecast precipitation per hour."),
        "p13": ("Forecast: pressure (hPa)", "Forecast pressure at the summit."),
        "p14": ("NOT station, last 24 h: humidity (%)", "Real measurement at the summit. The dome closes at 90%."),
        "p15": ("NOT station, last 24 h: wind (km/h)", "Real measurement at the summit. Limit: 80 km/h."),
        "p16": ("Forecast against measured: humidity, last 24 h (%)",
                "The forecast looks at a point lower and damper than the summit: that is why it closes too often."),
    },
}
OUT_FILES = {"es": OUT_FILE, "en": OUT_FILE.with_name("roquemodel_en.json")}


def dashboard(lang: str = "es") -> dict:
    t = TEXTS[lang]
    hours = query("A", "hourlyClosureProbability", [("hourLocal", t["hour"], "string"), ("probability", "RoqueModel", "number")])
    raw = query("A", "hourlyClosureProbability", [("hourLocal", t["hour"], "string"),
                                                  ("forecastAloneClosed", t["alone"], "boolean")])
    fc = lambda cols: query("A", "hourlyWeatherForecast", [("t", t["hour"], "timestamp"), *cols])
    st = lambda attr, scale, name: query("A", station(attr, scale), [("t", t["hour"], "timestamp"), ("v", name, "number")],
                                         url=STATION_HISTORY_URL)
    one = lambda sel, name, kind="number": query("A", "", [(sel, name, kind)])

    about = t["about"].format(web=t["web"])
    level_colors = [(None, GOOD), (0.2, WARNING), (0.5, CRITICAL)]
    mode_map = [{"type": "value", "options": {
        "provisional": {"text": t["provisional"], "color": WARNING, "index": 0},
        "final": {"text": t["final"], "color": GOOD, "index": 1}}}]

    panels = [
        {"id": 1, "type": "text", "title": "", "gridPos": {"x": 0, "y": 0, "w": 24, "h": 3},
         "options": {"mode": "markdown", "content": about}},
        stat(2, *t["p2"], one("openHoursForecast", t["hours"]), {"x": 0, "y": 3, "w": 6, "h": 4}, "suffix: h",
             [(None, CRITICAL), (3, WARNING), (6, GOOD)]),
        stat(3, *t["p3"], one("domeClosedHours", t["hours"]), {"x": 6, "y": 3, "w": 6, "h": 4}, "suffix: h",
             [(None, GOOD), (2, WARNING), (5, CRITICAL)], 1),
        stat(4, *t["p4"], one("forecastMode", t["model"], "string"), {"x": 12, "y": 3, "w": 6, "h": 4}, "none",
             [(None, BLUE)], mappings=mode_map),
        stat(5, *t["p5"], one("nightLengthHours", t["hours"]), {"x": 18, "y": 3, "w": 6, "h": 4}, "suffix: h",
             [(None, BLUE)], 1),

        # One bar per night hour (local time), coloured by level like the web page.
        {"id": 6, "type": "barchart", "title": t["p6"][0], "description": t["p6"][1],
         "datasource": DATASOURCE, "gridPos": {"x": 0, "y": 7, "w": 16, "h": 9}, "targets": [hours],
         "fieldConfig": {"defaults": {"unit": "percentunit", "min": 0, "max": 1, "decimals": 0,
                                      "color": {"mode": "thresholds"}, **thresholds(level_colors),
                                      "custom": {"fillOpacity": 90, "lineWidth": 0}}, "overrides": []},
         "options": {"xField": t["hour"], "showValue": "always", "barWidth": 0.85, "groupWidth": 0.7,
                     "orientation": "vertical", "colorByField": "RoqueModel",
                     "legend": {"showLegend": False}, "tooltip": {"mode": "single"}}},
        {"id": 7, "type": "table", "title": t["p7"][0], "description": t["p7"][1],
         "datasource": DATASOURCE, "gridPos": {"x": 16, "y": 7, "w": 8, "h": 9}, "targets": [raw],
         "fieldConfig": {"defaults": {"custom": {"align": "center"}}, "overrides": [
             {"matcher": {"id": "byName", "options": t["alone"]}, "properties": [
                 {"id": "mappings", "value": [{"type": "value", "options": {
                     "true": {"text": t["close"], "color": CRITICAL}, "false": {"text": t["open"], "color": GOOD}}}]},
                 {"id": "custom.cellOptions", "value": {"type": "color-background", "mode": "basic"}}]}]},
         "options": {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}}},

        series(8, *t["p8"], [fc([("rh", t["humidity"], "number")])], {"x": 0, "y": 16, "w": 8, "h": 8}, "percent",
               {t["humidity"]: BLUE}, limits=[(None, "transparent"), (90, CRITICAL)], minimum=0, maximum=100),
        series(9, *t["p9"], [kmh(fc([("wind750", "wind750", "number")]), "wind750", t["wind"])],
               {"x": 8, "y": 16, "w": 8, "h": 8}, "velocitykmh",
               {t["wind"]: AQUA}, limits=[(None, "transparent"), (80, CRITICAL)], minimum=0,
               transformations=hide("wind750")),
        series(10, *t["p10"], [fc([("temp", t["temp"], "number"), ("dew", t["dew"], "number")])],
               {"x": 16, "y": 16, "w": 8, "h": 8}, "celsius", {t["temp"]: ORANGE, t["dew"]: BLUE}),
        series(11, *t["p11"], [fc([("cloud", t["cloud"], "number")])], {"x": 0, "y": 24, "w": 8, "h": 7}, "percent",
               {t["cloud"]: GREY}, minimum=0, maximum=100),
        series(12, *t["p12"], [fc([("precip", t["rain"], "number")])], {"x": 8, "y": 24, "w": 8, "h": 7}, "lengthmm",
               {t["rain"]: BLUE}, bars=True, minimum=0),
        series(13, *t["p13"], [fc([("pressure", t["pressure"], "number")])], {"x": 16, "y": 24, "w": 8, "h": 7},
               "pressurehpa", {t["pressure"]: GREY}),

        series(14, *t["p14"], [st("relativeHumidity", 100, t["humidity"])], {"x": 0, "y": 31, "w": 8, "h": 8}, "percent",
               {t["humidity"]: BLUE}, limits=[(None, "transparent"), (90, CRITICAL)], minimum=0, maximum=100, last_24h=True),
        series(15, *t["p15"], [st("windSpeed", 3.6, t["wind"])], {"x": 8, "y": 31, "w": 8, "h": 8}, "velocitykmh",
               {t["wind"]: AQUA}, limits=[(None, "transparent"), (80, CRITICAL)], minimum=0, last_24h=True),
        series(16, *t["p16"],
               [query("A", "forecastVsMeasured", [("t", t["hour"], "timestamp"), ("forecast", t["forecast"], "number"),
                                                    ("measured", t["measured"], "number")])],
               {"x": 16, "y": 31, "w": 8, "h": 8}, "percent", {t["forecast"]: GREY, t["measured"]: ORANGE},
               limits=[(None, "transparent"), (90, CRITICAL)], minimum=0, maximum=100, last_24h=True),
    ]
    return {
        "uid": t["uid"], "title": t["title"],
        "tags": ["roquemodel", "public"], "timezone": "Atlantic/Canary", "refresh": "1h", "schemaVersion": 39,
        "editable": False, "graphTooltip": 1, "time": NIGHT_RANGE, "panels": panels,
    }


def main() -> int:
    for lang, out in OUT_FILES.items():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(dashboard(lang), indent=1, ensure_ascii=False), encoding="utf-8")
        print("written", out.relative_to(config.PROJECT_DIR))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
