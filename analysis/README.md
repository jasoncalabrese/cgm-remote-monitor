# Nightscout T1D Analysis & Loop Tuning

Data analysis and **iterative closed-loop (Loop) tuning** for a Type 1 diabetic ("Andrew")
using data from a personal Nightscout server (v14.2.6, public-read — no token).
What began as a one-time 90-day pattern review has become an ongoing loop: analyze → propose a
settings change → apply it in Loop → verify → review a week later → adjust.

> **Not medical advice.** Everything here is observational. Settings changes are entered by the
> user in the Loop app and are a care-team decision. This repo only analyzes and proposes.

## Status (2026-07-11)
- **Control is excellent:** last clean week (G7) GMI **5.9%**, TIR **93%**, severe lows (<54) **0.8%**.
- **Basal:** tuned over three steps (Step 1 → 1b → 1c). Currently **Step-1c**, working well.
- **Sensor:** switched **G6 → G7 on Jun 26** (tooling auto-detects & excludes warmup).
- **ISF/CR:** left at ISF 53 / CR 6 — **held** (can't be tuned confidently; see caveats below).
- **Active work:** hand-labeling events (`event_labels.csv`) to calibrate the event classifier.

## Toolkit

| File | What it does |
|---|---|
| `REPORT.md` | The 90-day baseline analysis + an **update log** of the whole tuning journey. |
| `analyze.py` | Reproducible baseline metrics (TIR, overnight/dawn, post-meal, hypo windows) from `data/raw/`. |
| `check_response.py` | **Sensor-aware** weekly review: pulls fresh CGM, auto-excludes sensor warmup / G6→G7 switch, compares target windows to baseline (RAW vs CLEAN). Run: `python3 check_response.py [days]`. |
| `event_classifier.py` | Classifies fast CGM drops into unlogged-Afrezza / walk / G7-compression / logged-correction. `--label` prints a per-day timeline; `--csv` writes a fill-in labeling sheet. |
| `event_labels.csv` | Ground-truth labeling worksheet (fill `ACTUAL_LABEL` + notes, then upload back to tune the classifier). |
| `proposed_basal.json` | The full basal history: current + every proposed step (1, 1b, 1c, step-2) with results. |
| `isf_carbratio_review.md` | ISF & carb-ratio evaluation + the data-integrity caveats that limit it. |
| `data/raw/*.json.gz` | Raw API responses (gzipped): entries, treatments, devicestatus, profile. |

## Workflow (how a tuning round goes)
1. **Review** — `python3 check_response.py 8` (auto-handles sensor warmup). Read the CLEAN column.
2. **Propose** — record the change in `proposed_basal.json` with its rationale.
3. **Apply** — user enters it in the **Loop app** (Therapy Settings). *Loop's settings live on the
   phone; Nightscout only receives Loop's uploads — you cannot write settings to Loop.*
4. **Verify** — pull the profile and confirm Loop uploaded the exact values ("verify").
5. **Wait ~1 week**, change one variable at a time, then go back to step 1.

## Data-integrity caveats (essential for interpreting anything here)
These are why **basal tuning succeeded but ISF/CR can't be cleanly tuned** — basal is a fasting
baseline immune to meal/correction noise; meals and corrections are buried in invisible insulin.

- **Dual CGM sources** (`share2` bridge + native `Dexcom`): de-duplicated to 5-min mean buckets.
- **Sensor warmup**: Dexcom day-1 reads jumpy-low; auto-excluded (24h normal, 48h for a G6→G7 switch).
- **G7 compression lows**: overnight false lows from lying on the sensor — behavioral, not a settings issue.
- **Fake carbs**: small carb entries (~2.8/day) used to trick Loop into correcting a high — not food.
- **Unlogged Afrezza** (~0.9+/day, dinner-clustered): inhaled ultra-fast insulin. **Loop does NOT
  model it** (no IOB, logged or not — it only reacts to the BG trend), so logging it has no dosing
  benefit; it's inferred from BG fast-drops instead.
- **Walks/exercise**: also cause fast drops; separable by the post-walk **rebound** + daytime timing.
- **Prebolus is invisible**: carbs and insulin are logged at the same timestamp (a Loop convention
  to avoid 0-temping), so timestamps are dose-time, not eat-time.

## Next steps
1. **Label events** — fill `event_labels.csv` (with recollection of walks/Afrezza), upload it back.
2. **Score & tune** the classifier against those labels (rebound cutoff, the "rebound despite logged
   insulin → walk" rule that currently hides activity).
3. **Then** re-attempt the meal-side read (esp. lunch CR) with Afrezza/walk windows excluded.
4. **Hold** ISF 53 / CR 6 / basal Step-1c meanwhile — the system is in a good place.
5. Keep watching G7 (compression lows are behavioral; not a basal target).

## Conventions & reproduce
- **Timezone** `ETC/GMT+7` → local = **UTC−7** (Arizona/MST, no DST). Entries stored in UTC; scripts shift −7h.
- **Public read**: `status.json` reports `authDefaultRoles: "readable"`, so no token is needed.
- Baseline metrics: `python3 analyze.py` (reads `*.json` or `*.json.gz`).
- Original 90-day pull commands are in `REPORT.md`.
