# Design: an inhaled-insulin model for the Loop fork

**Status:** design, not implemented. Needs the Loop fork to name files.
**Date:** 2026-11-10. **Target window:** Thanksgiving break (phone + Loop update).

---

## The problem, stated precisely

Loop does not model inhaled insulin. Every Afrezza cartridge therefore enters the
system as **insulin Loop cannot see**, and Loop continues dosing against an IOB that
is wrong by the size of a meal bolus.

Measured from 63+ days of this user's own data (method below):

| | |
|---|---|
| Dose per cartridge | 4U inhaled (only size stocked) |
| **Injected-equivalent** | **3.8U** (median, n=18; p25 2.05, p75 3.96) |
| Potency ratio | ~0.94 U injected per U inhaled |
| Peak glucose-lowering | ~40 min post-dose |
| Action essentially complete | ~60–75 min post-dose |

On top of that invisible 3.8U, the user's son adds "fake carbs" — small carb entries
that exist precisely to make Loop deliver more than its correction logic would, i.e.
to route *around* the IOB check that would otherwise refuse. A 10g fake carb at CR 6
generates ~1.7U. The composite ritual is Rage + fake carbs + manual bolus in the same
minute, repeated 5–16 minutes later.

So at the moment of a typical event, actual insulin on board can exceed Loop's
estimate by **4–6 units**, and Loop's recommendation — and its prediction line, and
its willingness to keep dosing — are all computed from the wrong number.

**Four settings changes have been proposed against the downstream symptoms** (Rage
target, Rage multiplier, overnight carb ratio, alert threshold). Each shaves a slice
off a dose that Loop should never have recommended. None addresses the cause.

## Why this one can actually get adopted

Two prior proposals died on adoption: a 💨 Afrezza stand-down preset, and a
behavioural "wait 20 minutes" rule. Both asked him to give something up in exchange
for a benefit he would not feel until ninety minutes later.

This is different. Logging the dose makes **the prediction line show the drop
actually arriving** — which is the reassurance he is currently seeking by dosing
again at minute ten. The button gives him something he wants at the moment he wants
it. That is the only design in this engagement with that property.

## How the numbers were measured

`afrezza_curve` method, reproducible from Nightscout alone:

1. **Event detection.** Fast drop (≥45 mg/dL within 40 min) starting from BG ≥150,
   with <0.8U of logged insulin in the window and **no carb entry at all** from −45
   to +180 min. This yields 18 clean events in 91 days.
2. **Shape.** Align events at the start of the observable fall, take the median
   ΔBG trajectory from −30 to +240 min. Peak lowering rate at t=+25, most of the
   fall done by t=+45, nadir −76 mg/dL at t=+85, flat thereafter.
   The inhalation precedes t=0 by roughly 15 min (action onset plus CGM lag), so
   peak effect lands ~40 min post-dose. This matches published Afrezza PD.
3. **Potency — the part that matters.** A naive `ΔBG / ISF` gives 1.25U and is
   **wrong**, because Loop suspends basal throughout the fall and the withheld
   insulin offsets it. For each event, over t=0..+120:

       net_other = (basal delivered + other boluses) − basal scheduled
       afrezza_equivalent = (−ΔBG / ISF) − net_other

   The median basal deficit is ~2.5U, so the corrected figure is **3.8U**, three
   times the naive estimate.

### Known limits of the estimate
- Events are selected on drops ≥45 mg/dL, biasing toward larger responses.
- Counter-regulation at low BG blunts the fall, so this likely **under**-states potency.
- The basal-deficit correction assumes scheduled basal was itself correct.
- Two of 18 events come out near zero and are probably misdetections, not Afrezza.
- Wide spread (p25 2.05 → p75 3.96) — treat 3.8U as a central estimate, not a constant.

## Proposed change

### 1. An inhaled insulin model
Loop's `ExponentialInsulinModel` is parameterised by action duration and peak
activity time; Fiasp and Lyumjev already ship as 360 min / 55 min variants. Add:

```
Afrezza (inhaled):  peakActivityTime ≈ 40 min,  actionDuration ≈ 150 min
```

150 rather than 75 deliberately: the tail is cheap (activity is near zero by then)
and a model that ends too early makes Loop over-deliver at exactly the wrong moment.

### 2. A dose-logging path that uses it
One control — "Afrezza 4U" — creating a dose that carries the inhaled model rather
than the pump's insulin type, and is **not** sent to the pump. If the fork already
has external/manual dose entry, this is a new insulin type on an existing path.

### 3. Conservative potency, staged
Log **3.0U**, not 3.8U, for the first cycle.

The error is asymmetric. Under-counting leaves some of today's problem in place.
Over-counting makes Loop withhold insulin it should have given, which is the
rebound-high failure the user has flagged before and would poison adoption on the
first bad night. Start low, verify, raise.

| stage | logged as | move when |
|---|---|---|
| 1 | 3.0U | two weeks, no new rebound highs after Afrezza events |
| 2 | 3.8U | re-fit the curve on *logged* events rather than inferred ones |

### 4. What must NOT change
- **No change to dosing math.** New insulin model and a logging path; nothing else.
- **Do not gate carb entry.** The fake-carb route is the one that matters, and
  correct IOB is what makes Loop's own refusal meaningful again — a UI gate would
  just be routed around as before.
- **The dose must never reach the pump.**

## Why correct IOB fixes the downstream behaviour

With the Afrezza counted:
- Loop stops recommending corrections on top of invisible insulin.
- The fake-carb trick stops working as a bypass, because the IOB it was invented to
  evade is now real — Loop's refusal becomes correct rather than merely cautious.
- The prediction line shows the fall coming, which answers the anxiety that drives
  the repeat dose.

None of that requires him to change a habit. It requires one button that makes the
app tell him the truth.

## Validation plan

Baselines to beat, all measured over the 63 days to 2026-11-09:

| metric | now |
|---|---|
| severe-low episodes (<54) | 0.78/day |
| share preceded by a repeat-dose pair | 67% |
| manual boluses ≥0.5U | 10.8/day |
| repeats within 20 min | 38% of boluses, 6.4 U/day |
| fake carbs | 3133g over 63d |

After the change, re-run the detector: Afrezza events that are now **logged** give a
clean population for re-fitting the curve, which stage 2 depends on. If logging rate
is low, the feature failed on adoption and should be reconsidered rather than tuned.

## Open questions — need the fork

1. Does the fork (or its upstream) already support external/manual dose entry?
2. Is `InsulinType` extensible without touching pump code paths?
3. Where does the bolus screen read IOB, so the logged dose shows immediately?
4. Does anything persist insulin type into Nightscout uploads? If so the analysis
   scripts here can verify from the server, as every other change has been.
