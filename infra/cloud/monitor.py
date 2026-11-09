#!/usr/bin/env python3
"""Hourly health check of everything a visitor of RoqueModel sees, with self-repair and alerts.

Runs on the FIWARE server (cron, every hour) with the system Python only (no packages):

1. Web page (GitHub Pages): it answers, tonight's forecast is recent and makes sense
   (probabilities between 0 and 1, closed + open hours = night length, the right model for
   the time of day, accuracy figures present), and /grafana/ still points to the dashboard.
2. FIWARE: Orion and QuantumLeap answer over HTTPS, the forecast entity is the same run as the
   web page, the NOT station history is recent, writing without the token is refused, and the
   HTTPS certificate is not about to expire.
3. Grafana Cloud: the public dashboard opens and its panels return data (read from FIWARE).
4. GitHub: the last hourly forecast and the last test run succeeded, and the workflows are enabled.
5. This server: the five containers are running, and there is disk and memory to spare.

Self-repair (checked first): containers that are not running are started again; if the forecast
is late, the hourly workflow is launched (an empty commit to the `kick` branch). A repair is reported
like a failure, so it also arrives by e-mail.

Result: Healthchecks.io gets "OK" (with a summary) or "fail" (with what failed), and e-mails
José on failure and on recovery. If this check itself stops (server down), Healthchecks.io
notices the missing ping and e-mails too.

Configuration in /opt/roquemodel/monitor.env (never in Git):
    HC_PING_URL=https://hc-ping.com/<uuid>
    GH_TOKEN=<optional: a GitHub token, only to raise the API rate limit>
To relaunch a late forecast it uses a deploy key of the repository (/root/.ssh/roquemodel_kick):
it can only write to this repository, and only pushes to the `kick` branch.

The same script also starts the forecast every hour (cron at :05, --launch): GitHub's own schedule
skips most runs, and this server is always on, so the page does not depend on any personal computer.

Usage:
    python3 monitor.py            # check, repair, report
    python3 monitor.py --dry-run  # check only: no repair, no report
    python3 monitor.py --launch   # only start the hourly forecast (up to 3 tries), no checks, no report
"""

import datetime as dt
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

WEB = "https://saimonx.github.io/roque-model/"
FIWARE_HOST = "178-105-253-255.sslip.io"
FIWARE = f"https://{FIWARE_HOST}"
FORECAST_ID = "urn:ngsi-ld:WeatherForecast:ORM-tonight"
NOT_ID = "urn:ngsi-ld:WeatherObserved:ORM-NOT"
GRAFANA = "https://ardentcloset2195.grafana.net"
# The public dashboards' access tokens (public links): one in Spanish (/grafana/), one in English (/grafana/en/).
GRAFANA_TOKENS = {"es": "da7d86c2a1c543a38467827c9f34b1c8", "en": "76bc0c1e23534e81b865e99f0b6f2a7f"}
GRAFANA_PATHS = {"es": "grafana/", "en": "grafana/en/"}
GRAFANA_PANELS = {2: "horas que se podrá observar", 6: "probabilidad por hora", 14: "estación del NOT"}
REPO = "saimonx/roque-model"
COMPOSE_DIR = "/opt/roquemodel"
SERVICES = ["mongo", "orion", "crate", "quantumleap", "caddy"]

MAX_FORECAST_AGE_MIN = 150   # the forecast runs hourly; GitHub sometimes starts it late
MAX_STATION_AGE_MIN = 240    # the NOT archive can lag a couple of hours
MIN_CERT_DAYS = 14
NOW = dt.datetime.now(dt.UTC)

problems: list[str] = []     # each one makes the check fail
notes: list[str] = []        # warnings and repairs, reported but not failures
summary: list[str] = []      # what was checked and found fine


def config() -> dict:
    out = dict(os.environ)
    path = os.path.join(COMPOSE_DIR, "monitor.env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.lstrip().startswith("#"):
                    k, v = line.strip().split("=", 1)
                    out.setdefault(k, v)
    return out


def http(url: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None,
         timeout: int = 30) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"User-Agent": "roquemodel-monitor", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def get_json(url: str, **kw):
    status, body = http(url, **kw)
    if status != 200:
        raise RuntimeError(f"{url} answered {status}")
    return json.loads(body)


class ServiceDown(Exception):
    """The service answered 5xx (or did not answer) on every try: its outage, not RoqueModel's."""


def get_json_retry(url: str, tries: int = 3, wait_s: int = 20, **kw):
    """Like get_json, but retries server errors and timeouts, which are usually brief.

    A 4xx (bad token, missing repo...) is not retried: that one is ours to fix."""
    for attempt in range(1, tries + 1):
        try:
            status, body = http(url, **kw)
        except (urllib.error.URLError, TimeoutError) as e:
            status, body = None, str(e)
        if status == 200:
            return json.loads(body)
        if status is not None and status < 500:
            raise RuntimeError(f"{url} answered {status}")
        if attempt < tries:
            time.sleep(wait_s)
    raise ServiceDown(f"{url} answered {status or 'nothing'} {tries} times")


def parse_time(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text)


def minutes_ago(t: dt.datetime) -> float:
    return (NOW - t).total_seconds() / 60


def check(name: str):
    """Decorator: run one group of checks; an unexpected error counts as a problem."""
    def wrap(fn):
        def run(*args):
            try:
                return fn(*args)
            except Exception as e:  # noqa: BLE001 - any failure here must be reported, not crash the check
                problems.append(f"{name}: {e}")
        return run
    return wrap


# --------------------------------------------------------------------------
# 1. The web page
# --------------------------------------------------------------------------
@check("web")
def check_web() -> dict | None:
    status, body = http(WEB)
    if status != 200 or b"RoqueModel" not in body:
        problems.append(f"web: la página no responde bien ({status})")
        return None
    page = get_json(WEB + "data/tonight.json?n=" + str(NOW.timestamp()))
    issued = parse_time(page["issued_utc"])
    age = minutes_ago(issued)
    if age > MAX_FORECAST_AGE_MIN:
        problems.append(f"web: el pronóstico tiene {age:.0f} min (límite {MAX_FORECAST_AGE_MIN})")
    night, forecast, hours = page["night"], page["forecast"], page["hours"]
    start, end = parse_time(night["start_utc"]), parse_time(night["end_utc"])
    if not hours:
        problems.append("web: el pronóstico no tiene horas")
    if any(not 0 <= h["p_closed"] <= 1 for h in hours):
        problems.append("web: hay probabilidades fuera de 0–1")
    closed_sum = sum(h["p_closed"] * h["dark_minutes"] / 60 for h in hours)
    if abs(closed_sum - forecast["closed_h"]) > 0.05:
        problems.append(f"web: horas cerradas {forecast['closed_h']} no cuadran con las horas ({closed_sum:.2f})")
    if abs(forecast["open_h"] + forecast["closed_h"] - night["length_h"]) > 0.05:
        problems.append("web: horas abiertas + cerradas no suman la noche")
    if not 7 <= night["length_h"] <= 12.5:
        problems.append(f"web: noche de {night['length_h']} h, fuera de lo posible")
    expected_mode = "final" if issued >= start else "provisional"
    if page["mode"] != expected_mode:
        problems.append(f"web: modelo {page['mode']} y debería ser {expected_mode}")
    if end < NOW - dt.timedelta(hours=2):
        problems.append("web: el pronóstico es de una noche que ya acabó")
    if not page.get("hourly") or not page.get("station_24h"):
        problems.append("web: faltan las gráficas de previsión o de la estación")
    for source, when in (page.get("stale") or {}).items():
        notes.append(f"web: la fuente {source} no respondió; se usó su copia de {when}")
    evaluation = get_json(WEB + "data/evaluation.json?n=" + str(NOW.timestamp()))
    wrong = evaluation["comparison"]["final"]["wrong"]
    if not 0.05 <= wrong <= 0.15:
        problems.append(f"web: el acierto publicado es raro ({1 - wrong:.1%})")
    for lang, path in GRAFANA_PATHS.items():
        status, body = http(WEB + path)
        if status != 200 or GRAFANA_TOKENS[lang].encode() not in body:
            problems.append(f"web: /{path} no lleva al panel")
    summary.append(f"web: pronóstico de hace {age:.0f} min, modelo {page['mode']}, "
                   f"{forecast['closed_h']} h cerradas de {night['length_h']}")
    return page


# --------------------------------------------------------------------------
# 2. FIWARE
# --------------------------------------------------------------------------
@check("fiware")
def check_fiware(page: dict | None) -> None:
    version = get_json(FIWARE + "/orion/version")
    if "orion" not in version:
        problems.append("fiware: Orion no responde")
    if "version" not in get_json(FIWARE + "/ql/version"):
        problems.append("fiware: QuantumLeap no responde")
    entity = get_json(f"{FIWARE}/orion/v2/entities/{FORECAST_ID}?options=keyValues")
    issued = parse_time(entity["dateIssued"])
    age = minutes_ago(issued)
    if age > MAX_FORECAST_AGE_MIN:
        problems.append(f"fiware: el pronóstico tiene {age:.0f} min")
    if page and parse_time(page["issued_utc"]) != issued:
        notes.append(f"fiware: pronóstico de las {issued:%H:%M} y web de las {parse_time(page['issued_utc']):%H:%M} UTC")
    if not entity.get("hourlyClosureProbability"):
        problems.append("fiware: el pronóstico no tiene las horas")
    history = get_json(f"{FIWARE}/ql/v2/entities/{NOT_ID}/attrs/relativeHumidity?lastN=1")
    station_age = minutes_ago(parse_time(history["index"][-1]))
    if station_age > MAX_STATION_AGE_MIN:
        problems.append(f"fiware: la última medida de la estación tiene {station_age:.0f} min")
    status, _ = http(FIWARE + "/orion/v2/entities", method="POST", data=b'{"id":"monitor","type":"Test"}',
                     headers={"Content-Type": "application/json"})
    if status != 401:
        problems.append(f"fiware: ¡se puede escribir sin token! ({status})")
    ctx = ssl.create_default_context()
    with socket.create_connection((FIWARE_HOST, 443), timeout=15) as sock, \
            ctx.wrap_socket(sock, server_hostname=FIWARE_HOST) as tls:
        expires = dt.datetime.strptime(tls.getpeercert()["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=dt.UTC)
    days = (expires - NOW).days
    if days < MIN_CERT_DAYS:
        problems.append(f"fiware: el certificado HTTPS caduca en {days} días")
    summary.append(f"fiware: pronóstico de hace {age:.0f} min, estación de hace {station_age:.0f} min, "
                   f"certificado {days} días")


# --------------------------------------------------------------------------
# 3. Grafana Cloud (public dashboard)
# --------------------------------------------------------------------------
@check("grafana")
def check_grafana() -> None:
    body = json.dumps({"intervalMs": 3600000, "maxDataPoints": 500,
                       "timeRange": {"from": "now-24h", "to": "now+12h", "timezone": "Atlantic/Canary"}}).encode()
    for lang, token in GRAFANA_TOKENS.items():
        status, _ = http(f"{GRAFANA}/api/public/dashboards/{token}")
        if status != 200:
            problems.append(f"grafana: el panel público ({lang}) no abre ({status})")
            continue
        for panel, label in GRAFANA_PANELS.items():
            status, raw = http(f"{GRAFANA}/api/public/dashboards/{token}/panels/{panel}/query", method="POST",
                               data=body, headers={"Content-Type": "application/json"})
            result = json.loads(raw).get("results", {}).get("A", {}) if status == 200 else {}
            frames = result.get("frames") or []
            rows = len(frames[0]["data"]["values"][0]) if frames and frames[0].get("data", {}).get("values") else 0
            if status != 200 or result.get("error") or rows == 0:
                problems.append(f"grafana: el panel «{label}» ({lang}) no tiene datos ({status} {result.get('error', '')})")
    summary.append("grafana: los dos paneles públicos (es, en) abren y tienen datos")


# --------------------------------------------------------------------------
# 4. GitHub Actions
# --------------------------------------------------------------------------
@check("github")
def check_github(token: str | None) -> bool:
    """Returns True if the hourly forecast looks late (so self-repair can launch it).

    If GitHub's API itself is down (5xx on every try) this is only a note, not a failure: the
    forecast does not need the API (it is started with git over SSH), and a late forecast is still
    caught by the web and FIWARE checks."""
    try:
        return _check_github(token)
    except ServiceDown as e:
        notes.append(f"github: no se ha podido comprobar, la API de GitHub falla ({e})")
        return False


def _check_github(token: str | None) -> bool:
    auth = {"Authorization": f"Bearer {token}"} if token else {}
    workflows = get_json_retry(f"https://api.github.com/repos/{REPO}/actions/workflows", headers=auth)["workflows"]
    for w in workflows:
        if w["state"] != "active":
            problems.append(f"github: el flujo «{w['name']}» está desactivado ({w['state']})")
    late = False
    for name, max_age_h in (("forecast.yml", 3), ("tests.yml", None)):
        runs = get_json_retry(f"https://api.github.com/repos/{REPO}/actions/workflows/{name}/runs?per_page=5&status=completed",
                        headers=auth)["workflow_runs"]
        if not runs:
            problems.append(f"github: {name} no tiene ejecuciones")
            continue
        last = runs[0]
        if last["conclusion"] != "success":
            problems.append(f"github: la última ejecución de {name} terminó en «{last['conclusion']}»: {last['html_url']}")
        if max_age_h and minutes_ago(parse_time(last["updated_at"])) > max_age_h * 60:
            late = True
            problems.append(f"github: {name} no se ejecuta desde hace más de {max_age_h} h")
    summary.append("github: últimas ejecuciones correctas")
    return late


# --------------------------------------------------------------------------
# 5. This server
# --------------------------------------------------------------------------
@check("servidor")
def check_server(repair: bool) -> None:
    if not shutil.which("docker") or not os.path.isdir(COMPOSE_DIR):
        return  # not on the server (a test run elsewhere)

    def running() -> set[str]:
        out = subprocess.run(["docker", "compose", "ps", "--status", "running", "--format", "{{.Service}}"],
                             cwd=COMPOSE_DIR, capture_output=True, text=True, timeout=120, check=False).stdout
        return set(out.split())

    missing = [s for s in SERVICES if s not in running()]
    if missing and repair:
        subprocess.run(["docker", "compose", "up", "-d"], cwd=COMPOSE_DIR, capture_output=True, timeout=600, check=False)
        still = [s for s in SERVICES if s not in running()]
        if still:
            problems.append(f"servidor: no arrancan {', '.join(still)} (reintentado)")
        else:
            notes.append(f"servidor: se habían parado {', '.join(missing)}; arrancados de nuevo")
    elif missing:
        problems.append(f"servidor: parados {', '.join(missing)}")
    disk = shutil.disk_usage("/")
    used = disk.used / disk.total
    if used > 0.85:
        problems.append(f"servidor: disco al {used:.0%}")
    with open("/proc/meminfo") as f:
        mem = dict(line.split(":") for line in f)
    available_mb = int(mem["MemAvailable"].split()[0]) // 1024
    if available_mb < 200:
        problems.append(f"servidor: solo {available_mb} MB de memoria libre")
    summary.append(f"servidor: contenedores en marcha, disco al {used:.0%}, {available_mb} MB libres")


def launch_forecast() -> bool:
    """Start the hourly forecast now: push one empty commit on top of main to the repository's `kick`
    branch, which the workflow listens to (GitHub reads the workflow from the pushed commit, so it
    must contain main's files). The server's deploy key can only write to this repository.
    Returns True if the push worked."""
    key = "/root/.ssh/roquemodel_kick"
    folder = os.path.join(COMPOSE_DIR, "kick")
    ssh = f"ssh -i {key} -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
    git = ["git", "-c", f"core.sshCommand={ssh}", "-c", "user.name=roque-model bot",
           "-c", "user.email=546832+saimonx@users.noreply.github.com"]
    shutil.rmtree(folder, ignore_errors=True)
    steps = [[*git, "clone", "-q", "--depth", "1", "--branch", "main", f"git@github.com:{REPO}.git", folder],
             [*git, "-C", folder, "commit", "-q", "--allow-empty", "-m", f"Start the forecast ({NOW:%Y-%m-%d %H:%M} UTC)"],
             [*git, "-C", folder, "push", "-q", "--force", "origin", "HEAD:kick"]]
    for step in steps:
        result = subprocess.run(step, capture_output=True, text=True, timeout=180, check=False)
        if result.returncode:
            notes.append(f"reparación: no se pudo lanzar el pronóstico ({result.stderr.strip()[:200]})")
            return False
    notes.append("reparación: lanzado el pronóstico en GitHub")
    return True


def launch_only() -> int:
    """The hourly start (cron at :05). Up to 3 tries, 30 s apart, because a single network timeout must
    not cost an hour. It does not ping Healthchecks.io: that is the job of the check at :35, which
    also notices if these starts stop working (the forecast gets late)."""
    for attempt in range(1, 4):
        if launch_forecast():
            print(f"{NOW:%Y-%m-%d %H:%M} UTC: pronóstico lanzado (intento {attempt})")
            return 0
        print(f"{NOW:%Y-%m-%d %H:%M} UTC: intento {attempt} fallido: {notes[-1]}")
        if attempt < 3:
            time.sleep(30)
    return 1


def report(url: str, failed: bool, text: str) -> None:
    http(url + ("/fail" if failed else ""), method="POST", data=text.encode()[:9000],
         headers={"Content-Type": "text/plain; charset=utf-8"}, timeout=20)


def main() -> int:
    if "--launch" in sys.argv:
        return launch_only()
    dry_run = "--dry-run" in sys.argv
    cfg = config()
    token = cfg.get("GH_TOKEN") or None
    # The server first: if a container had stopped and is started again, give it a moment so the
    # checks below see the repaired state.
    check_server(not dry_run)
    if any(n.startswith("servidor:") for n in notes):
        time.sleep(60)
    page = check_web()
    check_fiware(page)
    check_grafana()
    late = check_github(token)
    if late and not dry_run and os.path.exists("/root/.ssh/roquemodel_kick"):
        launch_forecast()
    repaired = any(n.startswith(("servidor:", "reparación:")) for n in notes)
    # A repair is reported as a failure too, so José gets an e-mail about it (and another when the
    # next hourly check is fine again).
    failed = bool(problems) or repaired
    state = "FALLA" if problems else ("REPARADO" if repaired else "todo bien")
    lines = [f"RoqueModel — comprobación del {NOW:%Y-%m-%d %H:%M} UTC: {state}", ""]
    lines += [f"✗ {p}" for p in problems] + [f"! {n}" for n in notes] + [f"✓ {s}" for s in summary]
    text = "\n".join(lines)
    print(text)
    if not dry_run and cfg.get("HC_PING_URL"):
        report(cfg["HC_PING_URL"], failed, text)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
