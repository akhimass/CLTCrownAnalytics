# Crown Analytics — 5-slide deck (Canva)

Deck order for **Charlotte Crown** investor/stakeholder storytelling. Export charts at 16:9 (repo default **1600×900 @ 150 dpi**) and place on **1920×1080** Canva frames; leave safe margins (~5% inset) so nothing clips on projectors.

**Generate deck assets:**  
`python -m viz.presentation_charts --deck5`  

**Generate every chart (full library):**  
`python -m viz.presentation_charts`  

**Survey data for P12:** Copy your Google Form export to  
`data/raw/crown_survey_responses.csv`  
(same column layout as the form). Re-run the commands above; **`P12_survey_framework.png`** auto-switches from the old “illustrative” placeholder to **live percentages** when that file exists and has ≥3 rows with a valid “most important factor” column.

**`--deck5` now includes:** `P1_driver_weights.png` and `P12_survey_framework.png` (Slide 3 pair).

---

## Business plan ↔ deck mapping (what to paste from the BP)

Use this so investor slides and the written plan tell one story. Section names follow a typical sports / venue BP; rename to match your doc.


| Slide | BP section(s) to pull or mirror                               | What to copy verbatim vs adapt                                                                                                                                                        |
| ----- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1     | **Market opportunity** / **Industry & fan behavior**          | Paste TAM/SAM only if you have real numbers; otherwise **adapt** this slide’s bullets as prose. Cite FC/Knights as **comparables**, not as competitors.                               |
| 2     | **Competitive landscape** / **Calendar risk**                 | **Adapt** overlap counts from the latest `P7` PNG (numbers change when the master calendar changes). Keep the **asymmetry** footnote (Crown vs MLS/MiLB) in BP footnotes or appendix. |
| 3     | **Marketing & sales** / **Customer acquisition**              | **Paste** priorities from **`P12`** (survey: factor, channel, price, promos) plus **`P1`** (model priors). Note P12 is **exploratory** unless the sample is weighted.                    |
| 4     | **Operations & partnerships** / **Go-to-market**              | **Paste** shuttle, parking/COA, opener-as-launch, and promo-calendar bullets into **GTM**; **PGA precedent** supports “city already does this for majors.”                            |
| 5     | **Financial projections** / **Use of funds** / **Milestones** | **Paste** Strategy A/B vs baseline from `P9b` into the financial summary table; **paste** the five decisions as **90-day milestones** or **use-of-funds** bullets.                    |


**Leave-behind:** Export the same PNGs into a **PDF appendix** labeled “Analytics — methodology” so diligence can match chart footnotes to `config/constants.py` and `models/revenue_model.py`.

---

## Presentation images (non-chart assets for Canva)

Charts come from the repo. **Images** below are what to add in Canva for emotion, geography, and credibility. Prefer **your own** or **licensed** photography; avoid unlicensed pro sports marks as hero art if you are not the rights holder.


| Slide | Role              | Suggested image(s)                                                                                                                                        | Notes                                                                                                                     |
| ----- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| 1     | Hero / texture    | Charlotte skyline (uptown) at dusk; or wide shot of a **full stadium** (generic crowd energy, back-of-house angle, or your venue lease line).             | Establishes “major-league city.” Optional: small **map inset** — Charlotte with pin at Bojangles Coliseum.                |
| 1     | Optional triptych | Three small tiles: **soccer night out**, **baseball fireworks night**, **basketball/hoops energy** (stock or league-agnostic).                            | Reinforces “trained market” without over-claiming Crown attendance.                                                       |
| 2     | Hero              | Stylized **May–Aug calendar** texture (Canva element) **or** aerial/map showing **BofA Stadium**, **Truist Field**, **Bojangles Coliseum** as three pins. | Visually encodes “same city, different nights.”                                                                           |
| 2     | Accent            | Semi-transparent **color key** strip matching P6/P7 (teal/blue) if you split charts.                                                                      | Helps eye link PNG to layout.                                                                                             |
| 3     | Primary           | **`P12_survey_framework.png`** (live when `data/raw/crown_survey_responses.csv` exists); pair with **`P1_driver_weights.png`** on a second slide or appendix. | Keep extra photos small — P12 already has four text panels.                                                               |
| 4     | Hero              | **LYNX Blue Line** train or station (CTC / uptown); **UNCC** campus establishing shot if the shuttle story names students.                                | Reinforces access, not “we bought buses” as the headline.                                                                 |
| 4     | Secondary         | **Quail Hollow / PGA** tournament crowd or shuttle bus exterior (event photography you have rights to use).                                               | Pairs with `P13_pga_shuttle_precedent.png`.                                                                               |
| 4     | Icon strip        | Simple icons: **parking P with slash** (free parking), **ticket**, **bus**, **megaphone** (promo).                                                        | Supports COA + shuttle + messaging bullets without extra charts.                                                          |
| 5     | Hero              | **Upward trend** abstract (subtle, on-brand colors) **or** “empty arena → filled arena” diptych (generic).                                                | Do not imply guaranteed results; subtitle should say “modeled scenarios.”                                                 |
| 5     | Close             | **Logo lockup** + **QR** to deck PDF or data room (if applicable).                                                                                        | Standard investor last slide.                                                                                             |


**Global:** One **consistent** color pull from the chart PNGs (teal/blue/dark gray) applied to shapes and icons so the deck feels like one template.

---

## SLIDE 1 — Crown market context

**Charts:** `P11_market_context.png`  

**Purpose:** Charlotte is not a cold market — FC and Knights have already trained fans on promos, star draws, and price/COA tradeoffs.

**Bullets (short):**

- FC: strong sustained fill; promo nights beat flat nights — rhythm matters.
- Knights: repeatable theme nights (fireworks, Thirsty Thursday, etc.) anchor the weekly calendar.
- Same three drivers show up in the data: **promotions**, **opponent/star draw**, **price & night-out cost**.

**So what:** Crown inherits a warm market; the job is execution, not education from zero.

**Speaker note:** P11 is a **single** dense figure — don’t read every sub-chart; land the headline and one proof point per row.

**Business plan:** Use **Market opportunity** + **Comparable markets / fan behavior**. Drop in 1–2 sentences on Charlotte population growth and event appetite only if you have a cited stat; otherwise lean on comparables.

**Presentation images:** Charlotte skyline or “big night out” crowd energy (see table above); optional three-tile promo / sport-night mood board.

---

## SLIDE 2 — Competition context

**Charts:** `P6_conflict_calendar.png` (May–Aug calendar grid), `P7_conflict_impact_table.png` (attendance drag + “most nights are clean”).

**Purpose:** Show **when** Crown shares the market with Charlotte FC or Truist Knights, the **modeled attendance hit** on those nights, and the headline that **same-night overlap is the minority** of the home schedule.

**Bullets:**

- **P6** — Crown home dates vs. FC / Knights same-night flags on the summer calendar (seed calendars; re-check when MLS/MiLB post final grids).
- **P7** — Left: **per-date** modeled drag from the master calendar (`cannibalization_pct` / time-aware penalties). Right: **headline count** of home games with **no** same-calendar-day FC or Knights home game — **read the number from the exported PNG** after `python -m viz.presentation_charts --deck5` (it tracks `build_master`). Footnote band still references planning priors in `CANNIBALIZATION` for methodology; bar heights reflect the calendar model.
- Cannibalization is **asymmetric** — Crown loses more to a big MLS night than FC loses to Crown; footnote on P7 states the FC↔Knights peer comparison.

**So what:** Calendar + impact in one story: **most** home nights have **low** same-day pressure from those two venues; dates with overlap deserve **heavier promo or media** — don’t over-index anxiety on the full season.

**Note:** FC promo / opener benchmarks (**P2**) belong on a **drivers** or **strategy** slide if you want them; they are **not** required for competition context.

**Business plan:** **Competitive landscape** + **Risk factors (calendar / same-night events)**. Mirror the headline stat from P7; put full seed-calendar assumptions in an appendix if investors ask.

**Presentation images:** Calendar texture or Charlotte **three-venue** map (pins); keep chart colors consistent with P6/P7.

---

## SLIDE 3 — Ticket purchase drivers

**Charts (recommended pair):**

1. **`P12_survey_framework.png`** — **Live Google Form results** when `data/raw/crown_survey_responses.csv` is in the repo (Charlotte Crown / Checkers exploratory survey). Left panel: **“most important factor”** for attending sports; right panels: **discovery channel**, **willing price for Crown**, **promotions wanted**, **age + which venue they’d attend on transit/location** + mean score for **notable players** (if column present).
2. **`P1_driver_weights.png`** — **Model priors** (promo / star / price weights) for side-by-side or appendix: “here’s what we assumed before launch; here’s what early respondents said.”

**Purpose:** Pair **stated fan preferences** (P12) with **model structure** (P1). P12 is built by `pipelines/crown_survey_aggregates.py` + `chart_p12_survey_framework()` — refresh by overwriting the CSV and re-running `python -m viz.presentation_charts --deck5` (or full library).

**Canva constraints:**

- **One-slide version:** Use **only P12** (busy but self-contained) **or** only **P1** — not both full-size.
- **Two-slide version (clearer):** Slide 3a = P12 + 3 bullets; Slide 3b = P1 + “how we’ll reconcile after gate data.”
- If P12 text boxes clip at 1080p, **zoom-crop** the right column in Canva or export a **taller** variant later (ask to add a `--tall` export if needed).

**Suggested bullets (after you regenerate P12):**

- Read the **largest bar** on the left (primary decision factor) and **top discovery channel** — align paid/organic mix to those two.
- **Price band** mode from P12 vs. your Strategy A ticket assumption — call out any gap.
- **Promotions** row: themed giveaways vs. drink specials vs. halftime entertainment — calendar planning.
- **So what:** **Spend and creative** follow P12 for messaging; **forecasting** still uses P1 + attendance MLR until post-launch refit.

**Speaker notes:**  
- P12: “Convenience sample — directional only until we have a weighted or larger wave.”  
- P1: “These bars are **literature + analyst priors**, not the survey.”

**Business plan:** **Marketing & sales strategy** / **Customer evidence**. Drop in P12 headline stats as **qualitative research**; keep P1 in **methodology** or **forecasting assumptions**.

**Presentation images:** **P12 as hero** when the CSV is live; **P1** as second figure or appendix. Optional small lifestyle inset only if it does not compete with P12’s four text panels.

---

## SLIDE 4 — Ticket sales strategy & recommendations

**Charts:** `P8_transit_shuttle.png`, `P13_pga_shuttle_precedent.png`  

**Optional on same slide or appendix:** `P10_summary_table.png` (Charlotte playbook → Crown actions) if it fits without crowding.

**Purpose:** Operational levers that turn context into revenue — **transit parity**, **proven local shuttle precedent**, pricing/promo discipline, and **opener as product launch**.

**Bullets:**

- **UNCC / transit:** Shuttle is framed as **revenue + access**, not a cost line — ridership and ancillary lift offset charter-style spend (see P8).
- **PGA / Quail Hollow precedent:** Charlotte already runs major-event shuttles; Crown is a **smaller, same-behavior** ask (P13).
- **Messaging:** Lead with **$0 parking** and **value ticket** where true — COA story is structural vs FC/Knights.
- **Opener (e.g. May 21):** Treat as a **product launch** — one named hero offer, clear CTA, PR and social peaking that week; FC-style opener lifts are the benchmark for “night one” intensity, not a normal home game.
- **Promo calendar:** Every home date gets a **named reason** to attend; stack heavier giveaways on conflict nights and rivalry nights (detail can live in speaker notes or a one-row appendix table in Canva).

**So what:** Strategy connects **access (shuttle)**, **proof (PGA)**, and **launch discipline (opener)** to the same drivers as Slide 3.

**Speaker note:** If time is short, show **P8 + P13** side-by-side and speak the opener / COA lines without extra graphics.

**Business plan:** **Operations**, **Partnerships (transit / city)**, **Go-to-market timeline**. Put shuttle pilot and CATS conversation in **partnerships**; put promo calendar and opener in **launch plan**.

**Presentation images:** Blue Line / station; PGA or major-event shuttle (see table); icon strip for parking/ticket/bus/promo.

---

## SLIDE 5 — Revenue impact & execution priorities

**Charts:** `P9b_revenue_table.png` (primary). **Optional:** `P9_revenue_waterfall.png` if you want the fill-rate story visually; avoid stacking both if the slide feels busy.

**Purpose:** Close with **magnitude** (Strategy A/B vs baseline) and **five decisions** that are already evidence-backed.

**Bullets:**

- Strategy B narrative: levers are **additive** — promos, bundles, shuttle, conflict-aware calendar (numbers on P9b).
- **Five decisions before / around launch:** lock named promo for all 17 homes; lead ads on COA; pilot shuttle; pursue CATS MOU path; survey first homestand to refresh the model.

**So what:** The model is a **sensitivity map**, not a crystal ball — execution items are the bridge to $1M+ season upside discussed in `models/revenue_model.py`.

**Speaker note:** P9b is table-dense — zoom crop in Canva or animate rows if presenting live.

**Business plan:** **Financial projections** (summary table = Strategy A/B vs baseline), **Use of funds** (tie “five decisions” to budget lines if you can), **Milestones** (90-day / through first homestand).

**Presentation images:** Subtle “growth” abstract or before/after arena fill (generic); final slide **logo + contact / QR**.

---

## Chart index (5-slide subset)


| Slide | PNG files                                              |
| ----- | ------------------------------------------------------ |
| 1     | P11_market_context.png                                 |
| 2     | P6_conflict_calendar.png, P7_conflict_impact_table.png |
| 3     | P12_survey_framework.png, P1_driver_weights.png      |
| 4     | P8_transit_shuttle.png, P13_pga_shuttle_precedent.png  |
| 5     | P9b_revenue_table.png                                  |


**Also generated by `--deck5` for optional use:** `P10_summary_table.png` (Slide 4 or backup).

---

## END OF SPEC

