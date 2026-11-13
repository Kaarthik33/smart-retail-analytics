"""Shared chart styling so every figure in the report looks like one system."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
NEUTRAL = "#c3c2b7"

STATUS = {"Reorder now": "#d03b3b", "Healthy": "#0ca30c", "Overstocked": "#fab219"}

# below average -> neutral -> above average
DIVERGING = LinearSegmentedColormap.from_list("retail_div", [ORANGE, "#f0efec", BLUE])


def apply_style() -> None:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.family": "DejaVu Sans", "font.size": 10,
        "text.color": INK, "axes.labelcolor": INK_SECONDARY,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelcolor": INK_SECONDARY, "ytick.labelcolor": INK_SECONDARY,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.titlepad": 14, "legend.frameon": False, "lines.linewidth": 2,
    })


def new_figure(width: float = 9, height: float = 4.8):
    apply_style()
    return plt.subplots(figsize=(width, height))


def titled(ax, title: str, subtitle: str | None = None) -> None:
    ax.set_title(title, pad=26 if subtitle else 14)
    if subtitle:
        ax.text(0, 1.03, subtitle, transform=ax.transAxes, color=INK_SECONDARY, fontsize=9.5)


def hbar(ax, labels, values, color=BLUE, fmt="{:,.0f}") -> None:
    """Horizontal bars, largest on top, with a value label at each bar end."""
    labels, values = list(labels)[::-1], list(values)[::-1]
    bars = ax.barh(labels, values, color=color, height=0.62)
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.bar_label(bars, labels=[fmt.format(v) for v in values], padding=4,
                 color=INK_SECONDARY, fontsize=9)
    ax.set_xlim(0, max(values) * 1.13)


def save(fig, path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
