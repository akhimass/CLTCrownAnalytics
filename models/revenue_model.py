# models/revenue_model.py
from __future__ import annotations

# Before/after Crown revenue scenarios — run: python -m models.revenue_model
import logging
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np
import pandas as pd

from config.settings import settings
from config.constants import (
    BASELINE_AVG_TICKET, STRATEGY_AVG_TICKET,
    BASELINE_ANCILLARY, STRATEGY_ANCILLARY,
    BASELINE_FILL_RATE, STRATEGY_FILL_RATE,
    PROMO_MULTIPLIERS, VENUES,
)
from pipelines.build_master_calendar import CROWN_HOME_GAMES, get_crown_home_penalty_lookup

logger = logging.getLogger(__name__)

CAPACITY = VENUES["crown"]["capacity"]  # 3,500


@dataclass
class GameRevenue:
    date: str
    opponent: str
    scenario: str
    fill_rate: float
    attendance: int
    avg_ticket: float
    ticket_revenue: float
    ancillary_revenue: float
    total_revenue: float
    promo_type: str = "none"
    has_conflict: bool = False
    conflict_penalty_pct: float = 0.0
    notes: str = ""


@dataclass
class ScenarioSummary:
    name: str
    games: List[GameRevenue] = field(default_factory=list)

    @property
    def total_attendance(self) -> int:
        return sum(g.attendance for g in self.games)

    @property
    def avg_fill_rate(self) -> float:
        return np.mean([g.fill_rate for g in self.games])

    @property
    def ticket_revenue(self) -> float:
        return sum(g.ticket_revenue for g in self.games)

    @property
    def ancillary_revenue(self) -> float:
        return sum(g.ancillary_revenue for g in self.games)

    @property
    def total_revenue(self) -> float:
        return self.ticket_revenue + self.ancillary_revenue

    @property
    def avg_game_revenue(self) -> float:
        return self.total_revenue / len(self.games) if self.games else 0

    def to_dict(self) -> dict:
        return {
            "scenario": self.name,
            "total_games": len(self.games),
            "total_attendance": self.total_attendance,
            "avg_fill_rate_pct": round(self.avg_fill_rate * 100, 1),
            "ticket_revenue": round(self.ticket_revenue),
            "ancillary_revenue": round(self.ancillary_revenue),
            "total_revenue": round(self.total_revenue),
            "avg_game_revenue": round(self.avg_game_revenue),
        }


# Game-level promo assignments for Strategy A (recommended calendar)
STRATEGY_A_PROMOS = {
    "2026-05-21": ("opener_night",   "Opening Night — Crown Inaugural Game"),
    "2026-05-25": ("giveaway",       "Crown Crown Giveaway Night"),
    "2026-05-30": ("theme_night",    "Women in Sports Night"),
    "2026-06-03": ("community_night","HBCU Day + Student Discount"),
    "2026-06-06": ("giveaway",       "Poster Giveaway"),
    "2026-06-14": ("discount_price", "Family Sunday — Kids $5"),
    "2026-06-17": ("community_night","NC Rivalry Night vs. Greensboro"),
    "2026-07-30": ("giveaway",       "Jersey Night Giveaway"),
    "2026-08-01": ("theme_night",    "First Responders Night"),
    "2026-08-02": ("discount_price", "Student Sunday — UNCC/JCSU"),
    "2026-08-05": ("star_feature",   "Star Player Spotlight + Autographs"),
    "2026-08-08": ("theme_night",    "Latinx Heritage Night"),
    "2026-08-09": ("community_night","Youth Basketball Clinic Day"),
    "2026-08-13": ("giveaway",       "Bobblehead Giveaway"),
    "2026-08-15": ("theme_night",    "Fan Appreciation Night"),
    "2026-08-22": ("giveaway",       "Championship Shirt Giveaway"),
    "2026-08-23": ("discount_price", "Season Finale — $10 All Seats"),
}

# Shuttle adds a transit score boost (small but meaningful for student segment)
SHUTTLE_LIFT = 0.04  # +4% attendance from Blue Line shuttle

class RevenueModel:
    def __init__(self):
        self.scenarios: Dict[str, ScenarioSummary] = {}
        self._penalty_lookup: dict[str, float] | None = None

    def _conflict_penalty(self, date_str: str) -> float:
        """Time-aware fractional penalty from master calendar (canonical with cannibalization_pct)."""
        if self._penalty_lookup is None:
            self._penalty_lookup = get_crown_home_penalty_lookup()
        return float(self._penalty_lookup.get(date_str, 0.0))

    def build_baseline(self) -> ScenarioSummary:
        """Scenario 1: No promo strategy, standard pricing."""
        scenario = ScenarioSummary("Baseline (No Strategy)")

        for game in CROWN_HOME_GAMES:
            date_str = game["date"]
            conflict_pct = self._conflict_penalty(date_str)
            fill = (BASELINE_FILL_RATE * (1 - conflict_pct))
            attendance = int(CAPACITY * fill)
            ticket_rev = attendance * BASELINE_AVG_TICKET
            ancillary_rev = attendance * BASELINE_ANCILLARY

            scenario.games.append(GameRevenue(
                date=date_str,
                opponent=game["opponent"],
                scenario="baseline",
                fill_rate=fill,
                attendance=attendance,
                avg_ticket=BASELINE_AVG_TICKET,
                ticket_revenue=ticket_rev,
                ancillary_revenue=ancillary_rev,
                total_revenue=ticket_rev + ancillary_rev,
                has_conflict=bool(conflict_pct),
                conflict_penalty_pct=round(conflict_pct * 100, 1),
            ))

        self.scenarios["baseline"] = scenario
        return scenario

    def build_strategy_a(self) -> ScenarioSummary:
        """Scenario 2: Promo calendar + pricing packages."""
        scenario = ScenarioSummary("Strategy A (Promo + Pricing)")

        for game in CROWN_HOME_GAMES:
            date_str = game["date"]
            promo_type, promo_label = STRATEGY_A_PROMOS.get(date_str, ("none", ""))
            promo_mult = PROMO_MULTIPLIERS.get(promo_type, 1.0)
            conflict_pct = self._conflict_penalty(date_str)

            # Special opener multiplier
            if promo_type == "opener_night":
                promo_mult = 1.40  # inaugural game novelty bump

            fill = min(STRATEGY_FILL_RATE * promo_mult * (1 - conflict_pct), 1.0)
            attendance = int(CAPACITY * fill)

            # Pricing: discount nights have lower avg ticket
            if promo_type == "discount_price":
                avg_price = 10.00
            elif promo_type == "opener_night":
                avg_price = 20.00  # opener commands premium
            else:
                avg_price = STRATEGY_AVG_TICKET

            ticket_rev = attendance * avg_price
            ancillary_rev = attendance * STRATEGY_ANCILLARY  # bundles boost this

            scenario.games.append(GameRevenue(
                date=date_str,
                opponent=game["opponent"],
                scenario="strategy_a",
                fill_rate=fill,
                attendance=attendance,
                avg_ticket=avg_price,
                ticket_revenue=ticket_rev,
                ancillary_revenue=ancillary_rev,
                total_revenue=ticket_rev + ancillary_rev,
                promo_type=promo_type,
                has_conflict=bool(conflict_pct),
                conflict_penalty_pct=round(conflict_pct * 100, 1),
                notes=promo_label,
            ))

        self.scenarios["strategy_a"] = scenario
        return scenario

    def build_strategy_b(self) -> ScenarioSummary:
        """Scenario 3: Strategy A + Blue Line shuttle + star player campaign."""
        a = self.scenarios.get("strategy_a") or self.build_strategy_a()
        scenario = ScenarioSummary("Strategy B (Full: Shuttle + Star Marketing)")

        for g in a.games:
            # Shuttle adds ~4% attendance uplift (student/transit-accessible segment)
            new_fill = min(g.fill_rate + SHUTTLE_LIFT, 1.0)
            new_att = int(CAPACITY * new_fill)
            new_ticket_rev = new_att * g.avg_ticket
            new_ancillary = new_att * STRATEGY_ANCILLARY

            scenario.games.append(GameRevenue(
                date=g.date,
                opponent=g.opponent,
                scenario="strategy_b",
                fill_rate=new_fill,
                attendance=new_att,
                avg_ticket=g.avg_ticket,
                ticket_revenue=new_ticket_rev,
                ancillary_revenue=new_ancillary,
                total_revenue=new_ticket_rev + new_ancillary,
                promo_type=g.promo_type,
                has_conflict=g.has_conflict,
                conflict_penalty_pct=g.conflict_penalty_pct,
                notes=g.notes + " + Shuttle",
            ))

        self.scenarios["strategy_b"] = scenario
        return scenario

    def run_all(self) -> pd.DataFrame:
        self.build_baseline()
        self.build_strategy_a()
        self.build_strategy_b()

        summary_rows = [s.to_dict() for s in self.scenarios.values()]
        return pd.DataFrame(summary_rows)

    def game_level_comparison(self) -> pd.DataFrame:
        """Game-by-game comparison across all scenarios."""
        rows = []
        for sname, scenario in self.scenarios.items():
            for g in scenario.games:
                rows.append({
                    "date": g.date,
                    "opponent": g.opponent,
                    "scenario": sname,
                    "attendance": g.attendance,
                    "fill_rate_pct": round(g.fill_rate * 100, 1),
                    "avg_ticket": g.avg_ticket,
                    "ticket_revenue": round(g.ticket_revenue),
                    "ancillary_revenue": round(g.ancillary_revenue),
                    "total_revenue": round(g.total_revenue),
                    "promo_type": g.promo_type,
                    "has_conflict": g.has_conflict,
                    "conflict_penalty_pct": g.conflict_penalty_pct,
                    "notes": g.notes,
                })
        return pd.DataFrame(rows)

    def uplift_table(self) -> pd.DataFrame:
        """Compare each strategy to baseline."""
        if not self.scenarios:
            self.run_all()
        base = self.scenarios["baseline"]
        rows = []
        for key, s in self.scenarios.items():
            if key == "baseline":
                continue
            rows.append({
                "scenario": s.name,
                "baseline_revenue": base.total_revenue,
                "strategy_revenue": s.total_revenue,
                "revenue_uplift": s.total_revenue - base.total_revenue,
                "uplift_pct": round((s.total_revenue - base.total_revenue) / base.total_revenue * 100, 1),
                "additional_fans": s.total_attendance - base.total_attendance,
                "avg_fill_strategy_pct": round(s.avg_fill_rate * 100, 1),
                "avg_fill_baseline_pct": round(base.avg_fill_rate * 100, 1),
            })
        return pd.DataFrame(rows)

    def print_summary(self):
        summary = self.run_all()
        print("\n" + "="*60)
        print("CROWN REVENUE MODEL — SCENARIO COMPARISON")
        print("="*60)
        print(summary.to_string(index=False))
        print("\nUPLIFT vs. BASELINE:")
        print(self.uplift_table().to_string(index=False))

    def save(self):
        game_df = self.game_level_comparison()
        path = settings.DATA_PROCESSED / "revenue_scenarios.csv"
        game_df.to_csv(path, index=False)
        logger.info(f"Saved revenue scenarios → {path}")
        summary = self.run_all()
        summary.to_csv(settings.DATA_PROCESSED / "revenue_summary.csv", index=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    model = RevenueModel()
    model.print_summary()
    model.save()
