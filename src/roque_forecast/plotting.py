"""One consistent look for every figure in the project.

Colours come from a colour-blind-safe categorical palette, used in a FIXED
order (series 1 is always blue, series 2 always orange...). Grid and axes are
light so the data stand out; text is dark grey, never coloured.
"""

import matplotlib.pyplot as plt

from roque_forecast import config

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"

# Categorical slots, in order (validated for colour-vision deficiencies).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# Single-hue blue ramp (light -> dark) for magnitudes such as heatmaps.
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

FIGURES_DIR = config.PROJECT_DIR / "reports" / "figures"


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "font.size": 10,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEXT_SECONDARY,
        "axes.titlecolor": TEXT_PRIMARY,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEXT_SECONDARY,
        "ytick.color": TEXT_SECONDARY,
        "axes.prop_cycle": plt.cycler(color=SERIES),
        "lines.linewidth": 2,
        "legend.frameon": False,
        "legend.labelcolor": TEXT_PRIMARY,
    })


def save(fig, name: str) -> None:
    """Save a figure as PNG in reports/figures/ (used by the README)."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / f"{name}.png", bbox_inches="tight")
