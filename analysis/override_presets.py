#!/usr/bin/env python3
"""Recover Loop's override presets, and how they are actually used, from Nightscout.

SOURCE: the override TREATMENTS, not devicestatus.
  Every activation writes eventType "Temporary Override" carrying reason (the preset
  name), insulinNeedsScaleFactor, correctionRange and the ACTUAL duration. A fractional
  duration (4.36m) is Loop reporting a run that ended early, so these records describe
  what Loop APPLIED, not what was commanded.

  An earlier version read devicestatus[].override instead. That only captures a preset
  if it happens to be ACTIVE during a 5-minute upload, so rarely-used presets vanish:
  it found 5 presets where this finds 9, and it led to two wrong statements on
  2026-09-08 — that no 0.70 preset existed (⬇️⬇️ Running Extra Low is x0.70/120) and
  that 🛴 Activity's definition was unrecoverable (x0.80/110).

  A preset never used in the window still cannot appear. Only the phone is definitive.

ALWAYS PAGINATE BY DATE. A bare count= query on treatments covers DAYS, not months -
Temp Basal and automatic Correction Bolus records dominate the collection - and a
corrupt far-future record (one dated 2161-03-09 exists here) breaks date-sorted
pagination. This module walks back a week at a time.

enteredBy separates where the tap happened:
  "Loop"                      -> set in the Loop app
  "Loop (via remote command)" -> set through Nightscout, i.e. the IFTTT widget
As of 2026-09-10 that split is 330 / 12, and 🤬 Rage is 243 / 0 - the widget is
essentially unused, which is where a new preset must NOT be put.

    python3 override_presets.py [days]
"""
import sys, json, urllib.request, urllib.parse, datetime, statistics as st
from collections import defaultdict as dd, Counter

BASE = "https://nightscout.cbrese.com/api/v1"
DAYS = next((int(a) for a in sys.argv[1:] if a.isdigit()), 63)


def fetch(path, params):
    with urllib.request.urlopen(f"{BASE}/{path}?" + urllib.parse.urlencode(params), timeout=120) as r:
        return json.load(r)


def load_overrides(days):
    out, wk = [], 0
    while wk * 7 < days:
        hi = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7 * wk)
        lo = max(hi - datetime.timedelta(days=7),
                 datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days))
        out += [x for x in fetch("treatments.json",
                                 {"find[created_at][$gte]": lo.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                                  "find[created_at][$lt]": hi.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                                  "count": 20000})
                if x.get("eventType") == "Temporary Override"]
        wk += 1
    return out


def main():
    ov = load_overrides(DAYS)
    if not ov:
        print("no override treatments found"); return
    D = dd(lambda: dd(int))
    for x in ov:
        cr = x.get("correctionRange")
        a, b = (cr[0], cr[1]) if isinstance(cr, list) and len(cr) == 2 else (None, None)
        D[x.get("reason", "?")][(x.get("insulinNeedsScaleFactor"), a, b)] += 1

    print(f"{len(ov)} override activations / {DAYS}d "
          f"(a preset never used in the window cannot appear)\n")
    print(f"{'preset':30} {'scale':>7} {'target':>9} {'uses':>6} {'medDur':>8} {'in-app':>7} {'widget':>7}")
    rows = [(n, name, s, a, b) for name, v in D.items() for (s, a, b), n in v.items()]
    for n, name, s, a, b in sorted(rows, reverse=True):
        sub = [x for x in ov if x.get("reason") == name]
        ds = [x["duration"] for x in sub if isinstance(x.get("duration"), (int, float))]
        src = Counter(x.get("enteredBy", "?") for x in sub)
        print(f"{name:30} {('x%.2f' % s) if s is not None else '(none)':>7} "
              f"{(f'{a:.0f}-{b:.0f}' if a is not None else 'profile'):>9} {n:6d} "
              f"{(st.median(ds) if ds else 0):7.0f}m {src['Loop']:7d} "
              f"{src['Loop (via remote command)']:7d}")

    tot = Counter(x.get("enteredBy", "?") for x in ov)
    app, rem = tot["Loop"], tot["Loop (via remote command)"]
    print(f"\nwhere the tap happens: Loop app {app}, widget {rem} "
          f"({100 * rem / max(app + rem, 1):.0f}% widget)")
    # a preset that rarely runs its full length is being cancelled or replaced early
    print("\nshare of activations that ran their FULL programmed length:")
    for name in sorted(D):
        ds = [x["duration"] for x in ov if x.get("reason") == name
              and isinstance(x.get("duration"), (int, float))]
        if not ds: continue
        full = sum(1 for d in ds if abs(d - round(d)) < 0.01)
        print(f"  {name:28} {full:3d}/{len(ds):3d}")


if __name__ == "__main__":
    main()
