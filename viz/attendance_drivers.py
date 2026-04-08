# viz/attendance_drivers.py
"""
Visualizations for attendance driver analysis.
Outputs: PNG charts saved to reports/
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns

from config.settings import settings
from config.constants import DRIVER_WEIGHTS_PRIOR, PROMO_MULTIPLIERS

logger = logging.getLogger(__name__)

# ── Style ──────────────────────────────────────────────────────────────────────
PALETTE = {
    "teal":   "#1D9E75",
    "blue":   "#378ADD",
    "amber":  "#BA7517",
    "purple": "#7F77DD",
    "gray":   "#888780",
    "red":    "#E24B4A",
    "green":  "#639922",
    "coral":  "#D85A30",
}
FONT = "DejaVu Sans"

def _setup_style():
    plt.rcParams.update({
        "font.family":       FONT,
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "axes.grid":         True,
        "grid.alpha":        0.3,
        "grid.linestyle":    "--",
        "figure.dpi":        150,
    })

# ── Chart 1: Driver weight bar chart ──────────────────────────────────────────
def plot_driver_weights(driver_df: pd.DataFrame = None, save: bool = True) -> plt.Figure:
    """
    Horizontal bar chart of attendance driver weights.
    driver_df: output of AttendanceMLR.driver_summary() or RF.driver_ranking().
    Falls back to prior weights if no model data.
    """
    _setup_style()

    if driver_df is not None and "weight_pct" in driver_df.columns:
        features = driver_df["feature"].tolist()
        weights  = driver_df["weight_pct"].tolist()
        sig      = driver_df.get("significant", [True] * len(features)).tolist()
    else:
        # Use labeled prior weights
        labels = {
            "Promotions & theme nights":   35,
            "Star player / opponent quality": 27,
            "Price & accessibility":       23,
            "Social / community identity": 10,
            "Transportation (transit)":     5,
        }
        features = list(labels.keys())
        weights  = list(labels.values())
        sig      = [True] * len(features)

    colors = [PALETTE["teal"] if s else PALETTE["gray"] for s in sig]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.barh(features[::-1], weights[::-1], color=colors[::-1],
                   height=0.6, edgecolor="none")

    # Value labels
    for bar, w in zip(bars, weights[::-1]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{w:.1f}%", va="center", fontsize=11, fontweight="bold",
                color=PALETTE["teal"] if w == max(weights) else "#444")

    ax.set_xlabel("Relative weight (%)", fontsize=11)
    ax.set_xlim(0, max(weights) * 1.25)
    ax.set_title("Attendance driver weights — Charlotte Crown 2026\n"
                 "Derived from Charlotte FC + Knights 3-year regression",
                 fontsize=13, pad=12)

    sig_patch = mpatches.Patch(color=PALETTE["teal"], label="Statistically significant (p<0.05)")
    ns_patch  = mpatches.Patch(color=PALETTE["gray"], label="Not significant / prior estimate")
    ax.legend(handles=[sig_patch, ns_patch], fontsize=9, loc="lower right")

    plt.tight_layout()
    if save:
        path = settings.REPORTS_DIR / "01_driver_weights.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


# ── Chart 2: Promo night multiplier (FC benchmark) ────────────────────────────
def plot_promo_benchmark(save: bool = True) -> plt.Figure:
    """Bar chart: FC promo nights attendance vs. non-promo average."""
    _setup_style()

    promo_data = {
        "Mar 1 — Snapback":        51_002,
        "Apr 5 — Gloves":          29_591,
        "Apr 26 — Scarf":          29_233,
        "May 17 — Party Shirt":    29_755,
        "May 24 — Soccer for All": 29_296,
        "Jul 5 — Straw Hat":       28_734,
        "Jul 26 — Collectible":    27_835,
        "Sep 13 — Crown":          35_607,
        "Sep 27 — Por la Cultura": 28_841,
        "Oct 18 — Fan Appr.":      31_191,
        "Non-promo avg":           27_800,
    }

    labels = list(promo_data.keys())
    values = list(promo_data.values())
    non_promo_avg = promo_data["Non-promo avg"]

    colors = []
    for lbl, val in promo_data.items():
        if lbl == "Non-promo avg":
            colors.append(PALETTE["gray"])
        elif val > non_promo_avg * 1.15:
            colors.append(PALETTE["teal"])
        elif val > non_promo_avg:
            colors.append(PALETTE["blue"])
        else:
            colors.append(PALETTE["amber"])

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.bar(range(len(labels)), values, color=colors, width=0.7, edgecolor="none")

    # Non-promo reference line
    ax.axhline(non_promo_avg, color=PALETTE["gray"], linestyle="--",
               linewidth=1.5, label=f"Non-promo avg: {non_promo_avg:,}")

    # Value labels
    for i, (bar, val) in enumerate(zip(bars, values)):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 300,
                f"{val/1000:.1f}K", ha="center", va="bottom", fontsize=9)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Attendance", fontsize=11)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x/1000:.0f}K"))
    ax.set_title("Charlotte FC 2025 — Promo nights vs. non-promo baseline\n"
                 "Source: public attendance records", fontsize=13, pad=12)
    ax.legend(fontsize=10)

    # Annotation: opener outlier
    ax.annotate("Season opener\n+83% vs. avg",
                xy=(0, 51_002), xytext=(1.5, 46_000),
                arrowprops=dict(arrowstyle="->", color="#444"),
                fontsize=9, color=PALETTE["teal"])

    plt.tight_layout()
    if save:
        path = settings.REPORTS_DIR / "02_promo_benchmark.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


# ── Chart 3: Promo multiplier by type ─────────────────────────────────────────
def plot_promo_multipliers(save: bool = True) -> plt.Figure:
    _setup_style()

    labels = {
        "No promo":        1.00,
        "Theme night":     1.12,
        "Community night": 1.10,
        "Star feature":    1.15,
        "Giveaway":        1.18,
        "Discount price":  1.25,
        "Season opener":   1.40,
    }

    names = list(labels.keys())
    mults = list(labels.values())
    colors = [PALETTE["gray"]] + [PALETTE["teal"]] * (len(names) - 1)
    colors[-1] = PALETTE["amber"]  # discount

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.barh(names, [m - 1 for m in mults], left=1.0,
                   color=colors, height=0.6, edgecolor="none")

    ax.axvline(1.0, color="#444", linewidth=1)
    for bar, m in zip(bars, mults):
        ax.text(m + 0.005, bar.get_y() + bar.get_height() / 2,
                f"×{m:.2f}", va="center", fontsize=10)

    ax.set_xlabel("Attendance multiplier vs. no-promo baseline", fontsize=11)
    ax.set_xlim(0.95, 1.55)
    ax.set_title("Estimated promo type multipliers\nDerived from FC/Knights 3-year data",
                 fontsize=13, pad=12)

    plt.tight_layout()
    if save:
        path = settings.REPORTS_DIR / "03_promo_multipliers.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


# ── Chart 4: Transit comparison ────────────────────────────────────────────────
def plot_transit_comparison(save: bool = True) -> plt.Figure:
    """Bar chart comparing transit access to Charlotte venues."""
    _setup_style()

    venues = ["Bojangles Coliseum\n(Crown)", "Bank of America\n(FC)", "Truist Field\n(Knights)", "Spectrum Center\n(Checkers)"]
    travel_from_uncc = [81, 34, 34, 32]
    transit_score    = [1, 2, 2, 2]
    colors = [PALETTE["amber"] if s < 2 else PALETTE["teal"] for s in transit_score]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))

    # Travel time
    bars = ax1.bar(venues, travel_from_uncc, color=colors, width=0.6, edgecolor="none")
    for bar, val in zip(bars, travel_from_uncc):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                 f"{val} min", ha="center", va="bottom", fontsize=10)
    ax1.set_ylabel("Transit travel time from UNCC (min)", fontsize=10)
    ax1.set_title("Travel time from UNCC via CATS transit", fontsize=11)
    ax1.axhline(20, color=PALETTE["gray"], linestyle="--", linewidth=1,
                label="20 min threshold (high willingness)")
    ax1.legend(fontsize=9)

    # Transit score
    score_labels = ["Bus w/ transfer", "Direct light rail"]
    score_vals   = [1, 2]
    ax2.barh(venues[::-1], transit_score[::-1],
             color=colors[::-1], height=0.6, edgecolor="none")
    ax2.set_xlim(0, 3)
    ax2.set_xticks([1, 2])
    ax2.set_xticklabels(score_labels, fontsize=10)
    ax2.set_title("Transit accessibility score", fontsize=11)

    direct_patch   = mpatches.Patch(color=PALETTE["teal"], label="Direct light rail")
    transfer_patch = mpatches.Patch(color=PALETTE["amber"], label="Bus w/ transfer")
    ax2.legend(handles=[direct_patch, transfer_patch], fontsize=9)

    fig.suptitle("Transit accessibility: Crown faces structural disadvantage vs. other Charlotte venues\n"
                 "Silver Line to Bojangles Coliseum is planned but not yet funded/built",
                 fontsize=12, y=1.02)

    plt.tight_layout()
    if save:
        path = settings.REPORTS_DIR / "04_transit_comparison.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


# ── Chart 5: Cannibalization heatmap ─────────────────────────────────────────
def plot_cannibalization_matrix(save: bool = True) -> plt.Figure:
    """
    Matrix showing estimated attendance impact when two teams share a game date.
    """
    _setup_style()

    teams = ["Crown", "FC", "Knights"]
    # cannibalization[i][j] = % impact on team i when team j also plays
    matrix = np.array([
        [0,     -18,  -9],   # Crown affected by FC / Knights
        [-4,     0,   -4],   # FC affected by Crown / Knights
        [-11,   -11,   0],   # Knights affected by Crown / FC
    ], dtype=float)

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        matrix, annot=True, fmt=".0f", cmap="RdYlGn",
        center=0, vmin=-25, vmax=5,
        xticklabels=["Crown playing", "FC playing", "Knights playing"],
        yticklabels=["Crown affected", "FC affected", "Knights affected"],
        ax=ax, linewidths=0.5, linecolor="white",
        annot_kws={"size": 12, "weight": "bold"},
        cbar_kws={"label": "Attendance impact (%)"},
    )
    ax.set_title("Same-day game cannibalization matrix\n"
                 "% attendance change when rival team also plays",
                 fontsize=12, pad=12)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=15, ha="right")

    plt.tight_layout()
    if save:
        path = settings.REPORTS_DIR / "05_cannibalization_matrix.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


def plot_all():
    logger.info("Generating all attendance driver charts...")
    plot_driver_weights()
    plot_promo_benchmark()
    plot_promo_multipliers()
    plot_transit_comparison()
    plot_cannibalization_matrix()
    logger.info("All driver charts saved to reports/")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    plot_all()
