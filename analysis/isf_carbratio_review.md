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

Impact: **basal work unaffected** (fasting baseline). **ISF 53 cannot be validated** — most
real corrections are Afrezza/fake-carb, invisible here (hold, don't change). **CR: the lunch
finding survives** (lunch window is relatively Afrezza-clean), **dinner is confounded** — do
not tune dinner CR from post-meal lows. Highest-value fix: **log Afrezza** (even approximately)
so Loop can account for it and future analysis is valid.

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

### Non-settings levers (higher yield for the shape problem)
- **Pre-bolus** 10–15 min before eating (currently 0%) — blunts the peak and lets the dose
  match carb absorption instead of front-loading.
- Don't fully bolus a meal when starting <90 and trending down (esp. lunch).

## Net
- ISF 53: **hold — cannot validate** (most corrections are unlogged Afrezza/fake-carb).
- CR 6: keep as base. **Test lunch CR 7** (lunch is Afrezza-clean). Do NOT tune dinner CR
  (dinner-time Afrezza confounds it).
- Highest-value action: **log Afrezza** — lets Loop stop double-dosing AND makes ISF/dinner-CR
  analysis possible.
- Consider pre-bolusing (0% currently).
- Basal (Step-1c) unchanged and working; overnight mild lows are partly G7 compression.
