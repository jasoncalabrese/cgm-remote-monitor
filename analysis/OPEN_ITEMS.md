# Open items

Everything currently outstanding, with owner and what it is waiting on. Becomes GitHub
issues once the private repo exists; this file goes away then.

Full reasoning for every item is in `proposed_basal.json` under the key named in each.

---

## Blocked on physical access to Andrew's phone

Historically the binding constraint — items have waited two months here. Next window is
**Thanksgiving break**.

### 1. Rage multiplier ×1.20 → ×1.00
`rage_reshape_2026_09_10` · proposed 2026-09-10 · still not applied

Target was moved 80 → 90–100 on 2026-11-01 and did what it was meant to: activations
3.7→2.6/day, median trigger BG 154→165, Rage-attributed share of severe lows 58%→36%.
The multiplier is the other half, worth ~21% of Rage's insulin on top of the 18% the
target bought. Leave the target alone.

**Verifies itself** — `insulinNeedsScaleFactor` appears on the next activation, within
hours given it fires ~2.6×/day.

### 2. Inhaled-insulin model in the Loop fork — `loop`
`afrezza_insulin_model.md` · the structural fix

A 4U cartridge is worth ~3.8U injected-equivalent and Loop cannot see any of it. Largest
open safety gap. Needs a build installed, so it shares the Thanksgiving window.

### 3. Sensor day-1 reduction override (habit, not a setting)
`sensor_day1_risk_window_2026_11_10`

First 24h of a sensor session: 4.0% below 54 against 1.1% for the rest — ~4× the rate,
and seven of nine episodes carry real insulin, so it is not warm-up noise. He pre-soaks,
so the swap is scheduled and predictable. One tap of ⬇️ Running Low for the first 8–12h.

---

## Ready for infra — no phone needed

### 4. `BG_TARGET_TOP` 165 → 180 — `infra`
`alerting_picture_2026_11_01`

`alarmTypes=['predict']` means the high alarm fires on an AR2 *forecast*, 30–45 min early
on a fast rise, landing while he is ~130–150 and climbing. Correcting at 120–149 ends
below 54 in 30% of cases; at 150–179, 5%. Do **not** disable `predict` — it also provides
the predictive low alarm the minimal Dexcom config depends on.

**Measure by:** the trigger-BG distribution shifting out of 120–149. Baseline over 63d —
under 120: 19, 120–149: 47, 150–179: 55, 180–219: 15.

### 5. Deploy `stack_watch.py` in observe mode — `infra`
`stack_watch.py`

67% of severe lows follow a repeat-dose pair. Fires once, 7 min after a qualifying manual
bolus. Tuned to 1.97 notifications/day. **Observe mode for ~2 weeks first** — Jason wants
a log before anything reaches the phone.

---

## Ready for Jason — profile edit, no special trip

### 6. Overnight carb ratio: `00:00` 6 → 8, new `08:00` segment at 6
`carbratio_midday_2026_09_07`, `carbratio_overnight_2026_11_10`

00:00–08:00 is 94% fake-carb traffic — four real meals against 60 fake entries in 63
days. That segment is effectively a fake-carb potency dial. 10g at CR 6 generates 1.67U;
at CR 8, 1.25U. On the night of 11/08 that is 7.5U versus 5.6U.

Does **not** address the doubling-up, and costs ~2U on the roughly fortnightly real
late-night meal.

---

## Project hygiene

### 7. Migrate off the public Nightscout fork — `analysis` + Jason
The fork is public and has been since July: 9.4 MB of raw CGM and treatment data, 80 KB
of clinical reasoning, AGP PDFs, and 68 commit messages with health detail. Moving stops
ongoing exposure; it does not undo past exposure.

Needs Jason to create the private repo and attach it to **all three** sessions.

### 8. Attach the analysis repo to the Loop and infra sessions
Without it they have no shared context and no issue channel, and they cannot message each
other.
