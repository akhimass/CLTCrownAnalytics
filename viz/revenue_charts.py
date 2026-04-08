# viz/revenue_charts.py
"""
Before/After revenue visualizations.
Outputs charts to reports/ directory.
"""
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.patches import FancyBboxPatch
import seaborn as sns

from config.settings import settings
from config.constants import SHUTTLE_COST_PER_GAME, CROWN_HOME_GAMES
from models.revenue_model import RevenueModel, CAPACITY
from pipelines.transit_features import shuttle_impact_estimate

logger = logging.getLogger(__name__)

PALETTE = {
    "gray":   "#888780",
    "teal":   "#1D9E75",
    "green":  "#639922",
    "amber":  "#BA7517",
    "blue":   "#378ADD",
    "red":    "#E24B4A",
    "purple": "#7F77DD",
}

def _setup_style():
    plt.rcParams.update({
        "font.family":       "DejaVu Sans",
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "axes.grid":         True,
        "grid.alpha":        0.25,
        "grid.linestyle":    "--",
        "figure.dpi":        150,
    })


# ── Chart 1: Scenario summary — stacked bar ────────────────────────────────────
def plot_scenario_comparison(model: RevenueModel = None, save: bool = True) -> plt.Figure:
    _setup_style()
    if model is None:
        model = RevenueModel()
        model.run_all()

    summary = pd.DataFrame([s.to_dict() for s in model.scenarios.values()])
    scenarios   = summary["scenario"].tolist()
    ticket_rev  = summary["ticket_revenue"].tolist()
    anc_rev     = summary["ancillary_revenue"].tolist()
    total_rev   = summary["total_revenue"].tolist()

    x = np.arange(len(scenarios))
    width = 0.5

    fig, ax = plt.subplots(figsize=(9, 5))
    bars1 = ax.bar(x, ticket_rev, width, label="Ticket revenue",
                   color=PALETTE["blue"], edgecolor="none")
    bars2 = ax.bar(x, anc_rev, width, bottom=ticket_rev, label="Ancillary (concessions + merch)",
                   color=PALETTE["teal"], edgecolor="none")

    # Total labels
    for xi, total in zip(x, total_rev):
        ax.text(xi, total + 1_500, f"${total:,.0f}", ha="center",
                fontsize=11, fontweight="bold", color="#222")

    # Uplift annotations
    base = total_rev[0]
    for xi, total in zip(x[1:], total_rev[1:]):
        uplift = total - base
        pct    = uplift / base * 100
        ax.annotate(f"+${uplift:,.0f}\n(+{pct:.0f}%)",
                    xy=(xi, total + 6_000), ha="center",
                    fontsize=9, color=PALETTE["teal"])

    ax.set_xticks(x)
    ax.set_xticklabels(scenarios, fontsize=10)
    ax.set_ylabel("Season revenue ($)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title("Charlotte Crown 2026 — Season revenue by scenario\n17 home games, Bojangles Coliseum (~3,500 capacity)",
                 fontsize=12, pad=12)
    ax.legend(fontsize=10, loc="upper left")
    plt.tight_layout()

    if save:
        path = settings.REPORTS_DIR / "06_scenario_comparison.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


# ── Chart 2: Game-by-game attendance projection ────────────────────────────────
def plot_game_by_game(model: RevenueModel = None, save: bool = True) -> plt.Figure:
    _setup_style()
    if model is None:
        model = RevenueModel()
        model.run_all()

    game_df = model.game_level_comparison()
    dates   = game_df[game_df["scenario"] == "baseline"]["date"].tolist()
    x       = np.arange(len(dates))
    width   = 0.28

    fig, (ax_att, ax_rev) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    for i, (sname, color, label) in enumerate([
        ("baseline",   PALETTE["gray"],  "Baseline"),
        ("strategy_a", PALETTE["blue"],  "Strategy A"),
        ("strategy_b", PALETTE["teal"],  "Strategy B (+ Shuttle)"),
    ]):
        sub = game_df[game_df["scenario"] == sname]
        att = sub["attendance"].tolist()
        rev = sub["total_revenue"].tolist()
        offset = (i - 1) * width
        ax_att.bar(x + offset, att, width * 0.9, label=label, color=color, edgecolor="none", alpha=0.9)
        ax_rev.bar(x + offset, rev, width * 0.9, label=label, color=color, edgecolor="none", alpha=0.9)

    # Conflict markers on attendance chart
    conflict_indices = []
    base_games = game_df[game_df["scenario"] == "baseline"]
    for j, (_, row) in enumerate(base_games.iterrows()):
        if row["has_conflict"]:
            conflict_indices.append(j)
            ax_att.axvspan(j - 0.5, j + 0.5, alpha=0.08, color=PALETTE["red"], zorder=0)

    ax_att.set_ylabel("Attendance", fontsize=11)
    ax_att.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax_att.axhline(CAPACITY, color=PALETTE["amber"], linestyle="--",
                   linewidth=1.2, label="Venue capacity (3,500)")
    ax_att.legend(fontsize=9, ncol=4)
    ax_att.set_title("Game-by-game attendance projection (shaded = conflict night)", fontsize=12)

    ax_rev.set_ylabel("Game revenue ($)", fontsize=11)
    ax_rev.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax_rev.set_xticks(x)

    short_dates = [d[5:] for d in dates]  # MM-DD only
    ax_rev.set_xticklabels(short_dates, rotation=45, ha="right", fontsize=8)
    ax_rev.legend(fontsize=9, ncol=3)
    ax_rev.set_title("Game-by-game revenue projection", fontsize=12)

    fig.suptitle("Charlotte Crown 2026 — Projected game-level performance\nAll 17 home games",
                 fontsize=13, y=1.01)
    plt.tight_layout()

    if save:
        path = settings.REPORTS_DIR / "07_game_by_game.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


# ── Chart 3: Fill rate waterfall ─────────────────────────────────────────────
def plot_fill_rate_waterfall(model: RevenueModel = None, save: bool = True) -> plt.Figure:
    _setup_style()
    if model is None:
        model = RevenueModel()
        model.run_all()

    steps = [
        ("Baseline\nfill rate",        0.50, PALETTE["gray"],  "start"),
        ("+ Promo calendar",           0.08, PALETTE["teal"],  "add"),
        ("+ Giveaway nights",          0.04, PALETTE["teal"],  "add"),
        ("− Conflict penalties",      -0.03, PALETTE["red"],   "sub"),
        ("+ Pricing bundles\n(group)", 0.03, PALETTE["blue"],  "add"),
        ("+ Star player nights",       0.02, PALETTE["blue"],  "add"),
        ("+ Shuttle / transit",        0.04, PALETTE["green"], "add"),
        ("Strategy B\nfill rate",      None, PALETTE["amber"], "total"),
    ]

    running = 0.50
    bottoms = []
    heights = []
    for label, delta, color, kind in steps:
        if kind == "start":
            bottoms.append(0)
            heights.append(running)
        elif kind == "total":
            bottoms.append(0)
            heights.append(running)
        elif kind == "add":
            bottoms.append(running)
            heights.append(delta)
            running += delta
        else:  # sub
            running += delta
            bottoms.append(running)
            heights.append(-delta)

    labels = [s[0] for s in steps]
    colors = [s[2] for s in steps]

    fig, ax = plt.subplots(figsize=(11, 5))
    bars = ax.bar(range(len(steps)), heights, bottom=bottoms,
                  color=colors, width=0.6, edgecolor="none")

    # Connector lines
    for i in range(len(steps) - 1):
        top_i = bottoms[i] + heights[i]
        ax.plot([i + 0.3, i + 0.7], [top_i, top_i],
                color="#999", linewidth=0.8, linestyle="--")

    # Value labels
    for i, (bar, b, h) in enumerate(zip(bars, bottoms, heights)):
        top = b + h
        label_y = top + 0.005 if h >= 0 else b - 0.02
        kind = steps[i][3]
        if kind in ("start", "total"):
            ax.text(i, top + 0.01, f"{top:.0%}", ha="center",
                    fontsize=10, fontweight="bold")
        else:
            sign = "+" if h > 0 else ""
            ax.text(i, label_y, f"{sign}{h:.0%}", ha="center",
                    fontsize=9, color=colors[i])

    ax.set_xticks(range(len(steps)))
    ax.set_xticklabels(labels, fontsize=9)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylim(0, 0.95)
    ax.set_ylabel("Venue fill rate", fontsize=11)
    ax.set_title("Fill rate waterfall: Baseline → Strategy B\nHow each lever contributes to attendance growth",
                 fontsize=12, pad=12)

    plt.tight_layout()
    if save:
        path = settings.REPORTS_DIR / "08_fill_rate_waterfall.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


# ── Chart 4: Revenue drivers breakdown (pie-ish donut) ─────────────────────────
def plot_revenue_breakdown(model: RevenueModel = None, save: bool = True) -> plt.Figure:
    _setup_style()
    if model is None:
        model = RevenueModel()
        model.run_all()

    base = model.scenarios["baseline"]
    strat_b = model.scenarios["strategy_b"]

    fig, axes = plt.subplots(1, 2, figsize=(10, 5))

    for ax, scenario, title in [
        (axes[0], base,    "Baseline (no strategy)"),
        (axes[1], strat_b, "Strategy B (full program)"),
    ]:
        sizes  = [scenario.ticket_revenue, scenario.ancillary_revenue]
        labels = [f"Ticket revenue\n${scenario.ticket_revenue:,.0f}",
                  f"Ancillary\n${scenario.ancillary_revenue:,.0f}"]
        colors = [PALETTE["blue"], PALETTE["teal"]]

        wedges, texts = ax.pie(
            sizes, labels=labels, colors=colors, startangle=90,
            wedgeprops={"edgecolor": "white", "linewidth": 2},
            textprops={"fontsize": 10},
        )
        ax.set_title(f"{title}\nTotal: ${scenario.total_revenue:,.0f}", fontsize=11)

    fig.suptitle("Revenue composition: baseline vs. full strategy", fontsize=13)
    plt.tight_layout()

    if save:
        path = settings.REPORTS_DIR / "09_revenue_breakdown.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


# ── Chart 5: Conflict impact on Crown revenue ─────────────────────────────────
def plot_shuttle_roi(save: bool = True) -> plt.Figure:
    """
    Bar chart: shuttle operating cost vs. incremental gross revenue (per game and season).

    Uses `shuttle_impact_estimate` defaults; labels net ROI from the same calculation.
    """
    _setup_style()
    est = shuttle_impact_estimate(games_per_season=CROWN_HOME_GAMES)
    per_game_cost = SHUTTLE_COST_PER_GAME
    per_game_gross = est["gross_revenue_uplift"] / CROWN_HOME_GAMES
    season_cost = est["season_shuttle_cost"]
    season_gross = est["gross_revenue_uplift"]

    labels = ["Per game", "Season total"]
    costs = [per_game_cost, season_cost]
    revs = [per_game_gross, season_gross]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width / 2, costs, width, label="Shuttle cost", color=PALETTE["red"], edgecolor="none")
    ax.bar(x + width / 2, revs, width, label="Incremental gross revenue", color=PALETTE["teal"], edgecolor="none")

    for i, (c, r) in enumerate(zip(costs, revs)):
        ax.text(i - width / 2, c + max(costs) * 0.02, f"${c:,.0f}", ha="center", fontsize=9)
        ax.text(i + width / 2, r + max(revs) * 0.02, f"${r:,.0f}", ha="center", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_ylabel("Dollars ($)")
    ax.set_title(
        "Blue Line shuttle economics — cost vs. incremental revenue\n"
        f"Net ROI ≈ {est['roi_pct']:.0f}% (charter cost vs. ticket + ancillary uplift)",
        fontsize=12,
        pad=12,
    )
    ax.legend(loc="upper left")
    ax.annotate(
        f"{est['roi_pct']:.0f}% ROI",
        xy=(0.98, 0.92),
        xycoords="axes fraction",
        ha="right",
        fontsize=14,
        fontweight="bold",
        color=PALETTE["teal"],
    )

    plt.tight_layout()
    if save:
        path = settings.REPORTS_DIR / "13_shuttle_roi.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


def plot_driver_comparison_mlr_vs_rf(mlr=None, rf=None, save: bool = True) -> plt.Figure:
    """
    Side-by-side normalized driver weights: MLR |coefficient| share vs. RF avg importance share.
    """
    _setup_style()
    from models.attendance_mlr import AttendanceMLR
    from models.random_forest_model import AttendanceRF

    if mlr is None:
        mlr = AttendanceMLR()
        pkl = settings.DATA_PROCESSED / "mlr_model.pkl"
        if pkl.exists():
            try:
                mlr = AttendanceMLR.load(pkl)
            except Exception:
                mlr = AttendanceMLR()
        if not getattr(mlr, "trained", False):
            mlr.fit()
    if rf is None:
        rf = AttendanceRF()
        pkl = settings.DATA_PROCESSED / "rf_model.pkl"
        if pkl.exists():
            try:
                rf = AttendanceRF.load(pkl)
            except Exception:
                rf = AttendanceRF()
        if not getattr(rf, "trained", False):
            rf.fit(mlr.load_training_data())

    mdf = mlr.driver_summary()[["feature", "weight_pct"]].rename(
        columns={"weight_pct": "mlr_weight_pct"}
    )
    rdf = rf.driver_ranking()[["feature", "weight_pct"]].rename(
        columns={"weight_pct": "rf_weight_pct"}
    )
    merged = mdf.merge(rdf, on="feature", how="outer").fillna(0)
    merged = merged.sort_values("mlr_weight_pct", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 6))
    y = np.arange(len(merged))
    h = 0.35
    ax.barh(y - h / 2, merged["mlr_weight_pct"], h, label="MLR |coef| share (%)", color=PALETTE["blue"], edgecolor="none")
    ax.barh(y + h / 2, merged["rf_weight_pct"], h, label="RF importance share (%)", color=PALETTE["amber"], edgecolor="none")
    ax.set_yticks(y)
    ax.set_yticklabels(merged["feature"])
    ax.set_xlabel("Relative weight (%)")
    ax.set_title(
        "Driver ranking agreement — MLR vs. Random Forest\n"
        "Both models should rank the same levers first even if magnitudes differ",
        fontsize=12,
        pad=12,
    )
    ax.legend(loc="lower right")

    plt.tight_layout()
    if save:
        path = settings.REPORTS_DIR / "14_driver_mlr_vs_rf.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


def plot_conflict_revenue_impact(model: RevenueModel = None, save: bool = True) -> plt.Figure:
    _setup_style()
    if model is None:
        model = RevenueModel()
        model.run_all()

    game_df = model.game_level_comparison()
    strat_a = game_df[game_df["scenario"] == "strategy_a"].copy()

    fig, ax = plt.subplots(figsize=(10, 4))

    conflict_games = strat_a[strat_a["has_conflict"] == True]
    clean_games    = strat_a[strat_a["has_conflict"] == False]

    ax.scatter(
        range(len(clean_games)),
        clean_games["total_revenue"],
        color=PALETTE["teal"], s=80, label="No conflict", zorder=5, alpha=0.85,
    )
    ax.scatter(
        [list(strat_a["date"]).index(d) for d in conflict_games["date"]],
        conflict_games["total_revenue"],
        color=PALETTE["red"], s=100, marker="X", label="Conflict night", zorder=6,
    )

    # Mean lines
    ax.axhline(clean_games["total_revenue"].mean(), color=PALETTE["teal"],
               linestyle="--", linewidth=1, alpha=0.6, label=f"Clean avg: ${clean_games['total_revenue'].mean():,.0f}")
    ax.axhline(conflict_games["total_revenue"].mean(), color=PALETTE["red"],
               linestyle="--", linewidth=1, alpha=0.6, label=f"Conflict avg: ${conflict_games['total_revenue'].mean():,.0f}")

    ax.set_xlabel("Game number (season order)", fontsize=11)
    ax.set_ylabel("Game total revenue ($)", fontsize=11)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v:,.0f}"))
    ax.set_title("Revenue impact of same-day conflict games (Strategy A scenario)",
                 fontsize=12, pad=12)
    ax.legend(fontsize=9, ncol=2)

    plt.tight_layout()
    if save:
        path = settings.REPORTS_DIR / "10_conflict_revenue_impact.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


def plot_all(model: RevenueModel = None, mlr=None, rf=None):
    if model is None:
        model = RevenueModel()
        model.run_all()
    logger.info("Generating all revenue charts...")
    plot_scenario_comparison(model)
    plot_game_by_game(model)
    plot_fill_rate_waterfall(model)
    plot_revenue_breakdown(model)
    plot_conflict_revenue_impact(model)
    plot_shuttle_roi()
    plot_driver_comparison_mlr_vs_rf(mlr=mlr, rf=rf)
    logger.info("All revenue charts saved to reports/")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    plot_all()
