# config/constants.py
from __future__ import annotations

# Project-wide constants — edit here, nowhere else.
from datetime import date

# ── Venues ────────────────────────────────────────────────────────────────────
VENUES = {
    "crown":    {"name": "Bojangles Coliseum", "capacity": 3_500,  "lat": 35.2084, "lon": -80.8302},
    "fc":       {"name": "Bank of America Stadium", "capacity": 38_000, "lat": 35.2258, "lon": -80.8528},
    "knights":  {"name": "Truist Field",       "capacity": 10_200, "lat": 35.2279, "lon": -80.8481},
    "checkers": {"name": "Spectrum Center",    "capacity": 19_500, "lat": 35.2255, "lon": -80.8393},
}

# ── Season windows ─────────────────────────────────────────────────────────────
CROWN_SEASON = {"start": date(2026, 5, 21), "end": date(2026, 8, 23)}
SCRAPE_YEARS = [2022, 2023, 2024, 2025]  # 3-year lookback for FC/Knights (ignored when SPORTS_SEED_ONLY)
# FC + Knights: never call fbref / Baseball Cube — use scrapers/seed_data only.
SPORTS_SEED_ONLY = True

# ── Transit ────────────────────────────────────────────────────────────────────
# Minutes from UNCC Main Station area to each venue via transit (planning anchors).
# FC/Knights: ~34 min Blue Line UNCC→CTC + short walk to venue (Moovit; no transfer).
# Crown (no shuttle): ~81 min (1h21) — Blue Line 34 + Bus 17/27 wait/ride + walk; see transit_features.
# Crown + CTC game-day shuttle (full journey): ~49–54 min (34 Blue Line + ~15–20 last mile at CTC).
TRANSIT_MINUTES = {
    "crown":    81,   # UNCC → Bojangles no shuttle (door-to-door)
    "fc":       34,   # UNCC → Bank of America Stadium via Blue Line + walk
    "knights":  34,   # UNCC → Truist Field via Blue Line + walk (peer band)
    "checkers": 32,   # UNCC → Spectrum / uptown venues (approx.; slightly shorter walk than FC)
}
TRANSIT_SCORE = {
    # 0 = drive-only, 1 = bus w/ transfer, 2 = direct light rail
    "crown":    1,
    "fc":       2,
    "knights":  2,
    "checkers": 2,
}

# ── Modeling ──────────────────────────────────────────────────────────────────
RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5

# FC/Knights literature + MLR anchors (217 home games) — used for P1, benchmarks, peer comparison
DRIVER_WEIGHTS_PRIOR = {
    "promotions":    0.35,
    "star_power":    0.27,
    "price":         0.23,
    "social":        0.10,
    "transit":       0.05,
}

# Crown Year 1 — survey-corrected planning priors (sum 100%; refresh after homestand / gate data)
CROWN_DRIVER_WEIGHTS_PRIOR = {
    "promotions":    0.34,
    "star_power":    0.07,
    "price":         0.25,
    "social":        0.14,
    "transit":       0.20,
}

# ── Revenue assumptions ───────────────────────────────────────────────────────
BASELINE_AVG_TICKET   = 17.00
STRATEGY_AVG_TICKET   = 14.00   # lower barrier, drive volume
BASELINE_ANCILLARY    =  4.00   # concessions + merch per head
STRATEGY_ANCILLARY    =  7.00   # bundle add-ons
BASELINE_FILL_RATE    =  0.50
STRATEGY_FILL_RATE    =  0.70
CROWN_HOME_GAMES      = 17   # Charlotte (Bojangles) home dates only
CROWN_SEASON_GAMES    = 34   # full 2026 schedule incl. road (see CROWN_FULL_SCHEDULE_2026)

# ── Promo type multipliers (derived from FC/Knights 3yr data) ─────────────────
PROMO_MULTIPLIERS = {
    "none":             1.00,
    "theme_night":      1.12,
    "giveaway":         1.18,
    "discount_price":   1.25,
    "star_feature":     1.15,
    "community_night":  1.10,
}

# ── Cannibalization (FC ↔ Knights same-day estimates) ─────────────────────────
# Negative = attendance loss when rival game is same night.
#
# FC ↔ Knights pairs: directional priors (league peer overlap); refine when same-day
# game logs support regression (see models/cannibalization.py).
#
# Crown rows: NOT estimated from Crown attendance — there is no Y1 history yet.
# crown_loss_when_fc / crown_loss_when_knights align with CROWN_CONFLICT_PENALTIES fc_same_time /
# knights_same_time for the flag-only helper (scenario_simulator / tests), not the time-aware bars.
CANNIBALIZATION = {
    "fc_loss_when_knights": -0.04,    # FC loses ~4% when Knights same night
    "knights_loss_when_fc": -0.11,    # Knights loses ~11% when FC same night
    "crown_loss_when_fc":   -0.12,    # Crown vs MLS same-time window — calibrated below FC 18% tier
    "crown_loss_when_knights": -0.05, # Crown vs Knights — different product/audience vs MiLB study
}

# Max combined fractional penalty when both same-night flags are set (additive formula below).
CROWN_CONFLICT_PENALTY_CAP = 0.30

# Time-adjusted cannibalization for Crown (fractional penalties, applied from start times).
# Calibrated for Crown Y1: WNBA vs MLS/MiLB audience overlap is limited; survey suggests less
# cross-shopping than generic sports-market priors. Staggered same-day often allows two games.
CROWN_CONFLICT_PENALTIES = {
    "knights_same_time": 0.05,       # Knights home, starts within threshold of Crown tip
    "knights_staggered": 0.02,      # Same calendar day, 2+ hour gap — often both games are feasible
    "fc_same_evening": 0.08,        # FC same day, staggered — wallet-day effect, not either/or
    "fc_same_time": 0.12,           # FC home within same-time window as Crown (rare for Crown slate)
    "leagues_cup_adjacent": 0.06,   # Leagues Cup at BofA same day — light wallet / noise
}

# If abs(crown_start_hour - rival_start_hour) < this (strict), treat as same-time bucket; gap == 2h → staggered.
CROWN_SAME_TIME_THRESHOLD_HOURS = 2.0


def crown_cannibalization_penalty(fc_same_day: int | bool, knights_same_day: int | bool) -> float:
    """
    Fractional attendance reduction applied to Crown fill when big Charlotte teams host same calendar day.

    Formula (planning priors, not Crown gate regression):
        penalty = fc_flag * |crown_loss_when_fc| + kn_flag * |crown_loss_when_knights|
        return min(penalty, CROWN_CONFLICT_PENALTY_CAP)

    Interpretation: expected fill (or normalized attendance) is multiplied by (1 - penalty).

    Note: Master calendar and RevenueModel use time-aware penalties from build_master_calendar
    (cannibalization_pct). This flag-only helper remains for scenario_simulator and quick tests.
    """
    fc = 1 if fc_same_day else 0
    kn = 1 if knights_same_day else 0
    raw = fc * abs(CANNIBALIZATION["crown_loss_when_fc"]) + kn * abs(CANNIBALIZATION["crown_loss_when_knights"])
    return float(min(raw, CROWN_CONFLICT_PENALTY_CAP))


def crown_conflict_fill_multiplier(fc_same_day: int | bool, knights_same_day: int | bool) -> float:
    """Multiply baseline fill / attendance norm by this factor after applying conflict flags."""
    return 1.0 - crown_cannibalization_penalty(fc_same_day, knights_same_day)


# ── Shuttle economics (game-day loop from CTC → Bojangles; see P8 / README) ───
SHUTTLE_COST_PER_GAME = 350.0
SHUTTLE_RIDERS_PER_GAME = 100  # riders_per_trip * trips_per_game from transit model default
SHUTTLE_GAMES_PER_SEASON = CROWN_HOME_GAMES

# Scenario / simulator — confidence band around point attendance estimate
SIMULATOR_ATTENDANCE_CI_FANS = 250  # ± fans when model uncertainty fallback used

# Incremental fill-rate lift when running a Blue Line → Bojangles shuttle program
SHUTTLE_FILL_RATE_LIFT = 0.04

# Concession price benchmarks (Charlotte market; Crown Bojangles-operated, family pricing)
CONCESSION_BENCHMARKS = {
    "crown_baseline": {
        "beer": 7.00,
        "soda": 4.00,
        "hot_dog": 5.00,
        "nachos": 7.00,
        "bundle_available": False,
    },
    "crown_strategy": {
        "beer": 6.00,
        "soda": 3.00,
        "hot_dog": 4.00,
        "nachos": 6.00,
        "bundle_available": True,
        "bundle_price": 15.00,
    },
    "fc_avg": {
        "beer": 14.00,
        "soda": 6.00,
        "hot_dog": 8.00,
        "nachos": 12.00,
        "bundle_available": False,
    },
    "knights_avg": {
        "beer": 9.00,
        "soda": 5.00,
        "hot_dog": 6.00,
        "nachos": 8.00,
        "bundle_available": False,
    },
}

# Value perception index: lower = better value (0 = best, 1 = worst vs FC reference)
CONCESSION_VALUE_INDEX = {
    "crown_baseline": round((7 + 5) / (14 + 8), 2),   # 0.55
    "crown_strategy": round((6 + 4) / (14 + 8), 2),   # 0.45
    "fc": 1.00,
    "knights": round((9 + 6) / (14 + 8), 2),          # 0.68
}

# Parking — Crown at Bojangles Coliseum is FREE (real competitive advantage)
PARKING_COSTS = {
    "crown":    {"min": 0, "max": 0, "avg": 0, "free": True},
    "fc":       {"min": 15, "max": 75, "avg": 35, "free": False},
    "knights":  {"min": 10, "max": 24, "avg": 15, "free": False},
    "checkers": {"min": 10, "max": 30, "avg": 18, "free": False},
}

# Total cost of attendance advantage (ticket + parking), Crown vs peers ($/person)
TOTAL_COA_ADVANTAGE = {
    "crown_vs_fc": 51,
    "crown_vs_knights": 19,
}

# Scenario / report — rough per-person concessions (beer+food midpoint) for COA framing
COA_CONCESSION_AVG_PER_PERSON = {
    "crown": 12.0,
    "fc": 22.0,
    "knights": 15.0,
}
COA_TICKET_ASSUMPTIONS = {
    "crown": 14.0,
    "fc": 30.0,
    "knights": 18.0,
}

# ── UpShot roster / star signal (update after May 9 announcements) ───────────
KNOWN_STAR_PLAYERS = {
    "Taj McWilliams-Franklin": {"tier": 3, "reason": "WNBA HOF, league VP"},
    "Trisha Stafford-Odom": {"tier": 2, "reason": "WNBA player, Crown HC"},
    "Aziaha James": {"tier": 2, "reason": "NC State, top ACC scorer"},
    "Deja Kelly": {"tier": 2, "reason": "UNC, Charlotte native"},
    "Reigan Richardson": {"tier": 2, "reason": "UNCC program alum"},
    "Elise Williams": {"tier": 1, "reason": "Wake Forest, Raleigh native, tryout coverage"},
}

OPPONENT_STAR_PRESENCE = {
    "Jacksonville Waves": {"has_star": False, "star_tier": 0, "notes": "TBD — roster not yet announced"},
    "Savannah Steel": {"has_star": False, "star_tier": 0, "notes": "TBD — roster not yet announced"},
    "Greensboro Groove": {"has_star": False, "star_tier": 0, "notes": "TBD — roster not yet announced"},
}
