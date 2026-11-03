"""Error reporting with Sentry for the hourly forecast.

The hourly run (GitHub Actions) sets SENTRY_DSN. Then any error is sent to Sentry with its
traceback and context: an exception that stops the run, and every logged error (for example a
FIWARE update that failed). Warnings, such as a data source that did not answer and was replaced
by its last copy, are not sent on their own: they travel as context of a later error. Healthchecks.io (the server's
hourly health check, infra/cloud/monitor.py) says THAT something is wrong; Sentry says WHY.

Without SENTRY_DSN (on the Mac, in the tests) nothing is sent.
"""

import os


def init(component: str) -> bool:
    """Start Sentry for one program (`component` is shown as a tag); False if not configured."""
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return False
    import sentry_sdk  # imported here: only needed when reporting is on

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        release=os.environ.get("GITHUB_SHA"),  # the commit that ran, in GitHub Actions
        send_default_pii=False,                # no personal data: there is none in this project anyway
        traces_sample_rate=0,                  # errors only, no performance tracing
    )
    sentry_sdk.set_tag("component", component)
    return True
