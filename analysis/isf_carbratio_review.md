# ISF & Carb-Ratio Review — 2026-07-04

Reviewed 30 days of meals/corrections (last week highlighted). Current profile is flat
all day: **ISF 53, CR 6, target 100, DIA 6**.

> Observational, not medical advice. Closed-loop (Loop) confounds classic ISF/CR tests
> because the algorithm continuously corrects — treat these as directional.

## ⚠️ Data-integrity caveats (important)
This user's data contains two invisible-insulin sources that confound ISF/CR analysis:
- **Fake carbs**: small carb entries used to trick Loop into correcting. 1–15g entries: 161
  in 30d, median BG-at-entry **152**, **51% at BG>150** → ~2.8/day are corrections, not food.
  (The CR analysis below uses the **≥30g** set, which is 93% real meals — so it's clean.)
- **Unlogged Afrezza** (inhaled ultra-fast): detected ~**0.9/day** as fast ≥40 mg/dL drops
  from BG>150 with <1U logged (a floor — doses on top of logged insulin are invisible).
  **Clusters at dinner/evening (16h:6, 18h:3), not lunch.**
- **Prebolus timing is invisible**: carbs and insulin are logged at the **same timestamp**
  (Loop convention — dosing insulin without announced carbs makes Loop 0-temp/suspend, so
  they're entered together; also easier). The timestamp = when they *dosed*, NOT when they
  *ate*. So bolus-vs-carb "offset" is always ~0 by construction and says nothing about
  prebolusing. **Retracts the earlier "0% pre-bolus / front-loading" reading** — the early
  post-bolus dip is consistent with a normal prebolus acting before food.

Impact: **basal work unaffected** (fasting baseline). **ISF 53 cannot be validated** — most
real corrections are Afrezza/fake-carb, invisible here (hold, don't change). **CR: the lunch
finding survives** (lunch window is relatively Afrezza-clean), **dinner is confounded** — do
not tune dinner CR from post-meal lows.

**Note: Loop does NOT model Afrezza.** Inhaled Afrezza has no IOB curve Loop understands, so
Loop never counts it as insulin-on-board — logged or not; it only reacts to the resulting BG
trend (and lags it, since Afrezza is ultra-fast). So logging Afrezza gives **no dosing benefit**
— it would only aid retrospective analysis, at a manual cost, so it's not worth asking for.
The practical fix is to **detect Afrezza from the BG trend** (fast drops from highs) in tooling
and exclude those windows from ISF/CR analysis — no logging required. See `event_classifier.py`.

- **Walks/exercise** also cause fast drops (another confounder). They're separable: a walk
  **rebounds** (the "return-home" rise) and lands in **daytime**, whereas Afrezza stays down,
  and G7 **compression** lows also rebound but cluster **overnight**. So: rebound = transient
  (walk or compression) vs sustained (Afrezza); time-of-day then splits walk from compression.
  Encoded in `event_classifier.py` (unlogged-Afrezza ~0.1/day, walk ~0.2/day, compression
  ~0.3/day, Loop corrections ~3.2/day). Best-effort labels — undercounts Afrezza stacked on a
  logged bolus, and a no-rebound walk-from-a-high can masquerade as Afrezza.

## Last week (Jun 28–Jul 4, first clean week on G7)
Mean **107** · GMI **5.9%** · TIR **93%** · CV 26% · <54 **0.8%** · >180 **0.6%**.
Excellent control; remaining issue is scattered *mild* lows (~7% <70), not highs.

## ISF 53 — keep
Isolated corrections (BG>150, no carbs ±2h, n=32): median 162 → +3h 130.
- Landed 80–150: **75%** · overshoot <80: **6%** · still >150: 19%.
- Verdict: correctly set, if anything marginally weak. **No change.**

## Carb ratio 6 — total ~right, shape is the problem

| Meal | n | pre-BG | peak | net@4h | post <70 | post <60 | insU/4h |
|---|---|---|---|---|---|---|---|
| Lunch | 36 | 90 | 141 | +26 | 31% | 17% | 14.6 |
| Dinner | 42 | 111 | 140 | +10 | 29% | 10% | 14.9 |
| Breakfast | 3 | 87 | 164 | +66 | 33% | — | 12.9 |

- Meals **end slightly high** (net +) → total dose not excessive.
- Yet **~30% dip <70** after, and the 45-min post-bolus change is **negative** (dinner −20).
- **0% of meals are pre-bolused** (dose is given *at* the meal).
- Interpretation: CR-6 + fast insulin **front-loads** → early dip (sometimes a low), then
  carbs catch up to a modest peak. A **shape/timing** issue, not magnitude → a blanket CR
  change just trades early-lows for late-highs.

### Recommended experiment: lunch-only CR 6 → 7 (11:00–15:00)
Lunch is the clear outlier — starts low (pre-BG 90, the long-standing midday-low window)
and **17% of lunches go <60**. Weakening just the lunch ratio cuts post-lunch lows; cost is
a slightly higher lunch peak (currently only ~141) that Loop corrects. Dinner/rest stay at 6.
Breakfast (n=3) too sparse to tune.

### Non-settings levers
- Prebolus timing is invisible in the data (carbs+insulin logged together), so it can't be
  assessed here — do not infer front-loading from timestamps.
- Don't fully bolus a meal when starting <90 and trending down (esp. lunch).

## Net (revised for data-integrity limits)
Between unlogged Afrezza (dinner), fake carbs, and invisible prebolus timing, **meal-level
CR/ISF cannot be tuned from CGM+treatments with confidence.** So:
- ISF 53: **hold — cannot validate.**
- CR 6: **hold.** Lunch is the least-confounded window and the only place a low-confidence
  case exists (starts ~90, 17% go <60) — treat lunch CR 7 as an *optional* experiment, not
  a data-backed recommendation. Do NOT touch dinner CR (Afrezza-confounded).
- **Path to a real ISF/dinner-CR read: detect Afrezza from the BG trend in tooling** and
  exclude those windows (Loop can't use logged Afrezza, so no point asking the user to log it).
  Even then the detector undercounts (Afrezza stacked on logged insulin is invisible), so
  meal-side tuning stays low-confidence.
- Basal (Step-1c) unchanged and working; overnight mild lows are partly G7 compression.
