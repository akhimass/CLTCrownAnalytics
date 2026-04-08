# CLTCrownAnalytics

**Sports business analytics for Charlotte’s indoor arena economy** — with a primary focus on the **Charlotte Crown** (women’s professional basketball, **UpShot League**) and comparative context from **Charlotte FC**, **Charlotte Knights**, and the **Charlotte Checkers** (AHL).

This repository is the quantitative backbone for planning Crown’s inaugural season: attendance drivers, revenue scenarios, same-night competition with MLS and MiLB, transit and shuttle economics, and survey-informed priors. It treats Crown as a *new* franchise in a *mature* sports market, using peer data where Crown history does not yet exist.

---

## Why this project exists

| Stakeholder | Role in the model |
|-------------|-------------------|
| **Charlotte Crown** | Primary subject — Bojangles Coliseum, ~3,500 capacity, UpShot League 2026 schedule, pricing and promo strategy. |
| **UpShot League** | League context — inaugural rosters, rivalries (e.g. Greensboro), and season structure that shape marketing and driver weights. |
| **Charlotte Checkers** | **Peer benchmark** — another major tenant at **Spectrum Center** with HockeyTech game data; used for transit comparisons, market density, and “same city, different venue” narratives in `transit_features` and charts. |
| **Charlotte FC / Knights** | **Cannibalization and calendar** — same-night overlap drives time-aware conflict penalties on Crown home dates. |

The goal is defensible *business* outputs: fill-rate and revenue ranges, conflict-night planning, and access equity (UNCC → Bojangles vs Blue Line peers), not just charts.

---

## Repository

**Suggested GitHub name:** [`CLTCrownAnalytics`](https://github.com/YOUR_ORG/CLTCrownAnalytics) — rename the remote when you publish:

```bash
git init
git remote add origin https://github.com/YOUR_ORG/CLTCrownAnalytics.git
git branch -M main
git add .
git commit -m "Initial commit: Charlotte Crown sports business analytics"
git push -u origin main
```

*(If this folder already has a remote, use `git remote set-url origin …` instead.)*

---

## Quickstart

```bash
pip install -r requirements.txt

# Full pipeline (default: `SPORTS_SEED_ONLY=True` in config — FC/Knights from seed only)
python main.py

# To allow live FC/Knights scraping, set SPORTS_SEED_ONLY=False in config/constants.py, then:
python main.py --scrape

# Individual modules
python main.py --revenue          # revenue scenarios only
python main.py --cannibalization  # conflict impact analysis
python main.py --transit          # transit accessibility analysis
python main.py --models           # train MLR + RF only
python main.py --viz-only         # regenerate charts only
```

---

## What it does

### 1. Data pipeline (`scrapers/`, `pipelines/`)
- **FC & Knights:** by default **no network** — `scrapers/seed_data.py` only (`SPORTS_SEED_ONLY`). Optional fbref / Baseball Cube when that flag is off.
- **Checkers:** HockeyTech JSON API when run with scraping enabled (raw JSON under `data/raw/charlotte_checkers_*`).
- Merges schedules into `master_calendar.csv` with same-day **FC / Knights** conflict flags for every **Crown home** game.
- Uses Playwright for JS-rendered pages (e.g. milb.com promo calendar) where needed.

### 2. Attendance models (`models/`)
| Model | Purpose |
|-------|---------|
| `AttendanceMLR` | OLS regression — interpretable coefficients + p-values for driver ranking |
| `AttendanceRF` | Random Forest + GBM ensemble — feature importance, SHAP support |
| `CannibalizationAnalyzer` | Paired t-test + OLS measuring attendance loss on shared game nights |
| `RevenueModel` | Three-scenario before/after revenue model (Baseline → Strategy A → Strategy B) |

### 3. Revenue scenarios (illustrative — refresh with live gates)
| Scenario | Avg fill rate | Season revenue | vs. baseline |
|----------|---------------|----------------|--------------|
| Baseline (no strategy) | 47.9% | $599,004 | — |
| Strategy A (promo + pricing) | 78.9% | $969,759 | +$370,755 (+62%) |
| Strategy B (+ shuttle + star marketing) | 82.8% | $1,017,036 | +$418,032 (+70%) |

### 4. Transit analysis (`pipelines/transit_features.py`)
Quantifies Crown’s structural transit disadvantage vs. FC, Knights, and **Checkers**-style uptown venues. Bojangles Coliseum is **bus-dependent** from UNCC (Blue Line + Bus 17/27 + walk). Deck shuttle ROI assumes a **CTC** uptown loop for the last mile.

### 5. Visualizations (`viz/`, `reports/`)
| Chart | File |
|-------|------|
| Driver weights bar chart | `01_driver_weights.png` |
| FC promo night benchmark | `02_promo_benchmark.png` |
| Promo type multipliers | `03_promo_multipliers.png` |
| Transit comparison | `04_transit_comparison.png` |
| Cannibalization matrix | `05_cannibalization_matrix.png` |
| Revenue scenario comparison | `06_scenario_comparison.png` |
| Game-by-game attendance + revenue | `07_game_by_game.png` |
| Fill rate waterfall | `08_fill_rate_waterfall.png` |
| Revenue breakdown (donut) | `09_revenue_breakdown.png` |
| Conflict revenue impact scatter | `10_conflict_revenue_impact.png` |
| Conflict calendar heatmap | `11_conflict_calendar.png` |
| Schedule table | `12_schedule_table.png` |

Presentation deck assets live under `reports/presentation/` (e.g. P7 conflict table, P8 transit shuttle, P15 driver weights).

---

## Key findings (planning priors)

### Crown Year 1 driver weights (survey-corrected; `CROWN_DRIVER_WEIGHTS_PRIOR`)
1. **Promotions & theme nights — 34%** — Survey: themed giveaways as top promo; for an inaugural team the promo is the product.
2. **Price & total COA — 25%** — Price sensitivity + $14-style tickets + free parking vs uptown peers.
3. **Transportation & transit — 20%** — ~81 min UNCC→Bojangles by transit vs ~10 min by car; CTC shuttle and optional campus-direct shuttle scenarios.
4. **Social & community — 14%** — Social discovery and group motivation; calibrated from survey.
5. **Star power & opponent — 7%** — Low until rosters stabilize; FC/Knights peer mix remains in `DRIVER_WEIGHTS_PRIOR` for benchmarks.

### Cannibalization (Crown vs MLS / MiLB same night)
Time-aware penalties in `config.constants.CROWN_CONFLICT_PENALTIES` (see `build_master_calendar.compute_time_aware_cannibal_penalty`): **FC same-time 12%**, **FC same-evening 8%**, **Knights same-time 5%**, **Knights staggered 2%**, Leagues Cup adjacent **6%**; combined cap **30%**. Tuned for **limited audience overlap** vs generic market studies — validate after Crown gate data exists.

### Transit (UNCC → venues)
Blue Line UNCC→CTC ~**34 min**; full UNCC→Bojangles transit ~**81 min** today; game-day shuttle from **CTC** targets ~**49–54 min** total journey. See README tables in-repo for leg-by-leg detail.

### Strategy recommendations
1. Theme nights and giveaways on the full home slate  
2. Entry pricing and bundles aligned to survey and COA story  
3. Heavy creative on **FC / Knights conflict nights** (see `master_calendar.csv`)  
4. CTC shuttle economics (`SHUTTLE_*` in `config/constants.py`)  
5. Social-first discovery and roster-driven beats after league announcements  

---

## Repo structure

```
CLTCrownAnalytics/   # or crown-analytics/ locally
├── scrapers/           # FC, Knights, Checkers scrapers + seed data
├── models/             # MLR, RF, cannibalization, revenue model, feature engineering
├── pipelines/          # Master calendar, transit, survey aggregates, pipeline runner
├── viz/                # Chart generation + presentation charts
├── config/             # Constants and settings
├── tests/              # pytest suite
├── analysis/           # Driver narrative / CLI summaries
├── data/
│   ├── raw/            # Scraped HTML/JSON (incl. Checkers HockeyTech)
│   └── processed/      # Game logs, master calendar, model outputs
├── reports/            # PNG charts, generated markdown, presentation/
├── main.py
├── Makefile
└── requirements.txt
```

---

## Adding real Crown attendance (post-season)

Once you have real Crown game attendance, extend `scrapers/seed_data.py` with Crown rows and retrain:

```python
CROWN_SEED_DATA = {
    2026: [
        {"date": "2026-05-21", "opponent": "Jacksonville Waves", "attendance": 2800, "result": "W"},
        # ...
    ]
}
```

Then run `python main.py` — driver weights and scenarios will re-center on **observed** Crown demand instead of priors alone.

---

## License and disclaimer

Models, priors, and dollar figures are **planning tools**, not audited financial statements. **UpShot League**, **Charlotte Crown**, **Charlotte Checkers**, and other team names are used for descriptive analytics context; this repo is not necessarily affiliated with those entities unless explicitly stated by the maintainer.

---

*CLTCrownAnalytics — sports business analytics at the intersection of the UpShot League, Charlotte Crown, and Charlotte’s wider arena and transit ecosystem.*
