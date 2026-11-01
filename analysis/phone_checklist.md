# Phone visit checklist

Everything that requires physical access to Andrew's phone, batched. Loop preset
definitions and alarm settings live only on the device — they cannot be changed or
even read through Nightscout, unlike the basal/CR/ISF profile, which this repo
verifies remotely after the fact.

Last updated 2026-11-01. STILL OUTSTANDING — none of this has been done since 2026-09-10.

Item 1 is now considerably better evidenced than when it was written. Over the last 35
days there were 21 distinct episodes below 54, and **57% of them follow a Rage
activation** (median 3.85U of manual insulin in the preceding 2.5h). The four deepest,
all nadir 40, are Rage episodes. Everything else in this engagement is now working —
overnight is at ~0.0% below 54, midday holds after the carb-ratio change, and game days
are handled by Running Extra Low. This button is the largest remaining cause of severe
lows, and it is unchanged at x1.20 / target 80, firing 3.9 times a day.

---

## 1. Change 🤬 Rage: multiplier ×1.20 → ×1.00 — PRIMARY

Leave the target at **80**. Do not change it on this visit.

Why: Rage fires 3.9×/day (243 activations in 63d) and delivers ~**6.5 U/day**, about
13% of total daily insulin, at a median trigger of BG 150. 43% of activations end
below 70 and 22% below 54. Dropping the multiplier removes ~25% of that — roughly
1.6 U/day — and eliminates the 20% basal boost that currently runs for 45 minutes on
top of each correction, which is the part that makes least sense when unlogged Afrezza
is already in flight.

Target deliberately untouched: it is the knob that changes suspension behaviour, and
suspension during an Afrezza drop is the thing we do not want more of.

Verifies itself — `insulinNeedsScaleFactor` appears on the next activation, so
`override_presets.py` will confirm within hours.

## 2. Read the alarm settings — DONE 2026-11-01, see below

Write these down even if nothing is changed:

ANSWERED: Rising Fast OFF, Falling Fast OFF, High 180, Low OFF, Urgent Low 55, Urgent Low Soon OFF.
Deliberately minimal because Pushover duplicates the alerting.

The live cue turned out to be on the SERVER, not the phone: Nightscout runs
alarmTypes=['predict'] with bgTargetTop 165, so the high alarm fires on an AR2 FORECAST
of 165 — 30-45 min early on a fast rise, landing while he is ~130-150 and climbing, which
is the worst correction window. Fix is BG_TARGET_TOP 165 -> 180 in the server config; no
phone needed. Do NOT disable 'predict' — it is also what provides the predictive LOW alarm.

Why it matters: he corrects at a median BG of 150, and 19 times below 120 — he is
reacting to an arrow, not a number. Correcting at 150–179 is fine (5% end <54);
correcting at 120–149 is his largest bucket and the worst (30% end <54); correcting on
a 45+ mg/dL/30min rise ends <54 **62%** of the time. If the rise alert is summoning him
into that window, turning it off is a one-toggle fix that needs no willpower.

## 3. Optional, if time — 🛴 Activity is mis-set for its job

Currently ×0.80 / target 110, used twice in 63 days. The game/band case wants something
stronger: ×0.70 / target 130. Note ⬇️⬇️ Running Extra Low (×0.70/120) already exists and
is close, so this is a convenience, not a necessity.

## 4. Optional — 💨 Afrezza preset

Shelved on adoption grounds (he is unlikely to change a 3.9×/day reflex), but it costs a
minute while the phone is in hand: **no multiplier, target 150, 30 min**. Rationale in
`proposed_basal.json` under `afrezza_preset_v2_2026_09_10`.

---

## NOT on this list — done elsewhere

- **⬇️⬇️ Running Extra Low onto the IFTTT widget**, replacing the dead Afrezza slot.
  That is on the caregiver's own account, needs no phone, and covers the 00:00–04:00
  rescues where ⬇️ Running Low (×0.80) has repeatedly proved too weak — Sat 09/05 hit 46
  with it running continuously from 19:30 to 01:00.
- **Profile changes** (basal / CR / ISF) — entered by the user, verified remotely here.
