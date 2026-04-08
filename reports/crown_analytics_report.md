# Charlotte Crown — Analytics Report (2026 season preview)


## Executive summary

- **Revenue upside**: Strategy A projects **$969,759** season revenue vs. baseline **$599,004**; Strategy B **$1,017,036** (from `RevenueModel`).

- **Cannibalization**: Same-night **Charlotte FC** is associated with roughly **-18%** lower Crown attendance in the synthetic/historical bridge model; **Knights** about **-9%**.

- **Transit gap**: Crown (Bojangles) faces about **+14.4 minutes** weighted average extra travel vs. Bank of America Stadium from key transit-dependent zips (`transit_features`).

- **Shuttle economics**: Estimated **500%** net ROI on a **$5,950** season shuttle budget vs. **$35,700** gross incremental revenue.

- **Driver model fit (MLR)**: OLS R² = **0.271** on normalized FC+Knights fill rates — interpretable ranking; RF used second for non-linear validation (`random_forest_model`).


## Top attendance drivers (MLR, top 3 by |coefficient| share)

| Rank | Driver | Weight % | Evidence | Confidence |
| --- | --- | --- | --- | --- |
| 1 | Transportation / transit access | 28.3% | coef=0.1915, p=3.112e-06 | High (p<0.05) |
| 2 | Evening slot | 14.2% | coef=0.0957, p=3.112e-06 | High (p<0.05) |
| 3 | Promotions (intensity) | 14.2% | coef=0.0957, p=3.112e-06 | High (p<0.05) |

*Literature priors for storytelling (`constants.DRIVER_WEIGHTS_PRIOR`):* promotions=35%, star_power=27%, price=23%, social=10%, transit=5%.


## Revenue scenarios (live `RevenueModel` outputs)

| scenario | total_games | total_attendance | avg_fill_rate_pct | ticket_revenue | ancillary_revenue | total_revenue | avg_game_revenue |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (No Strategy) | 17 | 28524 | 47.9 | 484908 | 114096 | 599004 | 35236 |
| Strategy A (Promo + Pricing) | 17 | 46949 | 78.9 | 641116 | 328643 | 969759 | 57045 |
| Strategy B (Full: Shuttle + Star Marketing) | 17 | 49260 | 82.8 | 672216 | 344820 | 1017036 | 59826 |

**Why the uplift moves:**

- **Strategy A** layers promo multipliers on a higher base fill (`STRATEGY_FILL_RATE`), discount/anchor pricing on select nights, and higher ancillary spend per head.

- **Strategy B** adds the Blue Line shuttle program lift on top of Strategy A attendance.


**Uplift vs. baseline:**

| scenario | baseline_revenue | strategy_revenue | revenue_uplift | uplift_pct | additional_fans | avg_fill_strategy_pct | avg_fill_baseline_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Strategy A (Promo + Pricing) | 599004.0 | 969759.0 | 370755.0 | 61.9 | 18425 | 78.9 | 47.9 |
| Strategy B (Full: Shuttle + Star Marketing) | 599004.0 | 1017036.0 | 418032.0 | 69.8 | 20736 | 82.8 | 47.9 |

## Game-by-game conflict risk (all Crown home games)

| date | opponent | hour | conflict_risk | fc_same_day | knights_same_day | cannibalization_pct | fc_opponent | knights_opponent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-05-21 00:00:00 | Jacksonville Waves | 19 | LOW | 0 | 0 | 0.0 |  |  |
| 2026-05-25 00:00:00 | Greensboro Groove | 19 | MODERATE | 0 | 1 | 0.09 |  | Memphis Redbirds |
| 2026-05-30 00:00:00 | Savannah Steel | 19 | MODERATE | 0 | 1 | 0.09 |  | Gwinnett Stripers |
| 2026-06-03 00:00:00 | Jacksonville Waves | 12 | MODERATE | 0 | 1 | 0.09 |  | Durham Bulls |
| 2026-06-06 00:00:00 | Savannah Steel | 16 | HIGH | 1 | 1 | 0.27 | Chicago Fire FC | Durham Bulls |
| 2026-06-14 00:00:00 | Savannah Steel | 14 | MODERATE | 0 | 1 | 0.09 |  | Oklahoma City Comets |
| 2026-06-17 00:00:00 | Greensboro Groove | 19 | MODERATE | 0 | 1 | 0.09 |  | Columbus Clippers |
| 2026-07-30 00:00:00 | Greensboro Groove | 19 | MODERATE | 0 | 1 | 0.09 |  | Norfolk Tides |
| 2026-08-01 00:00:00 | Savannah Steel | 16 | MODERATE | 0 | 1 | 0.09 |  | Norfolk Tides |
| 2026-08-02 00:00:00 | Jacksonville Waves | 14 | LOW | 0 | 0 | 0.0 |  |  |
| 2026-08-05 00:00:00 | Greensboro Groove | 19 | MODERATE | 0 | 1 | 0.09 |  | Iowa Cubs |
| 2026-08-08 00:00:00 | Savannah Steel | 16 | LOW | 0 | 0 | 0.0 |  |  |
| 2026-08-09 00:00:00 | Savannah Steel | 14 | LOW | 0 | 0 | 0.0 |  |  |
| 2026-08-13 00:00:00 | Jacksonville Waves | 19 | MODERATE | 0 | 1 | 0.09 |  | Durham Bulls |
| 2026-08-15 00:00:00 | Jacksonville Waves | 16 | HIGH | 1 | 1 | 0.27 | Columbus Crew | Durham Bulls |
| 2026-08-22 00:00:00 | Greensboro Groove | 16 | HIGH | 1 | 1 | 0.27 | DC United | Gwinnett Stripers |
| 2026-08-23 00:00:00 | Greensboro Groove | 14 | LOW | 0 | 0 | 0.0 |  |  |

## Cannibalization — what it means for scheduling

| team_affected | team_causing_conflict | n_conflict_games | n_no_conflict_games | mean_attendance_clean | mean_attendance_conflict | delta_fans | delta_pct | t_statistic | p_value | ols_coefficient | ols_p_value | significant | source |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| charlotte_fc | charlotte_knights | 0 | 0 | 24700 | 23712 | -988 | -4.0 |  |  | -988 |  |  | model_estimate |
| charlotte_knights | charlotte_fc | 0 | 0 | 6630 | 5901 | -729 | -11.0 |  |  | -729 |  |  | model_estimate |
| charlotte_crown | charlotte_fc | 0 | 0 | 2275 | 1866 | -409 | -18.0 |  |  | -409 |  |  | model_estimate |
| charlotte_crown | charlotte_knights | 0 | 0 | 2275 | 2071 | -204 | -9.0 |  |  | -204 |  |  | model_estimate |

**Interpretation:** nights when FC or Knights also draw the Charlotte sports entertainment dollar compress Crown trial — lead with stronger promos/pricing and transit ease on those dates rather than expecting organic walk-up.


## Transit gap & shuttle ROI

| venue | transit_score | avg_travel_min_from_uncc | avg_travel_min_from_uptown | transit_penalty_vs_fc | reachable_transit_pop | reachable_pct | has_direct_lightrail | silver_line_planned |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Bojangles Coliseum | 1 | 47 | 36 | 14.4 | 62000 | 57.9 | False | True |
| Bank of America Stadium | 2 | 25 | 18 | 0.0 | 107000 | 100.0 | True | False |
| Truist Field | 2 | 24 | 16 | -0.6 | 107000 | 100.0 | True | False |

**Shuttle scenario (defaults in `shuttle_impact_estimate`):**

| index | value |
| --- | --- |
| shuttle_origin | 7th Street Station |
| riders_per_game | 100 |
| season_riders | 1700 |
| season_shuttle_cost | 5950.0 |
| incremental_ticket_rev | 23800 |
| incremental_ancillary | 11900 |
| gross_revenue_uplift | 35700 |
| net_revenue_uplift | 29750 |
| roi_pct | 500.0 |

**Parking & total cost of attendance:** Crown's free parking at Bojangles Coliseum provides a **~$35 per-person** cost advantage vs. FC (uptown parking avg **$35**) and **~$15** vs. Knights. Combined with lower ticket prices, total cost of attendance is **$40–$51 cheaper per person** than an FC game (see `TOTAL_COA_ADVANTAGE` in `constants`), which is the single strongest value-proposition marketing message available to the Crown in Year 1.


## Value proposition — illustrative night out for two

Using the same ticket + parking + average concession framing as the strategy model (Crown **$14** tickets, **$0** parking; FC **$30** + **$35** parking; Knights **$18** + **$15** parking; concession spend per person from `COA_CONCESSION_AVG_PER_PERSON`):

| Venue | Tickets (2) | Parking | Concessions (2) | Total |
| --- | --- | --- | --- | --- |
| Crown @ Bojangles | $28 | $0 | $36 | $64 |
| Charlotte FC @ BofA | $60 | $35 | $44 | $139 |
| Knights @ Truist | $36 | $15 | $30 | $81 |

Crown is about **54% cheaper than FC** and **~21% cheaper than Knights** for this illustrative couple night out — driven by **free parking**, lower tickets, and a lower concession value index vs. uptown stadiums.


## Recommended promo calendar (Strategy A mapping)

| date | promo_type | description |
| --- | --- | --- |
| 2026-05-21 | opener_night | Opening Night — Crown Inaugural Game |
| 2026-05-25 | giveaway | Crown Crown Giveaway Night |
| 2026-05-30 | theme_night | Women in Sports Night |
| 2026-06-03 | community_night | HBCU Day + Student Discount |
| 2026-06-06 | giveaway | Poster Giveaway |
| 2026-06-14 | discount_price | Family Sunday — Kids $5 |
| 2026-06-17 | community_night | NC Rivalry Night vs. Greensboro |
| 2026-07-30 | giveaway | Jersey Night Giveaway |
| 2026-08-01 | theme_night | First Responders Night |
| 2026-08-02 | discount_price | Student Sunday — UNCC/JCSU |
| 2026-08-05 | star_feature | Star Player Spotlight + Autographs |
| 2026-08-08 | theme_night | Latinx Heritage Night |
| 2026-08-09 | community_night | Youth Basketball Clinic Day |
| 2026-08-13 | giveaway | Bobblehead Giveaway |
| 2026-08-15 | theme_night | Fan Appreciation Night |
| 2026-08-22 | giveaway | Championship Shirt Giveaway |
| 2026-08-23 | discount_price | Season Finale — $10 All Seats |

## Before / after revenue (modeled)

| scenario | baseline_revenue | strategy_revenue | revenue_uplift | uplift_pct | additional_fans | avg_fill_strategy_pct | avg_fill_baseline_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Strategy A (Promo + Pricing) | 599004.0 | 969759.0 | 370755.0 | 61.9 | 18425 | 78.9 | 47.9 |
| Strategy B (Full: Shuttle + Star Marketing) | 599004.0 | 1017036.0 | 418032.0 | 69.8 | 20736 | 82.8 | 47.9 |

**% uplift** reflects higher modeled fill, promo-driven attendance multipliers, and ancillary attach — not a guarantee of realized results.


## Example scenario simulation (single game)

```
{'projected_attendance': 3000, 'fill_rate_pct': 85.71, 'ticket_revenue': 36000.0, 'ancillary_revenue': 21000.0, 'total_revenue': 57000.0, 'confidence_interval': [2584, 3416], 'model_source': 'mlr_pickle', 'total_coa_per_person': 24.0, 'value_vs_fc': 63.0, 'value_vs_knights': 24.0}
```


## Methodology

- **Multiple linear regression (`AttendanceMLR`)** — OLS via statsmodels for coefficients and p-values; Ridge on standardized features for stable predictions. **R² (0.271)** is in-sample explanatory power on FC+Knights normalized attendance; it is *not* Crown-specific validation (no Crown games yet).

- **Random Forest + GBM (`AttendanceRF`)** — captures non-linearities and interactions; permutation importance cross-checks the MLR ranking.

- **Why MLR first, then RF:** MLR gives an interpretable signed ranking for stakeholders; RF stress-tests whether the same factors dominate when allowing flexible functional form.


### RF driver ranking (full table)

| feature | rf_importance | gbm_importance | permutation_importance | weight_pct |
| --- | --- | --- | --- | --- |
| game_number | 0.2667560484502137 | 0.4082229507383868 | -6.661338147750939e-17 | 33.7 |
| parking_avg_cost | 0.24900524194669396 | 0.08419548103597391 | -7.216449660063518e-17 | 16.7 |
| month | 0.11217437621332714 | 0.21877835288017183 | 8.326672684688674e-17 | 16.5 |
| concession_value_index | 0.2364491653519888 | 0.05097983217169592 | 0.012453206303753872 | 14.4 |
| school_session_score | 0.060557419814634736 | 0.05118061132260481 | -1.1102230246251566e-17 | 5.6 |
| is_weekend | 0.04831795918982956 | 0.043672281999819505 | 0.07926600351393481 | 4.6 |
| is_bad_weather | 0.004114512307748242 | 0.05870274852406155 | -1.4988010832439614e-16 | 3.1 |
| is_holiday_weekend | 0.02102578873312176 | 0.037500725176011336 | 0.04823045603988656 | 2.9 |
| opponent_tier | 0.0 | 0.04064673612874919 | 0.0005376167197760518 | 2.0 |
| competing_event_score | 0.0015994879924422117 | 0.006120280022525009 | 0.0563332041554665 | 0.4 |
| parking_free | 0.0 | 0.0 | 2.2204460492503132e-17 | 0.0 |
| social_buzz_score | 0.0 | 0.0 | 0.024402375384988916 | 0.0 |
| has_promo | 0.0 | 0.0 | 0.004070421060681217 | 0.0 |
| has_bundle_offer | 0.0 | 0.0 | 0.0004919553812137379 | 0.0 |
| promo_multiplier | 0.0 | 0.0 | 8.881784197001253e-17 | 0.0 |
| transit_score | 0.0 | 0.0 | 0.056712313436601304 | 0.0 |
| is_evening | 0.0 | 0.0 | 2.7755575615628914e-17 | 0.0 |
| total_coa_vs_fc | 0.0 | 0.0 | 1.3877787807814457e-16 | 0.0 |

## Charts generated with this report

- `13_shuttle_roi.png` — shuttle cost vs. incremental revenue.

- `14_driver_mlr_vs_rf.png` — MLR |coef| share vs. RF importance share.
