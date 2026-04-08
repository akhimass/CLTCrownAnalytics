# viz/conflict_calendar.py
"""
Calendar heatmap showing Crown home games and same-night FC/Knights conflicts.
"""
import logging
import calendar
from datetime import date, datetime

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from config.settings import settings
from pipelines.build_master_calendar import (
    CROWN_HOME_GAMES, FC_2026_HOME, build_master
)

logger = logging.getLogger(__name__)

# Crown home cells only (four conflict types). Non–Crown days use BLANK.
HOME_CONFLICT_COLORS = {
    "NONE":          "#6B4FB8",   # purple — no same-night FC or Knights
    "FC_ONLY":       "#378ADD",   # blue — Charlotte FC home same night only
    "KNIGHTS_ONLY":  "#1D9E75",   # teal — Knights home same night only
    "BOTH":          "#E24B4A",   # red — FC and Knights both home
    "BLANK":         "#F5F5F2",   # other calendar days
}


def _crown_conflict_category(fc_same_day: int, knights_same_day: int) -> str:
    if fc_same_day and knights_same_day:
        return "BOTH"
    if fc_same_day:
        return "FC_ONLY"
    if knights_same_day:
        return "KNIGHTS_ONLY"
    return "NONE"


def plot_conflict_calendar(save: bool = True) -> plt.Figure:
    """
    Monthly calendar grid for May–August 2026.
    Only Crown home dates are colored — four conflict categories vs same-night FC/Knights.
    """
    fc_dates = {datetime.strptime(g["date"], "%Y-%m-%d").date() for g in FC_2026_HOME}
    knights_dates: set = set()
    kn_path = settings.DATA_PROCESSED / "knights_games.csv"
    if kn_path.exists():
        kdf = pd.read_csv(kn_path, parse_dates=["date"])
        if "season" in kdf.columns:
            kdf = kdf[kdf["season"] == 2026]
        knights_dates = set(pd.to_datetime(kdf["date"]).dt.date.dropna())

    crown_conflict: dict = {}
    try:
        master = build_master(save=False)
        for _, row in master.iterrows():
            d = pd.Timestamp(row["date"]).date()
            fc_sd = int(row.get("fc_same_day", 0) or 0)
            kn_sd = int(row.get("knights_same_day", 0) or 0)
            crown_conflict[d] = _crown_conflict_category(fc_sd, kn_sd)
    except Exception:
        for g in CROWN_HOME_GAMES:
            d = datetime.strptime(g["date"], "%Y-%m-%d").date()
            crown_conflict[d] = _crown_conflict_category(
                int(d in fc_dates),
                int(d in knights_dates),
            )

    months = [(2026, 5), (2026, 6), (2026, 7), (2026, 8)]
    month_names = ["May 2026", "June 2026", "July 2026", "August 2026"]

    fig, axes = plt.subplots(2, 2, figsize=(12.5, 7.2))
    axes = axes.flatten()

    for ax, (year, month), mname in zip(axes, months, month_names):
        _draw_month(ax, year, month, mname, crown_conflict)

    # Tight grids + margin reserved for legend below (no overlap with months)
    fig.subplots_adjust(left=0.04, right=0.98, top=0.84, bottom=0.20, hspace=0.12, wspace=0.06)

    legend_items = [
        mpatches.Patch(color=HOME_CONFLICT_COLORS["NONE"], label="Crown home — no conflict (purple)"),
        mpatches.Patch(color=HOME_CONFLICT_COLORS["FC_ONLY"], label="Crown home — FC same night only (blue)"),
        mpatches.Patch(color=HOME_CONFLICT_COLORS["KNIGHTS_ONLY"], label="Crown home — Knights same night only (teal)"),
        mpatches.Patch(color=HOME_CONFLICT_COLORS["BOTH"], label="Crown home — FC + Knights same night (red; none yet)"),
        mpatches.Patch(color=HOME_CONFLICT_COLORS["BLANK"], label="No Crown home game"),
    ]
    fig.legend(
        handles=legend_items,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.10),
        ncol=3,
        fontsize=7.8,
        frameon=True,
        fancybox=False,
        edgecolor="#ccc",
    )
    fig.suptitle(
        "Charlotte Crown 2026 — Home calendar (same-night conflicts with FC / Knights)",
        fontsize=13,
        fontweight="bold",
        y=0.97,
    )
    fig.text(
        0.5,
        0.908,
        "Purple = clean night · Blue = FC home same date · Teal = Knights (Truist) home same date · Red = both. "
        "Current seeds: no Crown night has FC + Truist Knights together — no red cells.",
        ha="center",
        fontsize=7.5,
        color="#444",
    )

    if save:
        path = settings.REPORTS_DIR / "11_conflict_calendar.png"
        fig.savefig(path, dpi=150, bbox_inches=None, facecolor="white")
        logger.info(f"Saved → {path}")
    return fig


def _draw_month(ax, year: int, month: int, title: str, crown_conflict: dict):
    cal = calendar.monthcalendar(year, month)
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    ax.set_xlim(0, 7)
    ax.set_ylim(0, len(cal) + 1)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(title, fontsize=11, fontweight="bold", pad=4)

    for i, dl in enumerate(day_labels):
        ax.text(i + 0.5, len(cal) + 0.5, dl, ha="center", va="center",
                fontsize=7.5, color="#666", fontweight="bold")

    for row_i, week in enumerate(cal):
        for col_i, day_num in enumerate(week):
            if day_num == 0:
                continue
            d = date(year, month, day_num)
            x, y = col_i, len(cal) - row_i - 1

            if d in crown_conflict:
                cat = crown_conflict[d]
                bg_color = HOME_CONFLICT_COLORS.get(cat, HOME_CONFLICT_COLORS["NONE"])
                text_color = "white"
                bold = True
            else:
                bg_color = HOME_CONFLICT_COLORS["BLANK"]
                text_color = "#444"
                bold = False

            rect = mpatches.FancyBboxPatch(
                (x + 0.05, y + 0.05), 0.9, 0.9,
                boxstyle="round,pad=0.05",
                facecolor=bg_color, edgecolor="white", linewidth=1.2,
            )
            ax.add_patch(rect)
            ax.text(
                x + 0.5, y + 0.5, str(day_num),
                ha="center", va="center",
                fontsize=9, color=text_color,
                fontweight="bold" if bold else "normal",
            )


def plot_schedule_table(save: bool = True) -> plt.Figure:
    """Clean tabular view of all Crown home games with conflict details."""
    try:
        master = build_master(save=False)
    except Exception:
        master = pd.DataFrame(CROWN_HOME_GAMES)
        master["conflict_risk"] = "UNKNOWN"
        master["fc_same_day"] = 0
        master["knights_same_day"] = 0

    display_cols = {
        "date": "Date",
        "opponent": "Opponent",
        "hour": "Time",
        "conflict_risk": "Risk",
        "fc_same_day": "FC Same Night",
        "knights_same_day": "Knights Same Night",
        "cannibalization_pct": "Cannibal. %",
    }

    available = {k: v for k, v in display_cols.items() if k in master.columns}
    df = master[list(available.keys())].rename(columns=available).copy()

    if "Time" in df.columns:
        df["Time"] = df["Time"].apply(lambda h: f"{h}:00" if pd.notna(h) else "TBD")
    if "Cannibal. %" in df.columns:
        df["Cannibal. %"] = df["Cannibal. %"].apply(
            lambda x: f"{x:.0f}%" if pd.notna(x) else "0%"
        )

    fig, ax = plt.subplots(figsize=(13, 8))
    ax.axis("off")

    tbl = ax.table(
        cellText=df.values,
        colLabels=df.columns,
        cellLoc="center",
        loc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.auto_set_column_width(range(len(df.columns)))

    # Color rows by risk
    risk_col_idx = list(df.columns).index("Risk") if "Risk" in df.columns else None
    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor("#2C2C2A")
            cell.set_text_props(color="white", fontweight="bold")
        elif risk_col_idx is not None and col == risk_col_idx:
            risk_val = df.iloc[row - 1]["Risk"] if row <= len(df) else ""
            risk_map = {"HIGH": "#FCEBEB", "MODERATE": "#FAEEDA", "LOW": "#EAF3DE"}
            cell.set_facecolor(risk_map.get(str(risk_val), "white"))
        else:
            cell.set_facecolor("#FAFAF9" if row % 2 == 0 else "white")

    ax.set_title("Charlotte Crown 2026 — Full home schedule with conflict analysis",
                 fontsize=12, pad=12)
    plt.tight_layout()

    if save:
        path = settings.REPORTS_DIR / "12_schedule_table.png"
        fig.savefig(path, bbox_inches="tight")
        logger.info(f"Saved → {path}")
    return fig


def plot_all():
    plot_conflict_calendar()
    plot_schedule_table()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    plot_all()
