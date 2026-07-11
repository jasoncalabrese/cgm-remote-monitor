#!/usr/bin/env python3
"""
Classify CGM drops into: logged-insulin correction, unlogged Afrezza, walk/exercise,
G7 compression, or ambiguous — so meal/correction (ISF/CR) analysis can exclude
confounders it can't otherwise see.

Two modes:
  (default)  summary  — tight threshold (>=40 in <=40min), one row per class, for stats.
  --label    timeline — looser, MERGED detection (>=25, up to 60min, sustained declines
             joined into one activity period) + carbs + overrides, laid out per day with a
             blank slot to confirm against memory. Use this to hand-label ground truth.

Signatures (validated on this user's data):
  - Rebound (BG rise after the nadir, no carbs) = TRANSIENT drop (walk or compression);
    no rebound + real insulin action = SUSTAINED (Afrezza / Loop correction).
  - Time-of-day splits transient drops: daytime rebound = WALK ("return-home" rise),
    overnight rebound = G7 COMPRESSION.
  - A drop that rebounds *despite* logged insulin is flagged as possible activity — the
    logged-insulin blind spot that hides walks/Afrezza stacked on a bolus.

    python3 event_classifier.py [days]            # summary (default 30)
    python3 event_classifier.py [days] --label    # per-day timeline for hand-labeling (default 3)
"""
import sys, json, urllib.request, urllib.parse, statistics as st, datetime, bisect
from collections import defaultdict as dd, Counter

BASE = "https://nightscout.cbrese.com/api/v1"
TZ = -7 * 3600 * 1000
HIGH_START = 150
REBOUND_HI, REBOUND_LO = 35, 25
NIGHT = range(0, 7)
LABEL = "--label" in sys.argv
DAYS = next((int(a) for a in sys.argv[1:] if a.isdigit()), 3 if LABEL else 30)
# detection sensitivity differs by mode
DROP_MIN, WIN_MIN, MERGE_GAP_MIN = (25, 60, 35) if LABEL else (40, 40, 0)


def fetch(path, params):
    with urllib.request.urlopen(f"{BASE}/{path}?" + urllib.parse.urlencode(params), timeout=90) as r:
        return json.load(r)


def lh(ms): return int(((ms + TZ) // 3600000) % 24)
def ld(ms): return datetime.datetime.utcfromtimestamp((ms + TZ) / 1000)
def ms_of(x):
    if x.get("mills"): return x["mills"]
    try: return int(datetime.datetime.fromisoformat(x["created_at"].replace("Z", "+00:00")).timestamp() * 1000)
    except Exception: return None
def num(x, k):
    v = x.get(k); return v if isinstance(v, (int, float)) else 0


def find_drops(seq, drop_min, win_min, merge_gap_min):
    """Detect drops >=drop_min within win_min; merge sustained declines within merge_gap_min."""
    ev = []
    i = 0
    while i < len(seq):
        ms, v = seq[i]
        nadir, nidx = v, i
        for j in range(i, len(seq)):
            if seq[j][0] - ms > win_min * 60000:
                break
            if seq[j][1] < nadir:
                nadir, nidx = seq[j][1], j
        if v - nadir >= drop_min:
            ev.append([ms, v, seq[nidx][0], nadir])   # start_ms, start_bg, nadir_ms, nadir
            i = max(nidx, i + 1)
        else:
            i += 1
    if not merge_gap_min:
        return ev
    merged = []
    for e in ev:
        if merged and e[0] <= merged[-1][2] + merge_gap_min * 60000:
            if e[3] < merged[-1][3]:
                merged[-1][2], merged[-1][3] = e[2], e[3]
        else:
            merged.append(e)
    return merged


def classify(start, nadir, rebound, logged, reb_carbs, hr):
    if reb_carbs and rebound >= REBOUND_HI:
        rebound = 0  # rebound is meal-driven, ignore for transient/sustained call
    if logged >= 1.0:
        if rebound >= REBOUND_HI and hr not in NIGHT:
            return "correction (+rebound: walk?)"
        return "logged-insulin correction"
    if start >= HIGH_START and rebound < REBOUND_LO:
        return "unlogged Afrezza"
    if rebound >= REBOUND_HI:
        return "G7 compression" if hr in NIGHT else "walk/exercise"
    return "ambiguous"


def build():
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    since = now - DAYS * 86400000
    e = fetch("entries.json", {"find[date][$gte]": since, "count": 60000})
    t = fetch("treatments.json",
              {"find[created_at][$gte]": ld(since + 7 * 3600000).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
               "count": 20000})
    bolus = sorted((ms_of(x), num(x, "insulin")) for x in t if num(x, "insulin") > 0 and ms_of(x))
    carbs = sorted((ms_of(x), num(x, "carbs")) for x in t if num(x, "carbs") > 0 and ms_of(x))
    carbt = [c[0] for c in carbs]
    bk = dd(list)
    for x in e:
        if x.get("type") == "sgv" and x.get("sgv"):
            bk[round(x["date"] / 300000)].append(x["sgv"])
    seq = sorted((b * 300000, sum(v) / len(v)) for b, v in bk.items())
    ts = [s[0] for s in seq]

    def ins_before(a, b): return sum(v for ms, v in bolus if a <= ms <= b)
    def carb_in(a, b):
        i = bisect.bisect_left(carbt, a); return i < len(carbt) and carbt[i] <= b
    def gi(ms):
        i = bisect.bisect_left(ts, ms); return seq[i][1] if 0 <= i < len(seq) else None

    events = []
    for ms, start, nms, nadir in find_drops(seq, DROP_MIN, WIN_MIN, MERGE_GAP_MIN):
        reb_win = [v for m, v in seq if nms + 15 * 60000 <= m <= nms + 150 * 60000]
        rebound = (max(reb_win) - nadir) if reb_win else 0
        logged = ins_before(ms - 15 * 60000, nms)
        rc = carb_in(nms, nms + 150 * 60000)
        events.append(dict(ms=ms, nms=nms, start=start, nadir=nadir, drop=start - nadir,
                           rebound=rebound, logged=logged, reb_carbs=rc, hr=lh(ms),
                           cls=classify(start, nadir, rebound, logged, rc, lh(ms))))
    return seq, events, carbs, bolus, gi


def summary(events):
    print(f"=== Fast-drop classification: last {DAYS}d, {len(events)} drops ===\n")
    grp = dd(list)
    for ev in events:
        grp[ev["cls"]].append(ev)
    print(f"{'class':30} {'n':>3} {'/day':>5} {'medStart':>8} {'medDrop':>7} {'medReb':>6}  peak hrs")
    for k, a in sorted(grp.items(), key=lambda kv: -len(kv[1])):
        hrs = Counter(x["hr"] for x in a)
        top = " ".join(f"{h}h" for h, _ in sorted(hrs.items(), key=lambda z: -z[1])[:4])
        print(f"{k:30} {len(a):3d} {len(a)/DAYS:5.1f} {st.median([x['start'] for x in a]):8.0f} "
              f"{st.median([x['drop'] for x in a]):7.0f} {st.median([x['rebound'] for x in a]):6.0f}  {top}")


def label(events, carbs, gi):
    # chronological per-day timeline: drops + carbs + fake-carb flags
    rows = []
    for ev in events:
        after = f"rebound +{ev['rebound']:.0f}" if ev["rebound"] >= 20 else "stayed down"
        ins = f"{ev['logged']:.1f}U" if ev["logged"] > 0.1 else "no ins"
        rows.append((ev["nms"], "DROP",
                     f"BG {ev['start']:.0f}->{ev['nadir']:.0f}, {after} | {ins} | guess: {ev['cls']}"))
    for ms, c in carbs:
        bg = gi(ms)
        tag = "FAKE?(correction)" if c <= 15 and bg and bg > 150 else "meal/snack?"
        rows.append((ms, "CARB", f"{c:.0f}g (BG~{bg:.0f}) -> {tag}"))
    rows.sort()
    print(f"=== LABEL timeline: last {DAYS}d — confirm each vs memory "
          f"(walk / Afrezza / compression / correction / real / fake / nothing) ===")
    curday = None
    for ms, kind, txt in rows:
        d = ld(ms).date()
        if d != curday:
            print(f"\n{d:%A %m/%d}")
            curday = d
        mark = "  ↓" if kind == "DROP" else "  •"
        print(f"{mark} {ld(ms):%H:%M}  {txt}\n        you: __________")


def main():
    seq, events, carbs, bolus, gi = build()
    (label(events, carbs, gi) if LABEL else summary(events))


if __name__ == "__main__":
    main()
