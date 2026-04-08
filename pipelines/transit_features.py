# pipelines/transit_features.py
"""
Computes transit accessibility features for each Crown home game.
Uses static CATS GTFS data (downloadable from charlottenc.gov/CATS).

Without GTFS data available, falls back to manually computed values.

Key output: transit_penalty column quantifying how much harder
Bojangles Coliseum is to reach vs. Blue Line-served venues.
"""
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from config.constants import TRANSIT_MINUTES, TRANSIT_SCORE, VENUES, SHUTTLE_COST_PER_GAME

logger = logging.getLogger(__name__)

# Travel times (minutes) from key origin zip codes to each venue via transit
# Based on CATS + Moovit segment checks (see README / P8).
#
# UNCC (28213) → Bojangles, no shuttle — ~81 min (1h21) door-to-door, legs:
#   walk to station 3 + Blue Line UNCC→CTC 34 + wait Bus 17/27 ~10–15 + bus leg ~25–28 + walk 8
#   (sum here: 3+34+12+26+8 = 83; model uses 81 as planning anchor)
# UNCC → FC/Knights: Blue Line UNCC→CTC ~34 + short walk to venue (no transfer) ≈ 34 total.
TRANSIT_MATRIX = {
    # (origin_zip, venue) -> {walk_min, wait_min, ride_min, transfers}
    ("28213", "crown"):    {"walk": 11, "wait": 12, "ride": 58, "transfers": 2},  # UNCC → Bojangles (81 total)
    ("28213", "fc"):       {"walk": 5,  "wait": 5,  "ride": 24, "transfers": 0},  # 34
    ("28213", "knights"):  {"walk": 5,  "wait": 5,  "ride": 24, "transfers": 0},  # 34
    ("28202", "crown"):    {"walk": 8,  "wait": 10, "ride": 20, "transfers": 1},  # Uptown → Bojangles ~38
    ("28202", "fc"):       {"walk": 10, "wait": 3,  "ride": 5,  "transfers": 0},  # Near BofA
    ("28202", "knights"):  {"walk": 8,  "wait": 3,  "ride": 5,  "transfers": 0},
    ("28205", "crown"):    {"walk": 7,  "wait": 8,  "ride": 15, "transfers": 1},  # NoDa/Plaza
    ("28205", "fc"):       {"walk": 5,  "wait": 5,  "ride": 20, "transfers": 0},
    ("28205", "knights"):  {"walk": 5,  "wait": 5,  "ride": 20, "transfers": 0},
    ("28204", "crown"):    {"walk": 8,  "wait": 10, "ride": 20, "transfers": 1},  # Midtown
    ("28204", "fc"):       {"walk": 8,  "wait": 5,  "ride": 10, "transfers": 0},
    ("28204", "knights"):  {"walk": 8,  "wait": 5,  "ride": 10, "transfers": 0},
}

# Estimated population in each zip code that's transit-dependent (no car)
ZIP_TRANSIT_POPULATION = {
    "28213": 45_000,  # UNCC area (~30K students + residents)
    "28202": 12_000,  # Uptown residents
    "28205": 28_000,  # NoDa, Plaza-Midwood
    "28204": 22_000,  # Midtown, Elizabeth
}


def compute_total_travel(origin_zip: str, venue: str) -> float:
    """Returns total door-to-door transit minutes."""
    key = (origin_zip, venue)
    if key not in TRANSIT_MATRIX:
        return 60.0  # default conservative estimate
    t = TRANSIT_MATRIX[key]
    return t["walk"] + t["wait"] + t["ride"]


def compute_transit_penalty(venue: str = "crown", reference: str = "fc") -> float:
    """
    Returns the weighted average additional travel time to reach venue
    vs. the reference venue, across all key zip codes.
    Weighted by transit-dependent population.
    """
    total_pop = sum(ZIP_TRANSIT_POPULATION.values())
    weighted_diff = 0.0

    for zip_code, pop in ZIP_TRANSIT_POPULATION.items():
        time_venue = compute_total_travel(zip_code, venue)
        time_ref   = compute_total_travel(zip_code, reference)
        weighted_diff += (time_venue - time_ref) * (pop / total_pop)

    return round(weighted_diff, 1)


def compute_accessible_population(venue: str, max_minutes: float = 45.0) -> dict:
    """
    Estimate how many people can reach this venue via transit within max_minutes.
    """
    reachable = 0
    for zip_code, pop in ZIP_TRANSIT_POPULATION.items():
        travel = compute_total_travel(zip_code, venue)
        if travel <= max_minutes:
            reachable += pop

    return {
        "venue": venue,
        "max_minutes_threshold": max_minutes,
        "reachable_population": reachable,
        "total_transit_population": sum(ZIP_TRANSIT_POPULATION.values()),
        "reachable_pct": round(reachable / sum(ZIP_TRANSIT_POPULATION.values()) * 100, 1),
    }


def transit_summary() -> pd.DataFrame:
    """Compare transit accessibility across all Charlotte venues."""
    venues = ["crown", "fc", "knights"]
    rows = []
    for v in venues:
        info = compute_accessible_population(v)
        rows.append({
            "venue": VENUES[v]["name"],
            "transit_score": TRANSIT_SCORE[v],
            "avg_travel_min_from_uncc": compute_total_travel("28213", v),
            "avg_travel_min_from_uptown": compute_total_travel("28202", v),
            "transit_penalty_vs_fc": compute_transit_penalty(v, "fc"),
            "reachable_transit_pop": info["reachable_population"],
            "reachable_pct": info["reachable_pct"],
            "has_direct_lightrail": TRANSIT_SCORE[v] == 2,
            "silver_line_planned": v == "crown",
        })
    return pd.DataFrame(rows)


def shuttle_impact_estimate(
    shuttle_origin: str = "CTC (uptown Blue Line)",
    games_per_season: int = 17,
    riders_per_trip: int = 25,
    trips_per_game: int = 4,
    ticket_price: float = 14.0,
    ancillary_per_head: float = 7.0,
) -> dict:
    """
    Estimate incremental revenue from running a Crown shuttle from the uptown hub (CTC) to Bojangles Coliseum.
    """
    riders_per_game = riders_per_trip * trips_per_game
    season_riders   = riders_per_game * games_per_season
    cost_per_game   = SHUTTLE_COST_PER_GAME
    season_cost     = cost_per_game * games_per_season

    ticket_rev   = season_riders * ticket_price
    ancillary    = season_riders * ancillary_per_head
    gross_uplift = ticket_rev + ancillary
    net_uplift   = gross_uplift - season_cost

    return {
        "shuttle_origin":       shuttle_origin,
        "riders_per_game":      riders_per_game,
        "season_riders":        season_riders,
        "season_shuttle_cost":  season_cost,
        "incremental_ticket_rev": round(ticket_rev),
        "incremental_ancillary":  round(ancillary),
        "gross_revenue_uplift":   round(gross_uplift),
        "net_revenue_uplift":     round(net_uplift),
        "roi_pct": round(net_uplift / season_cost * 100, 1),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("\nTRANSIT COMPARISON:")
    print(transit_summary().to_string(index=False))

    penalty = compute_transit_penalty("crown", "fc")
    print(f"\nCrown transit penalty vs. FC: +{penalty} min avg travel time")

    print("\nSHUTTLE IMPACT ESTIMATE:")
    shuttle = shuttle_impact_estimate()
    for k, v in shuttle.items():
        print(f"  {k}: {v}")
