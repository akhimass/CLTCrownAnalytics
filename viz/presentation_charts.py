# viz/presentation_charts.py
"""
Presentation-ready charts (16:9, 1600x900 @ 150 dpi) → reports/presentation/
Run: python -m viz.presentation_charts          # full chart library
Run: python -m viz.presentation_charts --deck5  # 5-slide deck assets only
"""
from __future__ import annotations

import logging
import shutil
import sys
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd
# Project root on path when run as script
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from config.constants import (
    COA_CONCESSION_AVG_PER_PERSON,
    COA_TICKET_ASSUMPTIONS,
    CROWN_DRIVER_WEIGHTS_PRIOR,
    DRIVER_WEIGHTS_PRIOR,
    PARKING_COSTS,
)
from config.settings import settings

logger = logging.getLogger(__name__)

PRES_DIR = settings.REPORTS_DIR / "presentation"
DPI = 150
# 1600 x 900 pixels at 150 dpi
FIG_W = 1600 / DPI
FIG_H = 900 / DPI

PALETTE = {
    "teal": "#1D9E75",
    "blue": "#378ADD",
    "amber": "#BA7517",
    "purple": "#7F77DD",
    "gray": "#888780",
    "red": "#E24B4A",
    "green": "#639922",
    "white": "#FFFFFF",
    "dark": "#2C2C2A",
}


def _presentation_rc():
    plt.rcParams.update({
        "figure.dpi": DPI,
        "savefig.dpi": DPI,
        "font.family": "DejaVu Sans",
        "font.size": 14,
        "axes.titlesize": 18,
        "axes.labelsize": 14,
        "xtick.labelsize": 14,
        "ytick.labelsize": 14,
        "legend.fontsize": 14,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "none",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.spines.bottom": False,
        "axes.grid": False,
    })


def _save(fig: plt.Figure, name: str, pad_inches: float = 0.55) -> Path:
    PRES_DIR.mkdir(parents=True, exist_ok=True)
    path = PRES_DIR / name
    fig.savefig(
        path,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
        dpi=DPI,
        pad_inches=pad_inches,
    )
    plt.close(fig)
    return path


def chart_p1_driver_weights():
    _presentation_rc()
    labels = [
        "Promotions & Theme Nights",
        "Star Player / Opponent Quality",
        "Price & Accessibility",
        "Social / Community Identity",
        "Transit / Transportation",
    ]
    keys = ["promotions", "star_power", "price", "social", "transit"]
    colors = ["#1D9E75", "#378ADD", "#BA7517", "#7F77DD", "#888780"]
    values = [DRIVER_WEIGHTS_PRIOR[k] * 100 for k in keys]
    order = np.argsort(values)[::-1]
    labels = [labels[i] for i in order]
    values = [values[i] for i in order]
    colors = [colors[i] for i in order]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0.28, right=0.96, top=0.86, bottom=0.10)
    y = np.arange(len(labels))
    bars = ax.barh(y, values, color=colors, height=0.55, edgecolor="none")
    ax.invert_yaxis()
    ax.set_xlim(0, max(values) * 1.35)
    ax.set_yticks(y)
    ax.set_yticklabels([textwrap.fill(lab, 22) for lab in labels], fontsize=12)
    for i in range(len(labels)):
        ax.get_yticklabels()[i].set_fontweight("bold" if i < 3 else "normal")
    for i, (bar, v) in enumerate(zip(bars, values)):
        w = bar.get_width()
        weight = "bold" if i < 3 else "normal"
        ax.text(w + 0.5, bar.get_y() + bar.get_height() / 2, f"{v:.0f}%",
                va="center", ha="left", fontsize=13, fontweight=weight)
    ax.set_xlabel("")
    ax.set_xticks([])
    ax.set_title(
        "What drives attendance in the Charlotte sports market\n"
        "Derived from 217 Charlotte FC + Knights home games, 2022–2025",
        fontsize=16,
        fontweight="bold",
        pad=12,
    )
    return _save(fig, "P1_driver_weights.png")


HARDCODED_FC_PROMO = {
    "2025 Opener\n(Snapback)": 51002,
    "2024 Opener\n(Patch)": 62291,
    "2024 Fan Appr.\n+ Shirt": 38259,
    "2024 Cards\nGiveaway": 36319,
    "2025 Crown\nGiveaway": 35607,
    "2024 Military\nAppreciation": 32232,
    "2025 Fan Appr.\n+ Shirt": 31191,
    "2024 Pride Night\n+ Shirt": 30468,
    "2024 Women in\nSports + Bag": 30104,
    "2025 Por la\nCultura": 28841,
    "Non-Promo\nAverage": 27800,
}


def chart_p2_fc_promo_benchmark():
    _presentation_rc()
    baseline = 27800
    path_fc = settings.DATA_PROCESSED / "fc_games.csv"
    items = []
    if path_fc.exists():
        fc = pd.read_csv(path_fc)
        if "has_promo" in fc.columns and fc["has_promo"].sum() > 0 and "promo_name" in fc.columns:
            non = fc[fc["has_promo"] == 0]
            baseline = float(non["attendance"].mean()) if len(non) else baseline
            promo = fc[fc["has_promo"] == 1].nlargest(10, "attendance")
            for _, r in promo.iterrows():
                nm = str(r["promo_name"])
                label = nm if len(nm) <= 24 else nm[:21] + "…"
                items.append((label.replace(" ", "\n", 1) if len(nm) > 18 else label, int(r["attendance"])))
    if not items:
        items = [(k, v) for k, v in HARDCODED_FC_PROMO.items() if "Non-Promo" not in k]

    items.sort(key=lambda x: x[1], reverse=True)
    labels = [textwrap.fill(x[0], 28) for x in items]
    vals = [x[1] for x in items]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0.26, right=0.98, top=0.88, bottom=0.08)
    y = np.arange(len(labels))
    colors = ["#1D9E75"] * len(labels)
    bars = ax.barh(y, vals, color=colors, height=0.5, edgecolor="none", label="Promo night")
    ax.axvline(baseline, color="#888780", linestyle="--", linewidth=2, zorder=0)
    ax.barh(len(labels), baseline, color="#888780", height=0.35, edgecolor="none", alpha=0.85)

    def fmt_k(x, _pos=None):
        if x >= 1000:
            return f"{x/1000:.0f}K"
        return f"{x:.0f}"

    xmax = max(max(vals), baseline)
    for i, (bar, v) in enumerate(zip(bars, vals)):
        lift = (v - baseline) / baseline * 100
        ax.text(v + xmax * 0.02, bar.get_y() + bar.get_height() / 2,
                f"{lift:+.0f}%", va="center", fontsize=11, fontweight="bold", color="#1a6b4e")
        ax.text(v - xmax * 0.008, bar.get_y() + bar.get_height() / 2,
                fmt_k(v), va="center", ha="right", fontsize=11, color="white", fontweight="bold")

    ax.text(baseline * 0.48, len(labels), f"Non-Promo avg\n{fmt_k(baseline)}", va="center", ha="center", fontsize=10, color="white", fontweight="bold")

    ax.set_yticks(list(range(len(labels) + 1)))
    ax.set_yticklabels(labels + ["Baseline"], fontsize=11)
    ax.invert_yaxis()
    ax.set_xlim(0, xmax * 1.32)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(fmt_k))
    ax.set_xlabel("Attendance", fontsize=13)
    ax.set_title(
        f"Charlotte FC: Promo nights consistently outperform\n"
        f"Non-promo baseline = {fmt_k(baseline)} (from processed games)",
        fontsize=15,
        fontweight="bold",
        pad=10,
    )
    return _save(fig, "P2_fc_promo_benchmark.png")


def chart_p3_promo_type_lift():
    _presentation_rc()
    promo_types = {
        "Season opener + giveaway": 65,
        "Physical giveaway": 18,
        "Theme/community night": 10,
        "No promo": 0,
    }
    labels = list(promo_types.keys())
    vals = list(promo_types.values())
    order = np.argsort(vals)[::-1]
    labels = [labels[i] for i in order]
    vals = [vals[i] for i in order]
    greens = ["#0d6b47", "#1D9E75", "#5cba8f", "#888780"]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0.30, right=0.96, top=0.88, bottom=0.14)
    y = np.arange(len(labels))
    colors = [greens[min(i, len(greens) - 1)] if v > 0 else "#888780" for i, v in enumerate(vals)]
    bars = ax.barh(y, vals, color=colors, height=0.5, edgecolor="none")
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.3 + 8)
    for bar, v in zip(bars, vals):
        ax.text(v + 2, bar.get_y() + bar.get_height() / 2, f"{v}%",
                va="center", fontsize=13, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels([textwrap.fill(lab, 26) for lab in labels], fontsize=12)
    ax.set_xlabel("% lift vs. non-promo baseline", fontsize=13)
    ax.set_title(
        "Promo type determines the magnitude of lift\n"
        "Giveaway = item fans take home (jersey, hat, towel)",
        fontsize=15,
        fontweight="bold",
        pad=10,
    )
    return _save(fig, "P3_promo_type_lift.png")


def chart_p4_cost_of_attendance():
    _presentation_rc()
    venues = {
        "Charlotte Crown\n(w/ strategy)": {"tickets": 28, "parking": 0, "concessions": 24},
        "Charlotte Knights": {"tickets": 36, "parking": 15, "concessions": 30},
        "Charlotte FC": {"tickets": 60, "parking": 35, "concessions": 44},
    }
    totals = {"Charlotte Crown\n(w/ strategy)": 52, "Charlotte Knights": 81, "Charlotte FC": 139}
    colors_c = {"tickets": "#378ADD", "parking": "#E24B4A", "concessions": "#BA7517"}

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    # Title + savings live in figure space above axes; legend below bars; footnote at bottom.
    fig.subplots_adjust(left=0.24, right=0.88, top=0.78, bottom=0.26)
    names = list(venues.keys())
    y = np.arange(len(names))
    left = np.zeros(len(names))
    for key in ("tickets", "parking", "concessions"):
        widths = [venues[n][key] for n in names]
        ax.barh(y, widths, left=left, color=colors_c[key], edgecolor="none", height=0.5, label=key.capitalize())
        left = left + widths

    bar_xmax = float(left.max())
    # Totals in a dedicated column right of bars (savings notes live in figure margin, not here).
    tot_x = bar_xmax + 10
    for yi, n in enumerate(names):
        ax.text(tot_x, yi, f"${totals[n]}", va="center", ha="left", fontsize=14, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=12)
    ax.invert_yaxis()
    ax.set_xlim(0, tot_x + 18)
    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        ncol=3,
        fontsize=11,
        frameon=False,
        handletextpad=0.9,
        columnspacing=2.0,
        handlelength=1.35,
        borderaxespad=0.5,
    )
    fig.text(
        0.5,
        0.965,
        "Crown is the best-value night out in Charlotte sports",
        ha="center",
        fontsize=15,
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.925,
        "Total cost for 2 | ticket + parking + concessions",
        ha="center",
        fontsize=12,
    )
    fig.text(
        0.5,
        0.885,
        "54% lower total cost than Charlotte FC",
        ha="center",
        fontsize=11,
        fontweight="bold",
        color="#1D9E75",
    )
    fig.text(
        0.5,
        0.852,
        "21% lower total cost than Knights",
        ha="center",
        fontsize=11,
        fontweight="bold",
        color="#BA7517",
    )
    # Parking $0: label above Crown row (offset points — no overlay on bar segments).
    crown_t = venues[names[0]]["tickets"]
    ax.annotate(
        "$0 parking",
        xy=(crown_t * 0.35, 0),
        xytext=(0, 26),
        textcoords="offset points",
        ha="center",
        fontsize=9,
        fontweight="bold",
        color="#E24B4A",
    )
    fig.text(
        0.5,
        0.07,
        "Crown: $0 parking — only major Charlotte sports venue with free parking",
        ha="center",
        va="bottom",
        fontsize=10,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#E1F5EE", edgecolor="#1D9E75"),
    )
    return _save(fig, "P4_cost_of_attendance.png")


def chart_p5_opponent_tier():
    _presentation_rc()
    path_fc = settings.DATA_PROCESSED / "fc_games.csv"
    tier_means = {1: 31339.0, 2: 34757.0, 3: 35804.0}
    tier_ns = {1: 44, 2: 7, 3: 2}
    if path_fc.exists():
        fc = pd.read_csv(path_fc)
        if "opponent_tier" in fc.columns and fc["opponent_tier"].nunique() > 1:
            g = fc.groupby("opponent_tier")["attendance"]
            tier_means = {int(k): float(v) for k, v in g.mean().items()}
            tier_ns = {int(k): int(c) for k, c in g.count().items()}

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(FIG_W, FIG_H), gridspec_kw={"width_ratios": [1.05, 1]})
    fig.subplots_adjust(left=0.08, right=0.98, top=0.82, bottom=0.12, wspace=0.28)
    tiers = sorted(tier_means.keys())
    means = [tier_means[t] for t in tiers]
    ns = [tier_ns.get(t, 0) for t in tiers]
    teals = ["#8fd4b8", "#3cb88c", "#1D9E75"]
    x = np.arange(len(tiers))
    bars = axL.bar(x, means, color=teals[: len(tiers)], edgecolor="none", width=0.55)
    axL.set_xticks(x)
    axL.set_xticklabels([f"Tier {t}" for t in tiers], fontsize=13)
    axL.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}K"))
    axL.set_ylabel("Avg attendance", fontsize=13)
    ymax = max(means) * 1.18
    axL.set_ylim(0, ymax)
    for i, (bar, m, n) in enumerate(zip(bars, means, ns)):
        axL.text(bar.get_x() + bar.get_width() / 2, m + ymax * 0.02, f"n={n}", ha="center", fontsize=11)
    if len(means) >= 2:
        d12 = (means[1] / means[0] - 1) * 100
        axL.text(
            0.5,
            (means[0] + means[1]) / 2 + ymax * 0.04,
            f"+{d12:.0f}%",
            ha="center",
            fontsize=11,
            fontweight="bold",
            color="#333",
        )
    if len(means) >= 3:
        d23 = (means[2] / means[1] - 1) * 100
        axL.text(
            1.5,
            (means[1] + means[2]) / 2 + ymax * 0.04,
            f"+{d23:.0f}%",
            ha="center",
            fontsize=11,
            fontweight="bold",
            color="#333",
        )

    axR.axis("off")
    text_lines = [
        "What drives each tier (FC)",
        "Tier 1: Standard MLS opponent",
        "Tier 2: Atlanta United, Nashville SC",
        "Tier 3: Inter Miami (Messi era)",
        "",
        "Crown equivalent",
        "Tier 1: Waves, Steel",
        "Tier 2: Greensboro Groove (NC)",
        "Tier 3: WNBA star announced → ~+15%",
    ]
    wrapped = "\n".join(text_lines)
    axR.text(0.02, 0.98, wrapped, transform=axR.transAxes, fontsize=11.5, va="top", ha="left", linespacing=1.45)

    fig.suptitle(
        "Opponent quality drives a 14% attendance premium in Charlotte\n"
        "FC data 2022–2025 | Crown tier mapping estimated",
        fontsize=15,
        fontweight="bold",
        y=0.96,
    )
    return _save(fig, "P5_opponent_tier.png")


def chart_p6_conflict_calendar():
    PRES_DIR.mkdir(parents=True, exist_ok=True)
    dst = PRES_DIR / "P6_conflict_calendar.png"
    src = settings.REPORTS_DIR / "11_conflict_calendar.png"
    try:
        if not src.exists():
            from viz.conflict_calendar import plot_conflict_calendar

            plot_conflict_calendar(save=True)
        if src.exists():
            shutil.copy2(src, dst)
            try:
                from PIL import Image

                resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
                with Image.open(dst) as im:
                    rgb = im.convert("RGB")
                    rgb.resize((1600, 900), resample).save(dst, format="PNG", dpi=(DPI, DPI))
            except Exception as resize_exc:
                logger.debug("P6 resize skipped: %s", resize_exc)
            logger.info("P6: copied %s → %s (target 1600x900)", src, dst)
            return dst
    except Exception as e:
        logger.warning("P6 calendar copy/render failed: %s", e)
    _presentation_rc()
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.text(0.5, 0.5, "Conflict calendar unavailable.\nRun full pipeline to generate\nreports/11_conflict_calendar.png",
            ha="center", va="center", fontsize=16)
    ax.axis("off")
    return _save(fig, "P6_conflict_calendar.png")


def chart_p7_conflict_table():
    """
    Competition context for Crown home schedule: modeled attendance drag when FC or Knights
    also host same night, plus headline that most nights have no same-night overlap.
    """
    _presentation_rc()
    from config.constants import CANNIBALIZATION, CROWN_CONFLICT_PENALTY_CAP, CROWN_CONFLICT_PENALTIES

    try:
        from pipelines.build_master_calendar import build_master

        m = build_master(save=False)
    except Exception as exc:
        logger.warning("P7: build_master failed (%s); using static fallback rows", exc)
        m = None

    fc_pct = abs(CANNIBALIZATION["crown_loss_when_fc"]) * 100
    kn_pct = abs(CANNIBALIZATION["crown_loss_when_knights"]) * 100

    n_fc_dates = n_kn_dates = 0
    if m is not None and len(m) > 0:
        n_home = len(m)
        n_fc_dates = int((m["fc_same_day"].astype(int) == 1).sum())
        n_kn_dates = int((m["knights_same_day"].astype(int) == 1).sum())
        cmask = (m["fc_same_day"].astype(int) == 1) | (m["knights_same_day"].astype(int) == 1)
        conflicts = m.loc[cmask].sort_values("date").copy()
        n_conf = int(cmask.sum())
        n_clean = n_home - n_conf
        pct_clean = 100.0 * n_clean / n_home
        pct_conf = 100.0 * n_conf / n_home
    else:
        n_home, n_conf, n_clean = 17, 8, 9
        pct_clean, pct_conf = 100.0 * n_clean / n_home, 100.0 * n_conf / n_home
        conflicts = None

    fig = plt.figure(figsize=(FIG_W, FIG_H))
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.085, right=0.99, top=0.83, bottom=0.05, hspace=0.32, wspace=0.34)
    gs = fig.add_gridspec(2, 2, height_ratios=[2.65, 1.65], width_ratios=[1.85, 0.88])

    ax_l = fig.add_subplot(gs[0, 0])
    ax_r = fig.add_subplot(gs[0, 1])
    ax_r.axis("off")
    ax_note = fig.add_subplot(gs[1, :])
    ax_note.axis("off")

    def _short(txt: str, n: int) -> str:
        t = str(txt).strip()
        if not t:
            return ""
        return t if len(t) <= n else t[: n - 1] + "…"

    if conflicts is not None and not conflicts.empty:
        # Wider row pitch so multi-line y-labels (FC/Knights + Crown) don't overlap adjacent rows
        _row_pitch = 1.55
        y = np.arange(len(conflicts), dtype=float) * _row_pitch
        hits = (conflicts["cannibalization_pct"].astype(float) * 100).values
        fc_flags = conflicts["fc_same_day"].astype(int).values
        kn_flags = conflicts["knights_same_day"].astype(int).values
        # Blue = FC-only; teal = Knights-only; purple = both host same day (rare)
        colors = [
            "#7B5EA7" if (fc and kn) else (PALETTE["blue"] if fc else PALETTE["teal"])
            for fc, kn in zip(fc_flags, kn_flags)
        ]
        lbls = []
        for _, row in conflicts.iterrows():
            d = pd.Timestamp(row["date"])
            crown_opp = str(row.get("opponent", "")).replace("Jacksonville ", "Jax. ").replace("Greensboro ", "Gb. ")
            crown_opp = _short(crown_opp, 16)
            fc_on = int(row.get("fc_same_day", 0))
            kn_on = int(row.get("knights_same_day", 0))
            fc_o = str(row.get("fc_opponent", "") or "").replace(" (Leagues Cup)", "").strip()
            kn_o = str(row.get("knights_opponent", "") or "").strip()

            if fc_on and kn_on:
                fc_part = _short(fc_o, 22) if fc_o else "TBD"
                kn_part = _short(kn_o, 20) if kn_o else "TBD"
                clash = f"FC vs {fc_part} · Knights vs {kn_part}"
            elif fc_on:
                clash = f"FC home: {_short(fc_o, 30)}" if fc_o else "FC home (schedule)"
            else:
                clash = f"Knights home: {_short(kn_o, 30)}" if kn_o else "Knights home (schedule)"

            lbls.append(f"{d.strftime('%b %d')} · {clash}\n\n    Crown vs {crown_opp}")
        _bar_h = 0.52 * _row_pitch
        bars = ax_l.barh(y, hits, color=colors, height=_bar_h, edgecolor="none")
        ax_l.set_yticks(y)
        ax_l.set_yticklabels(lbls, fontsize=9, linespacing=1.62)
        ax_l.invert_yaxis()
        ax_l.set_xlabel("Modeled same-night attendance drag vs. a clean night (%)", fontsize=12)
        ax_l.set_xlim(0, max(22, hits.max() * 1.15))
        for bar, h in zip(bars, hits):
            ax_l.text(
                h + 0.35,
                bar.get_y() + bar.get_height() / 2,
                f"−{h:.0f}%",
                va="center",
                fontsize=10,
                fontweight="bold",
                color="#333",
            )
        ax_l.set_title(
            "Crown home dates with same-day Charlotte MLS/MiLB overlap — blue = FC @ BofA, teal = Knights @ Truist, purple = both\n"
            f"({n_fc_dates} of {n_home} Crown home dates overlap FC; {n_kn_dates} overlap Knights; "
            f"{len(conflicts)} total conflict nights in current schedule data)",
            fontsize=10,
            fontweight="bold",
            pad=8,
            loc="left",
        )
    else:
        ax_l.axis("off")
        ax_l.text(0.5, 0.5, "Run pipeline to build master_calendar\nfor conflict rows.", ha="center", va="center", fontsize=14)

    # Right column: headline stats only (priors / methods live in bottom band — no overlay)
    ax_r.text(
        0.5,
        0.88,
        "Same-night competition is\nrelatively low",
        transform=ax_r.transAxes,
        ha="center",
        va="top",
        fontsize=15,
        fontweight="bold",
        color=PALETTE["dark"],
    )
    ax_r.text(
        0.5,
        0.58,
        f"{n_clean} of {n_home} home games",
        transform=ax_r.transAxes,
        ha="center",
        va="top",
        fontsize=21,
        fontweight="bold",
        color=PALETTE["teal"],
    )
    ax_r.text(
        0.5,
        0.38,
        textwrap.fill(
            f"({pct_clean:.0f}%) have no Charlotte FC or Knights home game the same evening. "
            f"{n_conf} Crown dates ({pct_conf:.0f}%) overlap — bar heights use time-adjusted penalties "
            f"(not the older flat {fc_pct:.0f}% / {kn_pct:.0f}% flag priors in CANNIBALIZATION).",
            30,
        ),
        transform=ax_r.transAxes,
        ha="center",
        va="top",
        fontsize=9,
        linespacing=1.35,
        color="#444",
    )

    fig.suptitle(
        "Competition context — Charlotte Crown 2026 home schedule",
        fontsize=15,
        fontweight="bold",
        y=0.955,
    )

    # Bottom band: color key + three short paragraphs (no in-chart legend — avoids bar overlap)
    fce = int(CROWN_CONFLICT_PENALTIES["fc_same_evening"] * 100)
    fst = int(CROWN_CONFLICT_PENALTIES["fc_same_time"] * 100)
    kst = int(CROWN_CONFLICT_PENALTIES["knights_same_time"] * 100)
    ksg = int(CROWN_CONFLICT_PENALTIES["knights_staggered"] * 100)
    p_key = (
        f"Bar colors: blue = FC home same calendar day; teal = Knights home same day; purple = both. "
        f"Bar height = cannibalization_pct: compare Crown vs FC/Knights start times, then apply CROWN_CONFLICT_PENALTIES "
        f"(e.g. FC evening ~{fce}%, FC same-time window ~{fst}%; Knights same-time ~{kst}%, staggered ~{ksg}%). "
        f"CANNIBALIZATION crown_loss_when_fc (~{fc_pct:.0f}%) / crown_loss_when_knights (~{kn_pct:.0f}%) are legacy flag-only anchors — not what the bars plot."
    )
    cap_pct = CROWN_CONFLICT_PENALTY_CAP * 100
    p_calc = (
        f"Computation: master calendar flags same-day MLS/MiLB hosts, then compute_time_aware_cannibal_penalty() "
        f"from start-time gaps (see CROWN_SAME_TIME_THRESHOLD_HOURS). "
        f"crown_cannibalization_penalty(fc,kn) in constants uses additive {fc_pct:.0f}%+{kn_pct:.0f}% flags for simulator/tests only — "
        f"RevenueModel + P7 use the time-aware %, capped at {cap_pct:.0f}%."
    )
    p_prior = (
        "Bar heights are not measured from Crown gate data — no inaugural history yet. "
        "If you see ~27% on other slides, that is usually star_power in DRIVER_WEIGHTS_PRIOR (model driver mix), "
        "not an FC conflict percentage."
    )
    p_peer = (
        "Separately, for league peers only: FC ~4% drag when Knights host the same night; Knights ~11% when FC hosts "
        "(also priors in CANNIBALIZATION)."
    )
    ax_note.add_patch(
        FancyBboxPatch(
            (0.008, 0.02),
            0.984,
            0.94,
            boxstyle="round,pad=0.018",
            transform=ax_note.transAxes,
            facecolor="#F7F7F4",
            edgecolor="#d0d0cc",
            linewidth=0.9,
        )
    )
    ax_note.text(
        0.5,
        0.96,
        "Methods — how we compute the drag (and what we do not know yet)",
        transform=ax_note.transAxes,
        ha="center",
        va="top",
        fontsize=11,
        fontweight="bold",
        color=PALETTE["dark"],
    )
    y0, step = 0.82, 0.195
    for yi, para in enumerate((p_key, p_calc, p_prior, p_peer)):
        ax_note.text(
            0.5,
            y0 - yi * step,
            textwrap.fill(para, 118),
            transform=ax_note.transAxes,
            ha="center",
            va="top",
            fontsize=8.2,
            linespacing=1.52,
            color="#3a3a38",
        )

    return _save(fig, "P7_conflict_impact_table.png", pad_inches=0.6)


def chart_p8_transit_shuttle():
    _presentation_rc()
    # UNCC origin: FC/Knights ≈34 min Blue Line; Crown today ≈81 min (1h21); CTC shuttle = 34 + ~17 last mile ≈52
    venues = {
        "FC/Knights/Checkers\n(Blue Line, no transfer)": 34,
        "Crown\n(UNCC→Bojangles, no shuttle today)": 81,
        "Crown\n(+ game-day shuttle from CTC)": 52,
    }
    # Extra width on the right so the Value column can use one line; keep row height ~original.
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(FIG_W, FIG_H), gridspec_kw={"width_ratios": [1.0, 1.28]})
    # Extra bottom margin for footer below table (avoid overlap with sponsor row)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.86, bottom=0.20, wspace=0.26)

    names = list(venues.keys())
    vals = list(venues.values())
    bar_colors = ["#1D9E75", "#E24B4A", "#1D9E75"]
    y = np.arange(len(names))
    axL.barh(y, vals, color=bar_colors, height=0.50, edgecolor="none")
    axL.set_yticks(y)
    axL.set_yticklabels(names, fontsize=12, linespacing=1.15)
    axL.invert_yaxis()
    axL.set_xlim(0, 95)
    axL.axvline(20, color="#888780", linestyle="--", linewidth=2, zorder=0)
    # Threshold note in axes coords — avoids overlapping bars / value labels
    axL.text(
        0.98,
        0.97,
        "20-min threshold\n(high willingness to use transit)",
        transform=axL.transAxes,
        fontsize=10,
        color="#555",
        va="top",
        ha="right",
        linespacing=1.25,
    )
    axL.set_xlabel("Minutes from UNCC via transit", fontsize=13)
    for yi, v in enumerate(vals):
        axL.text(min(v + 1.5, 88), yi, f"{v}", va="center", fontsize=13, fontweight="bold", color="#222")
    # Keep callout in left axes upper area — bottom placement overlapped the economics table
    axL.annotate(
        "CTC shuttle: ~49–54 min\ntotal from UNCC\n(−~29 min vs today)",
        xy=(52, 2),
        xytext=(0.04, 0.90),
        textcoords=axL.transAxes,
        ha="left",
        va="top",
        fontsize=10,
        fontweight="bold",
        color="#1D9E75",
        arrowprops=dict(
            arrowstyle="->",
            color="#1D9E75",
            lw=1.6,
            connectionstyle="arc3,rad=0.15",
            shrinkA=2,
            shrinkB=4,
        ),
    )

    shuttle_data = [
        ["Vehicle", "2× 25-passenger minibuses (loop)"],
        ["Route", "CTC → Bojangles (direct; game-day schedule)"],
        ["Last mile @ CTC", "~15–20 min wait + ride (vs 10–15 wait + 25–28 local bus today)"],
        ["Cost per game (uptown shuttle)", "$350–500"],
        ["Season cost (17 games)", "$5,950–$8,500"],
        ["Campus-direct option", "UNCC→Bojangles ~23–25 min • $500–650/game"],
        ["Riders per game (est.)", "50–80"],
        ["Ticket revenue added", "$700–$1,120/game"],
        ["Ancillary added", "$350–$560/game"],
        ["Net per game", "+$700–$1,180"],
        ["Season net ROI", "300–500%"],
        ["Sponsor naming option", "$5K–$15K offsets cost"],
    ]
    axR.axis("off")
    tbl = axR.table(
        cellText=shuttle_data,
        colLabels=["Item", "Value"],
        cellLoc="left",
        loc="center",
        colWidths=[0.30, 0.70],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    for (row, col), cell in tbl.get_celld().items():
        cell.set_edgecolor("#d8d8d4")
        cell.set_linewidth(0.8)
        if row == 0:
            cell.set_facecolor("#2C2C2A")
            cell.set_text_props(color="white", fontweight="bold", fontsize=11)
        else:
            cell.set_facecolor("#F5F5F2" if row % 2 else "white")
            cell.set_text_props(fontsize=10, linespacing=1.2)
            if shuttle_data[row - 1][0] in ("Net per game", "Season net ROI"):
                cell.set_text_props(fontweight="bold", fontsize=10)
    # Slightly shorter rows so last table row clears the footer strip
    tbl.scale(1.38, 1.88)
    fig.text(
        0.72,
        0.06,
        "If UNCC or CATS sponsors naming rights → $0 net cost to Crown",
        transform=fig.transFigure,
        ha="center",
        fontsize=9,
        style="italic",
        color="#1D9E75",
        fontweight="bold",
    )

    fig.suptitle(
        "CTC game-day shuttle: UNCC ~52 min vs ~81 min today (Blue Line 34 min + last mile solved)",
        fontsize=13,
        fontweight="bold",
        y=0.95,
    )
    return _save(fig, "P8_transit_shuttle.png", pad_inches=0.55)


def chart_p9_waterfall():
    _presentation_rc()
    from models.revenue_model import RevenueModel

    model = RevenueModel()
    model.run_all()
    steps = [
        ("Baseline\nfill rate", 0.50, PALETTE["gray"], "start"),
        ("+ Promo calendar", 0.08, PALETTE["teal"], "add"),
        ("+ Giveaway nights", 0.04, PALETTE["teal"], "add"),
        ("− Conflict penalties", -0.03, PALETTE["red"], "sub"),
        ("+ Pricing bundles\n(group)", 0.03, PALETTE["blue"], "add"),
        ("+ Star player nights", 0.02, PALETTE["blue"], "add"),
        ("+ Shuttle / transit", 0.04, PALETTE["green"], "add"),
        ("Strategy B\nfill rate", None, PALETTE["amber"], "total"),
    ]
    running = 0.50
    bottoms, heights = [], []
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
        else:
            running += delta
            bottoms.append(running)
            heights.append(-delta)

    fig, ax = plt.subplots(figsize=(18, 6.2))
    fig.patch.set_facecolor("white")
    fig.subplots_adjust(left=0.07, right=0.98, top=0.88, bottom=0.22)
    bars = ax.bar(range(len(steps)), heights, bottom=bottoms, color=[s[2] for s in steps], width=0.6, edgecolor="none")
    for i in range(len(steps) - 1):
        top_i = bottoms[i] + heights[i]
        ax.plot([i + 0.3, i + 0.7], [top_i, top_i], color="#999", linewidth=0.9, linestyle="--")
    for i, (b, h) in enumerate(zip(bottoms, heights)):
        top = b + h
        kind = steps[i][3]
        if kind in ("start", "total"):
            ax.text(i, top + 0.015, f"{top:.0%}", ha="center", fontsize=14, fontweight="bold")
        else:
            sign = "+" if h > 0 else ""
            ax.text(i, top + 0.012 if h >= 0 else b - 0.025, f"{sign}{h:.0%}", ha="center", fontsize=13)
    ax.set_xticks(range(len(steps)))
    ax.set_xticklabels([s[0] for s in steps], fontsize=10)
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=18, ha="right")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.0%}"))
    ax.set_ylim(0, 0.95)
    ax.set_ylabel("Venue fill rate", fontsize=14)
    ax.set_title("Fill rate waterfall: Baseline → Strategy B\nHow each lever contributes to attendance growth",
                 fontsize=18, fontweight="bold", pad=14)
    for spine in ax.spines.values():
        spine.set_visible(False)
    PRES_DIR.mkdir(parents=True, exist_ok=True)
    path = PRES_DIR / "P9_revenue_waterfall.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white", dpi=DPI, pad_inches=0.5)
    plt.close(fig)
    _ = model
    return path


def chart_p9b_revenue_table():
    _presentation_rc()
    scenario_data = [
        ["", "Baseline", "Strategy A", "Strategy B"],
        ["Avg fill rate", "47.9%", "78.9%", "82.8%"],
        ["Avg ticket price", "$17.00", "$14.00", "$14.00"],
        ["Ancillary / head", "$4.00", "$7.00", "$7.00"],
        ["Total attendance", "28,524", "46,949", "49,260"],
        ["Ticket revenue", "$484,908", "$641,116", "$672,216"],
        ["Ancillary revenue", "$114,096", "$328,643", "$344,820"],
        ["Total revenue", "$599,004", "$969,759", "$1,017,036"],
        ["vs. baseline", "—", "+$370,755 (+62%)", "+$418,032 (+70%)"],
    ]

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0.04, right=0.96, top=0.88, bottom=0.06)
    ax.axis("off")
    tbl = ax.table(cellText=scenario_data[1:], colLabels=scenario_data[0], cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    header_bg = "#2C2C2A"
    strat_a = "#d4e4f7"
    strat_b = "#c5ebe0"
    teal_row = "#E1F5EE"

    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            if col == 2:
                cell.set_facecolor(strat_a)
                cell.set_text_props(color="#222", fontweight="bold", fontsize=14)
            elif col == 3:
                cell.set_facecolor(strat_b)
                cell.set_text_props(color="#222", fontweight="bold", fontsize=14)
            else:
                cell.set_facecolor(header_bg)
                cell.set_text_props(color="white", fontweight="bold", fontsize=11)
            continue
        if row == len(scenario_data) - 1:
            cell.set_text_props(fontweight="bold")
            if col >= 2 and scenario_data[row][col].startswith("+"):
                cell.set_text_props(color="#1D9E75", fontweight="bold")
        if row == 7:
            cell.set_facecolor(teal_row)
        cell.set_edgecolor("#ddd")

    tbl.scale(1.08, 1.95)
    ax.set_title(
        "Strategy B turns $599K into $1M+ — here's every assumption",
        fontsize=15,
        fontweight="bold",
        pad=12,
        y=0.98,
    )
    return _save(fig, "P9b_revenue_table.png")


def chart_p10_summary_table():
    _presentation_rc()
    summary_data = [
        ["Driver", "FC Evidence", "Knights Evidence", "Crown Action"],
        ["1. Promotions", "+82% opener, +18% avg giveaway", "Fireworks Fri = top attended weekly", "Theme all 17 games. Opener = biggest moment."],
        ["2. Star / Opponent", "+14% for Tier 3 opponents", "OKC Comets = biggest 2026 draw", "Market coach, VP, WNBA players by name May 9+"],
        ["3. Price / COA", "FC costs $139 for 2 → Crown gap to own", "Knights 68% fill at moderate prices", "$14 ticket + $0 parking = $52 for 2. Lead every ad."],
    ]
    row_colors = ["#E1F5EE", "#d4e4f7", "#FAEEDA"]  # promo | star/draw | price/COA

    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0.03, right=0.98, top=0.90, bottom=0.05)
    ax.axis("off")
    tbl = ax.table(cellText=summary_data[1:], colLabels=summary_data[0], cellLoc="left", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor("#2C2C2A")
            cell.set_text_props(color="white", fontweight="bold", fontsize=10)
            continue
        cell.set_facecolor(row_colors[row - 1])
        cell.set_edgecolor("#ccc")
        cell.PAD = 0.04
    tbl.scale(1.02, 2.4)
    ax.set_title("The Charlotte playbook — validated by FC and Knights data", fontsize=15, fontweight="bold", pad=14)
    return _save(fig, "P10_summary_table.png")


def chart_p11_market_context():
    """Section 1 — Driver 1 promo split, Driver 3 COA framing, Driver 2 FC opponent tier."""
    _presentation_rc()
    fc_path = settings.DATA_PROCESSED / "fc_games.csv"
    kn_path = settings.DATA_PROCESSED / "knights_games.csv"

    fc_non, fc_promo, fc_n0, fc_n1 = 31109.0, 33253.0, 32, 21
    kn_non, kn_promo, kn_n0, kn_n1 = 7596.0, 7791.0, 72, 92
    fc_fill_non = fc_fill_promo = None
    kn_fill_non = kn_fill_promo = None

    if fc_path.exists():
        fc = pd.read_csv(fc_path)
        if "has_promo" in fc.columns and int(fc["has_promo"].sum()) > 0:
            p = fc.loc[fc["has_promo"] == 1, "attendance"]
            n = fc.loc[fc["has_promo"] == 0, "attendance"]
            fc_promo, fc_n1 = float(p.mean()), int(len(p))
            fc_non, fc_n0 = float(n.mean()), int(len(n))
            if "fill_rate" in fc.columns:
                fc_fill_promo = float(fc.loc[fc["has_promo"] == 1, "fill_rate"].mean())
                fc_fill_non = float(fc.loc[fc["has_promo"] == 0, "fill_rate"].mean())

    if kn_path.exists():
        kn = pd.read_csv(kn_path)
        if "has_promo" in kn.columns and int(kn["has_promo"].sum()) > 0:
            p = kn.loc[kn["has_promo"] == 1, "attendance"]
            n = kn.loc[kn["has_promo"] == 0, "attendance"]
            kn_promo, kn_n1 = float(p.mean()), int(len(p))
            kn_non, kn_n0 = float(n.mean()), int(len(n))
            if "fill_rate" in kn.columns:
                kn_fill_promo = float(kn.loc[kn["has_promo"] == 1, "fill_rate"].mean())
                kn_fill_non = float(kn.loc[kn["has_promo"] == 0, "fill_rate"].mean())

    fc_lift = (fc_promo / fc_non - 1) * 100 if fc_non else 0.0
    kn_lift = (kn_promo / kn_non - 1) * 100 if kn_non else 0.0

    coa_fc = (
        COA_TICKET_ASSUMPTIONS["fc"] * 2
        + PARKING_COSTS["fc"]["avg"]
        + COA_CONCESSION_AVG_PER_PERSON["fc"] * 2
    )
    coa_kn = (
        COA_TICKET_ASSUMPTIONS["knights"] * 2
        + PARKING_COSTS["knights"]["avg"]
        + COA_CONCESSION_AVG_PER_PERSON["knights"] * 2
    )

    tier_means = {1: 31339.0, 2: 34757.0, 3: 35804.0}
    tier_ns = {1: 44, 2: 7, 3: 2}
    if fc_path.exists():
        fc_df = pd.read_csv(fc_path)
        if "opponent_tier" in fc_df.columns and fc_df["opponent_tier"].nunique() > 1:
            g = fc_df.groupby("opponent_tier")["attendance"]
            tier_means = {int(k): float(v) for k, v in g.mean().items()}
            tier_ns = {int(k): int(c) for k, c in g.count().items()}

    pri_p = int(round(DRIVER_WEIGHTS_PRIOR["promotions"] * 100))
    pri_s = int(round(DRIVER_WEIGHTS_PRIOR["star_power"] * 100))
    pri_co = int(round(DRIVER_WEIGHTS_PRIOR["price"] * 100))
    pri_tr = int(round(DRIVER_WEIGHTS_PRIOR["transit"] * 100))

    fig = plt.figure(figsize=(FIG_W, FIG_H))
    gs = GridSpec(
        2,
        2,
        figure=fig,
        height_ratios=[1.05, 1],
        hspace=0.34,
        wspace=0.26,
        left=0.08,
        right=0.98,
        top=0.84,
        bottom=0.17,
    )
    ax_fc = fig.add_subplot(gs[0, 0])
    ax_kn = fig.add_subplot(gs[0, 1])
    ax_coa = fig.add_subplot(gs[1, 0])
    ax_tier = fig.add_subplot(gs[1, 1])

    xb = np.array([0, 1])
    for ax, non, promo, n0, n1, lift, cap, cap_lbl, colors, ymax_base in (
        (
            ax_fc,
            fc_non,
            fc_promo,
            fc_n0,
            fc_n1,
            fc_lift,
            38000,
            "~38K cap",
            ("#888780", "#378ADD"),
            38000,
        ),
        (
            ax_kn,
            kn_non,
            kn_promo,
            kn_n0,
            kn_n1,
            kn_lift,
            10200,
            "~10.2K cap",
            ("#B4B2A9", "#1D9E75"),
            10200,
        ),
    ):
        ax.set_xlim(-0.55, 1.55)
        ax.bar(xb, [non, promo], width=0.52, color=colors, edgecolor="none")
        ax.set_xticks(xb)
        ax.set_xticklabels(["Non-promo", "Promo"], fontsize=10)
        ax.set_ylabel("Avg attendance", fontsize=11)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.1f}K"))
        ymax = max(non, promo, ymax_base) * 1.2
        ax.set_ylim(0, ymax)
        ax.axhline(cap, color="#BA7517", linestyle="--", linewidth=1.4, alpha=0.85)
        ax.text(1.38, cap, cap_lbl, fontsize=8, color="#555", va="center")
        ax.text(0, non + ymax * 0.02, f"{non:,.0f}\n(n={n0})", ha="center", fontsize=9, fontweight="bold")
        ax.text(1, promo + ymax * 0.02, f"{promo:,.0f}\n(n={n1})", ha="center", fontsize=9, fontweight="bold")
        ax.text(0.5, ymax * 0.92, f"Lift +{lift:.1f}%", ha="center", fontsize=10, fontweight="bold", color="#222")
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(True, axis="y", alpha=0.22)

    ax_fc.set_title(f"Driver 1 — Promotions (prior {pri_p}%)", fontsize=11, fontweight="bold", pad=4)
    ax_fc.text(0.5, -0.16, "Charlotte FC", transform=ax_fc.transAxes, ha="center", fontsize=9, color="#333")
    if fc_fill_non is not None and fc_fill_promo is not None:
        ax_fc.text(
            0.5,
            -0.24,
            f"Fill {fc_fill_non:.0%} → {fc_fill_promo:.0%}",
            transform=ax_fc.transAxes,
            ha="center",
            fontsize=7.5,
            color="#555",
        )

    ax_kn.set_title("", fontsize=11, fontweight="bold", pad=4)
    ax_kn.text(0.5, -0.16, "Charlotte Knights", transform=ax_kn.transAxes, ha="center", fontsize=9, color="#333")
    if kn_fill_non is not None and kn_fill_promo is not None:
        ax_kn.text(
            0.5,
            -0.24,
            f"Fill {kn_fill_non:.0%} → {kn_fill_promo:.0%}",
            transform=ax_kn.transAxes,
            ha="center",
            fontsize=7.5,
            color="#555",
        )

    venues = ["FC", "Knights"]
    coa_vals = [coa_fc, coa_kn]
    coa_colors = ["#378ADD", "#1D9E75"]
    xc = np.arange(len(venues))
    bars_c = ax_coa.bar(xc, coa_vals, color=coa_colors, width=0.5, edgecolor="none")
    ax_coa.set_xticks(xc)
    ax_coa.set_xticklabels(venues, fontsize=11)
    ax_coa.set_ylabel("Estimated $ for 2 adults", fontsize=11)
    ymax_c = max(coa_vals) * 1.15
    ax_coa.set_ylim(0, ymax_c)
    for bar, v in zip(bars_c, coa_vals):
        ax_coa.text(bar.get_x() + bar.get_width() / 2, v + ymax_c * 0.02, f"${v:.0f}", ha="center", fontsize=10, fontweight="bold")
    ax_coa.set_title(
        f"Driver 3 — Price & total night out (prior {pri_co}%)",
        fontsize=11,
        fontweight="bold",
        pad=6,
    )
    ax_coa.text(
        0.5,
        -0.14,
        "2 adults: ticket×2 + parking + concessions (constants)",
        transform=ax_coa.transAxes,
        ha="center",
        fontsize=7.5,
        color="#555",
    )
    for spine in ax_coa.spines.values():
        spine.set_visible(False)
    ax_coa.grid(True, axis="y", alpha=0.22)

    tiers = sorted(tier_means.keys())
    means = [tier_means[t] for t in tiers]
    ns = [tier_ns.get(t, 0) for t in tiers]
    teals = ["#8fd4b8", "#3cb88c", "#1D9E75"]
    x_t = np.arange(len(tiers))
    bars_t = ax_tier.bar(x_t, means, color=teals[: len(tiers)], edgecolor="none", width=0.52)
    ax_tier.set_xticks(x_t)
    ax_tier.set_xticklabels([f"Tier {t}" for t in tiers], fontsize=10)
    ax_tier.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}K"))
    ax_tier.set_ylabel("Avg attendance", fontsize=11)
    ymax_t = max(means) * 1.2 if means else 40000
    ax_tier.set_ylim(0, ymax_t)
    for bar, m, n in zip(bars_t, means, ns):
        ax_tier.text(bar.get_x() + bar.get_width() / 2, m + ymax_t * 0.02, f"n={n}", ha="center", fontsize=8)
    ax_tier.set_title(
        f"Driver 2 — Opponent / star draw (prior {pri_s}%)",
        fontsize=11,
        fontweight="bold",
        pad=6,
    )
    ax_tier.text(
        0.5,
        -0.14,
        "FC tiers from opponent map; Knights tier = 1 (pipeline)",
        transform=ax_tier.transAxes,
        ha="center",
        fontsize=7.5,
        color="#555",
    )
    for spine in ax_tier.spines.values():
        spine.set_visible(False)
    ax_tier.grid(True, axis="y", alpha=0.22)

    fig.suptitle(
        "Charlotte market context — three ticket drivers (promo, draw, price)",
        fontsize=14,
        fontweight="bold",
        y=0.945,
    )
    # Three short lines in bottom margin (avoids wrap/overlap on 16:9 export)
    fig.text(
        0.5,
        0.102,
        "Top: processed avg attendance when has_promo is set (else seed fallback).",
        ha="center",
        va="top",
        fontsize=7,
        color="#666",
    )
    fig.text(
        0.5,
        0.076,
        "Bottom left: COA from constants (2 adults). Bottom right: fc_games opponent_tier.",
        ha="center",
        va="top",
        fontsize=7,
        color="#666",
    )
    fig.text(
        0.5,
        0.050,
        f"Transit ≈{pri_tr}% prior — separate lever, not a top-three driver here.",
        ha="center",
        va="top",
        fontsize=7,
        color="#666",
    )
    return _save(fig, "P11_market_context.png")


def _p12_bar_colors(n: int) -> list:
    cycle = ["#BA7517", "#1D9E75", "#7F77DD", "#378ADD", "#888780", "#E24B4A", "#639922", "#2C2C2A"]
    return [cycle[i % len(cycle)] for i in range(n)]


def _chart_p12_illustrative():
    """Fallback when no survey CSV — literature-style priors."""
    _presentation_rc()
    survey_data = {
        "Low ticket price / value": 72,
        "Promo / giveaway night": 61,
        "Convenient location / parking": 58,
        "Friend or family group outing": 54,
        "Local player / team connection": 41,
        "Star player or marquee opponent": 38,
        "Transit / public transport access": 22,
    }
    bar_colors_map = _p12_bar_colors(len(survey_data))

    fig = plt.figure(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.86, bottom=0.10, wspace=0.28)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1])
    axL = fig.add_subplot(gs[0, 0])
    labels = list(survey_data.keys())
    vals = list(survey_data.values())
    y = np.arange(len(labels))
    axL.barh(y, vals, color=bar_colors_map, height=0.52, edgecolor="none")
    axL.invert_yaxis()
    axL.set_xlim(0, 88)
    axL.set_xlabel("% selecting (illustrative)", fontsize=12)
    for yi, v in zip(y, vals):
        axL.text(v + 1.2, yi, f"{v}%", va="center", fontsize=11, fontweight="bold")
    axL.set_yticks(y)
    axL.set_yticklabels([textwrap.fill(lab, 32) for lab in labels], fontsize=10)
    axL.set_title(
        "Why attend minor / developmental league sports?\n"
        "(Charlotte market — illustrative)",
        fontsize=12,
        fontweight="bold",
        pad=8,
    )
    axL.text(
        0.5,
        -0.12,
        "Comparable developmental-league benchmarks — not Crown-specific data",
        transform=axL.transAxes,
        ha="center",
        fontsize=9,
        style="italic",
        color="#666",
    )
    for spine in axL.spines.values():
        spine.set_visible(False)

    gs_r = gs[0, 1].subgridspec(2, 2, hspace=0.35, wspace=0.2)
    boxes = [
        (gs_r[0, 0], "#E1F5EE", "HOW DID YOU HEAR?", "• Social / TikTok / IG\n• Friend or family\n• Email list\n• CATS / transit ad\n• Promo flyer"),
        (gs_r[0, 1], "#d4e4f7", "WHAT ALMOST STOPPED YOU?", "• Parking unknown\n• Transit friction\n• Price unclear\n• Missed promo info"),
        (gs_r[1, 0], "#FAEEDA", "WHAT BRINGS YOU BACK?", "• Better giveaway\n• Cheaper concessions\n• Shuttle option\n• Recognizable player"),
        (gs_r[1, 1], "#E8E8E6", "DEMOGRAPHICS", "• Age, zip, UNCC tie\n• First Crown game?\n• Sting memory?"),
    ]
    for gss, face, title, body in boxes:
        axb = fig.add_subplot(gss)
        axb.axis("off")
        axb.add_patch(
            FancyBboxPatch(
                (0.02, 0.05),
                0.96,
                0.90,
                boxstyle="round,pad=0.02",
                transform=axb.transAxes,
                facecolor=face,
                edgecolor="#bbb",
                linewidth=0.8,
            )
        )
        axb.text(0.06, 0.88, title, transform=axb.transAxes, fontsize=10, fontweight="bold", va="top", color="#222")
        axb.text(0.06, 0.72, body, transform=axb.transAxes, fontsize=9, va="top", color="#333", linespacing=1.25)

    fig.suptitle(
        "Survey framework: validate drivers with real fan data after May 21\n"
        "First homestand survey → model refresh by Game 5",
        fontsize=14,
        fontweight="bold",
        y=0.96,
    )
    return _save(fig, "P12_survey_framework.png")


def _chart_p12_from_responses(agg: dict, source_name: str) -> Path:
    """P12 from Google Form aggregates (pipelines.crown_survey_aggregates)."""
    from pipelines.crown_survey_aggregates import (
        format_bullets_from_pct,
        reformat_hear_bullets,
    )

    _presentation_rc()
    n = int(agg["n"])
    factor = agg["factor_pct"].sort_values(ascending=True)
    labels = [textwrap.fill(str(i), 30) for i in factor.index]
    vals = factor.values.astype(float)
    colors = _p12_bar_colors(len(vals))
    xmax = max(45.0, float(vals.max()) * 1.22)

    fig = plt.figure(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0.07, right=0.98, top=0.84, bottom=0.08, wspace=0.28)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.08, 1])
    axL = fig.add_subplot(gs[0, 0])
    y = np.arange(len(vals))
    axL.barh(y, vals, color=colors, height=0.52, edgecolor="none")
    axL.invert_yaxis()
    axL.set_xlim(0, xmax)
    axL.set_xlabel(f"% of respondents (n = {n})", fontsize=12)
    for yi, v in zip(y, vals):
        axL.text(min(v + 0.8, xmax - 8), yi, f"{v:.0f}%", va="center", fontsize=11, fontweight="bold")
    axL.set_yticks(y)
    axL.set_yticklabels(labels, fontsize=10)
    axL.set_title(
        "Most important factor when attending\nsporting events (this sample)",
        fontsize=12,
        fontweight="bold",
        pad=8,
    )
    axL.text(
        0.5,
        -0.11,
        f"Source: {source_name}  ·  Replace data/raw/crown_survey_responses.csv to refresh",
        transform=axL.transAxes,
        ha="center",
        fontsize=8,
        style="italic",
        color="#666",
    )
    for spine in axL.spines.values():
        spine.set_visible(False)

    hear_body = reformat_hear_bullets(agg["hear_pct"].head(6))
    price_body = format_bullets_from_pct(agg["price_pct"].head(6))
    promo_body = format_bullets_from_pct(agg["promo_pct"].head(6))

    team_body = format_bullets_from_pct(agg["team_pct"].head(5))
    age_body = format_bullets_from_pct(agg["age_pct"].head(5))
    demo_lines = [age_body, "", "LIKELY VENUE (transit / location)", team_body]
    if agg.get("star_mean") is not None and agg.get("star_n", 0) > 0:
        demo_lines.extend(
            [
                "",
                f"Notable players lift interest (1–5): mean {agg['star_mean']:.1f} (n={agg['star_n']})",
            ]
        )
    demo_body = "\n".join(demo_lines)

    gs_r = gs[0, 1].subgridspec(2, 2, hspace=0.38, wspace=0.2)
    boxes = [
        (gs_r[0, 0], "#E1F5EE", "WHERE THEY HEAR ABOUT CROWN", hear_body),
        (gs_r[0, 1], "#d4e4f7", "PRICE — WILLING TO PAY (CROWN)", price_body),
        (gs_r[1, 0], "#FAEEDA", "PROMOTIONS / EVENTS THEY WANT", promo_body),
        (gs_r[1, 1], "#E8E8E6", "AGE + VENUE PREFERENCE", demo_body),
    ]
    for gss, face, title, body in boxes:
        axb = fig.add_subplot(gss)
        axb.axis("off")
        axb.add_patch(
            FancyBboxPatch(
                (0.02, 0.04),
                0.96,
                0.92,
                boxstyle="round,pad=0.02",
                transform=axb.transAxes,
                facecolor=face,
                edgecolor="#bbb",
                linewidth=0.8,
            )
        )
        axb.text(0.05, 0.90, title, transform=axb.transAxes, fontsize=9, fontweight="bold", va="top", color="#222")
        axb.text(0.05, 0.78, body, transform=axb.transAxes, fontsize=8, va="top", color="#333", linespacing=1.22)

    fig.suptitle(
        f"Exploratory survey — Charlotte Crown / Checkers (n = {n})\n"
        "Early signals to complement model priors — validate with May 21+ attendance",
        fontsize=13,
        fontweight="bold",
        y=0.97,
    )
    return _save(fig, "P12_survey_framework.png", pad_inches=0.5)


def chart_p12_survey_framework(survey_csv: Path | None = None):
    """
    Survey slide: real Google Form export if ``data/raw/crown_survey_responses.csv``
    exists (or path passed), else illustrative framework.
    """
    from pipelines.crown_survey_aggregates import aggregates_for_p12, load_crown_survey_csv, resolve_crown_survey_csv

    path = survey_csv or resolve_crown_survey_csv()
    if path is not None and path.exists():
        try:
            df = load_crown_survey_csv(path)
            agg = aggregates_for_p12(df)
            if agg["n"] >= 3 and not agg["factor_pct"].empty:
                logger.info("P12: using survey responses from %s (n=%s)", path, agg["n"])
                return _chart_p12_from_responses(agg, path.name)
        except Exception as exc:
            logger.warning("P12: survey CSV failed (%s); using illustrative fallback", exc)
    return _chart_p12_illustrative()


def chart_p13_pga_shuttle_precedent():
    """Section 4 — PGA Truist precedent + Crown shuttle economics."""
    _presentation_rc()

    pga_facts = [
        ("Event", "Truist Championship (Wells Fargo Championship)\nQuail Hollow Club, Charlotte NC"),
        ("Shuttle Route", "Park-and-ride lots → Quail Hollow Club\nMultiple pickup points incl. transit hubs"),
        ("Why it exists", "Quail Hollow has limited on-site parking\nShuttle is the PRIMARY access mode for fans"),
        ("Operator", "CATS + private charter hybrid\nCATS provides overflow bus capacity on game days"),
        ("Fan response", "Shuttle usage cited in PGA fan surveys as\n#1 reason access concerns resolved"),
    ]
    shuttle_comparison = {
        "PGA Truist Chmpship\n(full tournament)": {"season_cost": 45000, "incremental_rev": None, "notes": "Public-private CATS partnership"},
        "Crown Season\n(17 games, charter)": {"season_cost": 7225, "incremental_rev": 17000, "notes": "Private charter"},
        "Crown Season\n(CATS partnership)*": {"season_cost": 2500, "incremental_rev": 17000, "notes": "CATS MOU / game-day bus"},
    }

    fig = plt.figure(figsize=(FIG_W, FIG_H))
    fig.subplots_adjust(left=0.04, right=0.98, top=0.90, bottom=0.14, wspace=0.26)
    axL = fig.add_axes([0.04, 0.16, 0.43, 0.74])
    axL.axis("off")
    axL.set_title(
        "Truist Championship — shuttle precedent\n(Quail Hollow, Charlotte)",
        fontsize=12,
        fontweight="bold",
        pad=6,
    )
    y = 0.91
    for lab, val in pga_facts:
        h = 0.125
        rect = FancyBboxPatch((0.02, y - h), 0.96, h - 0.015, boxstyle="round,pad=0.012", transform=axL.transAxes,
                              facecolor="white", edgecolor="#ccc", linewidth=0.8)
        axL.add_patch(rect)
        axL.plot([0.02, 0.02], [y - h + 0.01, y - 0.01], color="#1D9E75", linewidth=4, transform=axL.transAxes, clip_on=False)
        axL.text(0.045, y - 0.015, lab, transform=axL.transAxes, fontsize=9, color="#666", fontweight="bold", va="top")
        axL.text(0.045, y - 0.048, val, transform=axL.transAxes, fontsize=9, color="#222", va="top", linespacing=1.2)
        y -= h + 0.008
    axL.text(
        0.02,
        0.01,
        textwrap.fill(
            "Crown parallel: free parking at Bojangles but weaker transit. "
            "PGA shows fans ride shuttles when marketing is clear — the gap is comms, not demand.",
            52,
        ),
        transform=axL.transAxes,
        fontsize=8.5,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="#E1F5EE", edgecolor="#1D9E75"),
        va="bottom",
    )

    axR = fig.add_axes([0.52, 0.16, 0.44, 0.72])
    names = list(shuttle_comparison.keys())
    x = np.arange(len(names))
    w = 0.32
    costs = [shuttle_comparison[n]["season_cost"] for n in names]
    revs = [shuttle_comparison[n]["incremental_rev"] for n in names]
    axR.bar(x - w / 2, costs, w, label="Season cost", color="#E24B4A", edgecolor="none", alpha=0.9)
    rev_heights = [0 if r is None else r for r in revs]
    axR.bar(x + w / 2, rev_heights, w, label="Incremental rev (est.)", color="#1D9E75", edgecolor="none", alpha=0.9)
    axR.text(x[0], 2000, "N/A /\nnot tracked", ha="center", fontsize=11, fontweight="bold", color="#555")
    axR.set_xticks(x)
    axR.set_xticklabels([textwrap.fill(n, 16) for n in names], fontsize=9)
    axR.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"${v/1000:.0f}K" if v >= 1000 else f"${v:.0f}"))
    axR.set_ylabel("Dollars ($)", fontsize=12)
    axR.set_title("Shuttle cost vs incremental revenue (est.)", fontsize=12, fontweight="bold")
    axR.legend(fontsize=10, loc="upper left", frameon=False)
    for spine in axR.spines.values():
        spine.set_visible(False)
    axR.grid(True, axis="y", alpha=0.25)
    fig.text(
        0.52,
        0.06,
        textwrap.fill(
            "* CATS partnership requires MOU. Crown captures ticket + ancillary uplift vs PGA access-satisfaction focus.",
            78,
        ),
        fontsize=9,
        color="#1D9E75",
        fontweight="bold",
        ha="left",
    )

    fig.suptitle("Charlotte shuttle precedent (PGA) + Crown season economics", fontsize=14, fontweight="bold", y=0.95)
    return _save(fig, "P13_pga_shuttle_precedent.png")


def chart_p14_revenue_assumptions():
    """Section 5 — assumptions tied to FC/Knights evidence."""
    _presentation_rc()
    fig = plt.figure(figsize=(FIG_W, FIG_H))
    fig.patch.set_facecolor("white")
    gs = fig.add_gridspec(
        3,
        2,
        height_ratios=[1, 1, 1.2],
        width_ratios=[0.36, 0.64],
        hspace=0.62,
        wspace=0.18,
        left=0.07,
        right=0.97,
        top=0.82,
        bottom=0.14,
    )

    fig.suptitle(
        "Every revenue assumption is tied to observed Charlotte behavior\n"
        "Conservative vs FC — anchored closer to Knights-level fill",
        fontsize=14,
        fontweight="bold",
        y=0.95,
    )

    # Row 1
    ax0 = fig.add_subplot(gs[0, 0])
    ax0.axis("off")
    ax0.text(0.05, 0.5, "Assumption:\nStrategy A\n79% fill", fontsize=12, fontweight="bold", va="center", transform=ax0.transAxes)
    ax1 = fig.add_subplot(gs[0, 1])
    cats = ["FC giveaway\nnights avg", "Knights Fri/Sat\navg fill", "Crown Strategy A\ntarget"]
    fills = [84, 75, 79]
    colors = ["#378ADD", "#378ADD", "#BA7517"]
    xb = np.arange(len(cats))
    ax1.bar(xb, fills, color=colors, width=0.55, edgecolor="none")
    ax1.set_xticks(xb)
    ax1.set_xticklabels([textwrap.fill(c, 14) for c in cats], fontsize=9)
    ax1.set_ylabel("Fill %", fontsize=11)
    ax1.set_ylim(0, 100)
    for i, v in enumerate(fills):
        ax1.text(i, v + 2, f"{v}%", ha="center", fontsize=10, fontweight="bold")
    ax1.text(0.5, -0.32, "Crown between FC promo-type fill & Knights weekend", transform=ax1.transAxes, ha="center", fontsize=9)
    for spine in ax1.spines.values():
        spine.set_visible(False)
    ax1.grid(True, axis="y", alpha=0.25)

    # Row 2
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.axis("off")
    ax2.text(0.05, 0.5, "Assumption:\nAncillary $4→$7\n(bundle)", fontsize=12, fontweight="bold", va="center", transform=ax2.transAxes)
    ax3 = fig.add_subplot(gs[1, 1])
    c2 = ["FC avg\n$/head", "Knights avg\n$/head", "Crown\nbaseline", "Crown strategy\n(bundle)"]
    v2 = [11.50, 7.50, 4.00, 7.00]
    col2 = ["#378ADD", "#378ADD", "#888780", "#1D9E75"]
    x2 = np.arange(len(c2))
    ax3.bar(x2, v2, color=col2, width=0.5, edgecolor="none")
    ax3.set_xticks(x2)
    ax3.set_xticklabels([textwrap.fill(c, 12) for c in c2], fontsize=8)
    ax3.set_ylabel("$ / head", fontsize=11)
    for i, v in enumerate(v2):
        ax3.text(i, v + 0.35, f"${v:.2f}", ha="center", fontsize=10, fontweight="bold")
    ax3.text(0.5, -0.38, "$15 F&B bundle pushes per-cap toward Knights tier", transform=ax3.transAxes, ha="center", fontsize=9)
    ax3.text(0.5, -0.50, "Crown list prices below Knights — bundle reads as value", transform=ax3.transAxes, ha="center", fontsize=8, style="italic", color="#555")
    for spine in ax3.spines.values():
        spine.set_visible(False)
    ax3.grid(True, axis="y", alpha=0.25)

    # Row 3
    ax4 = fig.add_subplot(gs[2, 0])
    ax4.axis("off")
    ax4.text(0.05, 0.55, "Assumption:\n$17→$14 ticket\nvolume > margin", fontsize=12, fontweight="bold", va="center", transform=ax4.transAxes)
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.axis("off")
    comp = [
        ["At $17, 50% fill", "1750 × $17", "$29,750/game"],
        ["At $14, 79% fill", "2765 × $14", "$38,710/game"],
    ]
    tbl = ax5.table(cellText=comp, colLabels=["Scenario", "Math", "Revenue / game"], cellLoc="center", loc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    for (row, col), cell in tbl.get_celld().items():
        if row == 0:
            cell.set_facecolor("#2C2C2A")
            cell.set_text_props(color="white", fontweight="bold", fontsize=9)
        elif row == 2:
            cell.set_facecolor("#E1F5EE")
            cell.set_text_props(fontweight="bold")
        else:
            cell.set_facecolor("#FAFAF9")
        cell.set_edgecolor("#ddd")
    tbl.scale(1.02, 1.95)
    fig.text(
        0.5,
        0.03,
        textwrap.fill(
            "NWSL expansion precedent: ~$12–15 Y1 tickets, $20+ by Y3 (Angel City, San Diego Wave).",
            96,
        ),
        ha="center",
        fontsize=9,
        style="italic",
        color="#444",
    )

    return _save(fig, "P14_revenue_assumptions.png")


CHART_FUNCS = [
    ("P1", chart_p1_driver_weights),
    ("P2", chart_p2_fc_promo_benchmark),
    ("P3", chart_p3_promo_type_lift),
    ("P4", chart_p4_cost_of_attendance),
    ("P5", chart_p5_opponent_tier),
    ("P6", chart_p6_conflict_calendar),
    ("P7", chart_p7_conflict_table),
    ("P8", chart_p8_transit_shuttle),
    ("P9", chart_p9_waterfall),
    ("P9b", chart_p9b_revenue_table),
    ("P10", chart_p10_summary_table),
    ("P11", chart_p11_market_context),
    ("P12", chart_p12_survey_framework),
    ("P13", chart_p13_pga_shuttle_precedent),
    ("P14", chart_p14_revenue_assumptions),
]

# Subset aligned with reports/presentation/SLIDE_CONTENT_SPEC.md (5-slide Canva deck).
DECK_5_CHART_FUNCS = [
    ("P11", chart_p11_market_context),
    ("P6", chart_p6_conflict_calendar),
    ("P7", chart_p7_conflict_table),
    ("P1", chart_p1_driver_weights),
    ("P12", chart_p12_survey_framework),
    ("P8", chart_p8_transit_shuttle),
    ("P13", chart_p13_pga_shuttle_precedent),
    ("P10", chart_p10_summary_table),
    ("P9b", chart_p9b_revenue_table),
]


def generate_deck5():
    """PNG exports for the 5-slide deck (see SLIDE_CONTENT_SPEC.md)."""
    PRES_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for name, fn in DECK_5_CHART_FUNCS:
        try:
            p = fn()
            saved.append(p.name if isinstance(p, Path) else str(p))
            logger.info("Deck5 saved %s", p)
        except Exception as e:
            logger.exception("Deck5 chart %s failed: %s", name, e)
    return saved


def generate_all():
    PRES_DIR.mkdir(parents=True, exist_ok=True)
    saved = []
    for name, fn in CHART_FUNCS:
        try:
            p = fn()
            saved.append(p.name if isinstance(p, Path) else str(p))
            logger.info("Saved %s", p)
        except Exception as e:
            logger.exception("Chart %s failed: %s", name, e)
    return saved


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    deck5 = "--deck5" in sys.argv
    saved = generate_deck5() if deck5 else generate_all()
    label = "5-slide deck" if deck5 else "full library"
    print(f"Generated {len(saved)} charts ({label}) to reports/presentation/")
    for f in sorted(saved):
        print(f"  - {f}")


def plot_driver_weights_comparison(save=True):
    """
    Side-by-side grouped horizontal bar chart comparing
    FC/Knights driver weights vs Crown Year 1 adjusted weights.
    Saves to reports/presentation/P15_driver_weights_comparison.png
    """
    _presentation_rc()
    from matplotlib.patches import Patch
    import matplotlib.gridspec as gridspec

    FC_KNIGHTS_WEIGHTS = {
        "Promotions &\nTheme Nights": 35,
        "Price & Total\nCost of Attendance": 23,
        "Transportation\n& Transit Access": 5,
        "Social &\nCommunity": 10,
        "Star Power &\nOpponent Draw": 27,
    }
    _cp = CROWN_DRIVER_WEIGHTS_PRIOR
    CROWN_WEIGHTS = {
        "Promotions &\nTheme Nights": int(round(_cp["promotions"] * 100)),
        "Price & Total\nCost of Attendance": int(round(_cp["price"] * 100)),
        "Transportation\n& Transit Access": int(round(_cp["transit"] * 100)),
        "Social &\nCommunity": int(round(_cp["social"] * 100)),
        "Star Power &\nOpponent Draw": int(round(_cp["star_power"] * 100)),
    }
    # Crown survey-corrected weights, descending (top to bottom after invert_yaxis)
    DRIVER_KEYS_ORDER = [
        "Promotions &\nTheme Nights",
        "Price & Total\nCost of Attendance",
        "Transportation\n& Transit Access",
        "Social &\nCommunity",
        "Star Power &\nOpponent Draw",
    ]
    # Crown vs FC/Knights (percentage points)
    delta_specs = [
        ("↓", "−1pt"),
        ("↑", "+2pts"),
        ("↑↑", "+15pts"),
        ("↑", "+4pts"),
        ("↓", "−20pts"),
    ]

    bar_h = 0.35
    pair_gap = 0.05
    group_gap = 0.3
    step = bar_h + pair_gap + bar_h + group_gap

    fig = plt.figure(figsize=(FIG_W, FIG_H))
    fig.patch.set_facecolor("white")
    gs = gridspec.GridSpec(
        1,
        2,
        figure=fig,
        width_ratios=[2.15, 1.0],
        wspace=0.28,
        left=0.07,
        right=0.98,
        top=0.76,
        bottom=0.30,
    )
    ax = fig.add_subplot(gs[0, 0])
    ax_side = fig.add_subplot(gs[0, 1])
    ax_side.axis("off")

    steel_blue = "#4A90D9"
    crown_purple = "#7B5EA7"

    for i, key in enumerate(DRIVER_KEYS_ORDER):
        fv = FC_KNIGHTS_WEIGHTS[key]
        cv = CROWN_WEIGHTS[key]
        y_fc = i * step
        y_cr = y_fc + bar_h + pair_gap
        ax.barh(y_fc, fv, height=bar_h, color=steel_blue, edgecolor="none")
        ax.barh(y_cr, cv, height=bar_h, color=crown_purple, edgecolor="none")
        y_fc_c = y_fc + bar_h / 2
        y_cr_c = y_cr + bar_h / 2
        # Tight to bar end (display pts); small +y = slightly above bar midline (screen coords)
        _pct_off = (2, 4)
        ax.annotate(
            f"{fv}%",
            xy=(fv, y_fc_c),
            xytext=_pct_off,
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=13,
            color=steel_blue,
        )
        ax.annotate(
            f"{cv}%",
            xy=(cv, y_cr_c),
            xytext=_pct_off,
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=13,
            color=crown_purple,
            fontweight="bold",
        )
        longer = max(fv, cv)
        arr, pts = delta_specs[i]
        y_mid = (y_fc_c + y_cr_c) / 2
        # Past bar ends + "%" labels (annotate uses ~0.3–0.5 share units for short strings)
        delta_x = longer + 3.2
        ax.text(
            delta_x,
            y_mid,
            f"{arr}{pts}",
            va="center",
            fontsize=11,
            color="#444",
            fontweight="bold",
            ha="left",
        )

    ax.axvline(27, color="#c8c8c8", linestyle="--", linewidth=1.2, zorder=0)

    ymax = len(DRIVER_KEYS_ORDER) * step - group_gap + 0.15
    ax.set_xlim(0, 48)
    ax.set_ylim(-0.15, ymax)
    ax.invert_yaxis()
    ax.set_xticks([0, 10, 20, 30, 40])
    ax.set_xticklabels(["0%", "10%", "20%", "30%", "40%"], fontsize=12)
    ax.set_xlabel("Share of purchase decision (%)", fontsize=12)
    y_row_centers = [i * step + 0.375 for i in range(len(DRIVER_KEYS_ORDER))]
    ax.set_yticks(y_row_centers)
    ax.set_yticklabels(DRIVER_KEYS_ORDER, fontsize=14)
    plt.setp(ax.get_yticklabels(), ha="right")
    ax.tick_params(axis="y", pad=8)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Callouts: dedicated right panel (no overlap with bars / legend)
    callout_style = dict(boxstyle="round,pad=0.5", linewidth=0)
    side_notes = [
        (
            "Survey: 48% picked themed\ngiveaways as top promo —\nfor Y1 the promo IS\nthe product",
            "#D4EDDA",
            "#155724",
            0.88,
        ),
        (
            "Social was underweighted:\n18% named social top driver;\n80% discover via social\n— now 14% in model",
            "#F8F9FA",
            "#6C757D",
            0.52,
        ),
        (
            "1h21 UNCC→Bojangles:\n34 min Blue Line +\nlast-mile bus/walk.\nCTC shuttle ~49–54 min\ntotal • $350–500/game",
            "#FFF3CD",
            "#856404",
            0.16,
        ),
    ]
    for txt, bg, fg, y0 in side_notes:
        ax_side.text(
            0.02,
            y0,
            txt,
            transform=ax_side.transAxes,
            fontsize=10,
            color=fg,
            ha="left",
            va="center",
            bbox={**callout_style, "facecolor": bg, "edgecolor": "none"},
        )

    fig.legend(
        handles=[
            Patch(facecolor=steel_blue, edgecolor="none", label="Charlotte FC + Knights (established)"),
            Patch(facecolor=crown_purple, edgecolor="none", label="Charlotte Crown Year 1 (survey-corrected)"),
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, 0.215),
        ncol=2,
        frameon=False,
        fontsize=11,
        handlelength=1.15,
        columnspacing=2.2,
    )

    fig.suptitle(
        "What drives ticket sales — established teams vs. Crown Year 1",
        fontsize=18,
        fontweight="bold",
        y=0.96,
    )
    fig.text(
        0.5,
        0.905,
        "FC/Knights from MLR + priors → Crown Year 1 from Spring 2026 survey + UNCC→Bojangles transit (CROWN_DRIVER_WEIGHTS_PRIOR)",
        ha="center",
        fontsize=12,
        color="#555",
    )
    fig.text(
        0.5,
        0.868,
        "Transit 20% vs 5% for established teams; star 7% until May 9 rosters. FC/Knights keep Blue Line access — Crown leans price + social + promo.",
        ha="center",
        fontsize=11,
        color="#7B5EA7",
        fontweight="bold",
    )
    fig.text(
        0.5,
        0.048,
        textwrap.fill(
            "FC/Knights shares from MLR on 217 home games (DRIVER_WEIGHTS_PRIOR). Crown shares from CROWN_DRIVER_WEIGHTS_PRIOR: "
            "survey (promo, price, social) + transit: UNCC→Bojangles ~81 min today (34 min Blue Line to CTC, then Bus 17/27 wait/ride + walk) vs ~10 min drive; "
            "game-day shuttle from CTC only (~49–54 min full journey) or campus-direct ~23–25 min (~$500–650/game). Planning priors — update after homestand + gate (target: Game 5).",
            100,
        ),
        ha="center",
        fontsize=10,
        color="#666",
    )

    PRES_DIR.mkdir(parents=True, exist_ok=True)
    path = PRES_DIR / "P15_driver_weights_comparison.png"
    if save:
        fig.savefig(
            path,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
            dpi=DPI,
            pad_inches=0.55,
        )
        plt.close(fig)
        return path
    plt.close(fig)
    return None


if __name__ == "__main__":
    main()
    plot_driver_weights_comparison()
