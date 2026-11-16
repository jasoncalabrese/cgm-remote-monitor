# Change log
Reconstructed from the 68 commits that touched `analysis/` in the public Nightscout
fork this work started in, 2026-07 to 2026-11, so the sequence survives the move to a
fresh history. Full reasoning for every entry is in `proposed_basal.json`.

## 2026-06-13
- Add 90-day Nightscout T1D data pull and pattern analysis
- Add basal/overnight-low analysis and profile history
- Add evidence-based overnight basal redesign
- Add phased daytime basal segments to redesign
- Add response checker for the Step-1 basal change
- Record night-1 result and add Step-1b basal correction

## 2026-06-20
- Record Step-1b week result and add Step-1c (dawn fix)
- Refine week-1b result: exclude sensor day-1 noise
- Make response checker sensor-aware (warmup + G6->G7 switch)
- Harden G6->G7 detection: trigger on any native device-string change

## 2026-07-04
- Fix G7 multi-uploader detection; record Step-1c G7-era result

## 2026-07-11
- Add ISF/carb-ratio review (30-day meal + correction analysis)
- Add fake-carb / unlogged-Afrezza confound analysis to ISF-CR review
- Retract prebolus finding; downgrade CR/ISF to hold (data-integrity limits)
- Correct Afrezza note: Loop doesn't model it, logging gives no benefit
- Add event classifier: separate Afrezza, walks, and G7 compression
- Add --label timeline mode + looser merged detection
- Add --csv export: fill-in labeling spreadsheet
- Update README and REPORT with the full tuning journey + next steps
- Remove Nightscout hostname from markdown docs

## 2026-07-18
- Add AGP-style 14-day glucose one-pager (HTML report)
- Add AGP 14-day report PDF (care-team deliverable)
- Add basal tuning history document (HTML + PDF)
- Add dark-theme PDF versions of the AGP and basal history reports

## 2026-07-25
- Add Step-1d: remove the vestigial late-morning basal bump
- Revise Step-1d down and add first-meal review (summer sleep-in context)
- Correct meal taxonomy to ordinal; add two-wave post-breakfast finding
- Correct breakfast analysis error; recommend holding settings
- Confirm 3-day pod-cycle effect - largest systematic driver found
- Add pod-cycle override automation (Nightscout-side, dry-run default)
- Fix pod override to use the real Loop command path
- Add droplet deployment notes and clean cron-log failure handling

## 2026-08-23
- Add care-team clinical summary (band activity / hypoglycemia)
- Correct care-team summary: early-start days, not day-of-week
- Propose Step-2 basal: close the delivered-vs-scheduled gap
- Refocus care-team doc on the overnight basal change
- Fix bolus attribution using Loop's automatic flag; add target finding
- Rebuild the doc as a personal working reference
- Simplify the plan doc to keep focus on the basal change
- Record overnight basal change as applied and verified

## 2026-09-05
- Record week review and propose afternoon-only basal trim
- Withdraw afternoon basal cut; add delivered-vs-scheduled tool
- Recover Loop override preset table from devicestatus

## 2026-09-07
- Record home-weekend read: problem is bolus timing, not basal
- Propose midday carb ratio 6 -> 6.5, the first time-segmented setting
- Revise midday carb ratio proposal from 6.5 to 7.0
- Record midday carb ratio 7.0 as applied and verified

## 2026-09-09
- Record first day on CR 7: low was correction stacking, not the ratio

## 2026-09-10
- Propose retargeting the Rage preset from 80 to 100
- Invert the Rage recommendation: Afrezza needs a stand-down, not a lean-in
- Withdraw the stand-down preset; propose removing the alert cue instead
- Propose the Afrezza preset: no multiplier, target 150, 30 minutes
- Arm only the first Afrezza override; hold the second until events are tagged
- Make the Afrezza button self-logging; drop the separate logging action
- Teach the classifier about logged Afrezza; correct the earlier zero-hits claim
- Read presets from override treatments; correct two wrong claims
- Identify the widget as the caregiver surface, not Andrew's
- Shelve the Afrezza preset; reshape Rage instead
- Add a phone-visit checklist

## 2026-09-13
- Record the Rose Bowl result and the CR 7 week review

## 2026-11-01
- Seven-week review: everything shipped worked, Rage is what is left
- Record the full alerting picture; the cue is server-side, not on the phone

## 2026-11-09
- First look at the Rage target change; verdict deferred on an aged sensor

## 2026-11-10
- Retract the sensor-age theory; find the day-1 risk window instead
- Propose splitting the overnight carb ratio to blunt the fake-carb dose
- Add stack_watch.py: nudge between the first dose and the repeat
- Design an inhaled-insulin model for the Loop fork

## 2026-11-16
- Split the work into three sessions and record the structure
