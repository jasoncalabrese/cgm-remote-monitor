# Project: Andrew T1D

Three sessions, one shared record. Tag `andrew-t1d`, plus a role tag each.

| session | tag | repos | owns |
|---|---|---|---|
| **Analysis** | `andrew-t1d:analysis` | `cgm-remote-monitor` | this `analysis/` directory, and every number in it |
| **Loop/NS code** | `andrew-t1d:loop` | `LoopWorkspace`, `Loop`, `LoopKit` | app and server code changes |
| **Infrastructure** | `andrew-t1d:infra` | `cbrese-infra` | droplet, Nightscout config, cron jobs |

Find each other with `ListAgents`; talk with `SendMessage`.

## The one rule

**Only the analysis session writes to `analysis/`.** Everything the project has learned
is here — every settings change with its rationale and result, and every finding that
was later retracted and why. Three sessions editing it concurrently would corrupt the
one thing that makes the work cumulative. The others read it and message analysis if
something is wrong.

Everything else is owned by whoever's directory it lives in.

## Why the split

The work has three genuinely different cadences. Analysis runs weekly against live
data and needs continuity of judgement — which confounders have already fooled us, which
findings were retracted. Infrastructure changes are rare, irreversible-ish, and touch a
live system. Loop code changes are gated on physical access to Andrew's phone, which has
been the binding constraint for months.

Mixing them in one session meant context about G7 compression artifacts competing with
Swift build errors for the same window.

## Shared facts any session needs

- Andrew, 19, at college. Omnipod Dash, Dexcom G7 **15-day** sensors (pre-soaked),
  Loop 3.9.4.57, `dosingStrategy: automaticBolus`. Nightscout 15.0.9 on a DigitalOcean
  droplet, `ETC/GMT+7` (UTC−7, no DST).
- Current therapy settings: basal 35.35 U/day over 10 segments; CR 6 / 7 from 10:00 /
  6 from 16:00; ISF 53; target 100.
- **Loop commands go through `POST /api/v2/notifications/loop`.** Posting a treatment to
  `/api/v1/treatments.json` writes a record Loop never reads while appearing to succeed.
- Afrezza is **not** modelled by Loop. A 4U cartridge is worth ~3.8U injected-equivalent
  (measured). This is the largest open safety gap and the subject of
  `afrezza_insulin_model.md`.
- There is no clinician in the loop. Jason makes the calls.

## Working constraints learned the hard way

- **Never write to the live Nightscout profile.** Settings are entered by hand on the
  phone; this project verifies afterwards by reading `profile.json` back.
- **Phone access is the scarce resource**, not analysis. See `phone_checklist.md`.
- A bare `count=` query on `treatments.json` covers *days*, not months — temp basals and
  automatic boluses dominate. Always paginate by date. This produced one wrong conclusion.
- Changes get judged on recorded baselines, not impressions. Eight-day windows have
  twice looked like regressions that were ordinary variation.
