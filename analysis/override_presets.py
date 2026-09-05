#!/usr/bin/env python3
"""Reconstruct Loop's override presets from Nightscout devicestatus.

WHY: this Loop (3.9.4.57) does not upload loopSettings.overridePresets — only the
CURRENTLY ACTIVE override, under devicestatus[].override:
    {"active":true,"name":"Running Low","multiplier":0.8,
     "currentCorrectionRange":{"minValue":120,"maxValue":120},"duration":5375}
So the preset table can only be recovered from presets that have actually been USED.
A preset never turned on, or turned on and cancelled within one 5-min upload cycle,
is invisible here — check the phone. (e.g. "Activity" was cancelled within seconds on
2026-08-29 and has no recoverable definition.)

Sample counts are 5-minute devicestatus uploads, i.e. roughly minutes/5 of active time,
so the table doubles as a usage profile: which levers actually get pulled.

RESULT 2026-09-05 (30d):
    Rage                    x1.20  target  80   ~77 h    <- the workhorse
    Running Low             x0.80  target 120   ~10 h    <- strongest reduction available
    Running a little Low    x0.90  target 100   ~7.5 h
    Eating Soon             (none) target  80   ~7.5 h
    Running a little High   x1.10  target 100   ~40 min
Note the asymmetry: the add-insulin preset is used ~8x more than the whole reduction
side, which is a legacy of when highs were the problem. As of Sep 2026 the problem is
afternoon/evening lows and there is nothing weaker than x0.80 to reach for.

Names print WITHOUT emoji here (Loop strips them in the override doc) but the treatment
log and the APNs remote-command path both need the emoji form, exactly.

    python3 override_presets.py [days]
"""
import sys, json, urllib.request, urllib.parse, datetime
from collections import defaultdict as dd

BASE = "https://nightscout.cbrese.com/api/v1"
DAYS = next((int(a) for a in sys.argv[1:] if a.isdigit()), 30)


def fetch(path, params):
    with urllib.request.urlopen(f"{BASE}/{path}?" + urllib.parse.urlencode(params), timeout=90) as r:
        return json.load(r)


def main():
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    docs = []
    for pg in range(12):                      # paginate; NS caps count per request
        d = fetch("devicestatus.json",
                  {"find[created_at][$gte]": since, "count": 10000, "skip": pg * 10000})
        if not d:
            break
        docs += d
        if len(d) < 10000:
            break

    seen = dd(lambda: dd(int))
    for d in docs:
        o = d.get("override")
        if not o or not o.get("active"):
            continue
        cr = o.get("currentCorrectionRange") or {}
        seen[o.get("name", "?")][(o.get("multiplier"), cr.get("minValue"), cr.get("maxValue"))] += 1

    print(f"{len(docs)} devicestatus docs / {DAYS}d  "
          f"(presets never used in this window cannot appear)\n")
    print(f"{'preset':30} {'scale':>6} {'target':>10} {'active':>9}")
    rows = [(n, name, m, lo, hi)
            for name, v in seen.items() for (m, lo, hi), n in v.items()]
    for n, name, m, lo, hi in sorted(rows, reverse=True):
        hrs = n * 5 / 60
        print(f"{name:30} {('x%.2f' % m) if m is not None else '-':>6} "
              f"{(f'{lo:.0f}-{hi:.0f}' if lo is not None else 'profile'):>10} "
              f"{(f'{hrs:.1f} h' if hrs >= 1 else f'{n*5:.0f} min'):>9}")


if __name__ == "__main__":
    main()
