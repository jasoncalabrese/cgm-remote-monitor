#!/usr/bin/env python3
"""
Classify fast CGM drops into: logged-insulin correction, unlogged Afrezza,
walk/exercise, G7 compression, or ambiguous — so meal/correction (ISF/CR)
analysis can exclude the confounders it can't otherwise see.

Signatures (validated on 30d of this user's data):
  - A fast drop (>=DROP_MIN in <=DROP_WIN min) is the trigger.
  - Rebound (BG rise in the ~2.5h after the nadir, no carbs) separates SUSTAINED
    drops (real insulin -> stays down) from TRANSIENT ones (recover).
  - Then:
      * logged insulin >=1U before the drop        -> Loop/manual correction
      * high start (>=150) + little rebound         -> UNLOGGED AFREZZA (correction of a high)
      * rebound + overnight (0-6h)                  -> G7 COMPRESSION low (artifact)
      * rebound + daytime (7-21h)                   -> WALK/exercise ("return-home" rise)
      * else                                        -> ambiguous

Limits: undercounts Afrezza stacked on a logged bolus (no clean no-insulin drop);
a walk from a high that doesn't rebound can look like Afrezza; imperfect at the edges.
Treat classes as best-effort labels, not ground truth.

    python3 event_classifier.py [lookback_days]   # default 30
"""
import sys, json, urllib.request, urllib.parse, statistics as st, datetime, bisect
from collections import defaultdict as dd, Counter

BASE = "https://nightscout.cbrese.com/api/v1"
TZ = -7 * 3600 * 1000
LOOKBACK = int(sys.argv[1]) if len(sys.argv) > 1 else 30
DROP_MIN, DROP_WIN = 40, 40          # mg/dL within minutes
REBOUND_HI, REBOUND_LO = 35, 25      # rebound thresholds
HIGH_START = 150
NIGHT = range(0, 7)                  # local hours counted as overnight (compression window)


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


def classify(ev):
    if ev["logged"] >= 1.0:
        return "logged-insulin correction"
    if ev["start"] >= HIGH_START and ev["rebound"] < REBOUND_LO and not ev["reb_carbs"]:
        return "unlogged Afrezza"
    if ev["rebound"] >= REBOUND_HI and not ev["reb_carbs"]:
        return "G7 compression" if ev["hr"] in NIGHT else "walk/exercise"
    return "ambiguous"


def main():
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000)
    since = now - LOOKBACK * 86400000
    e = fetch("entries.json", {"find[date][$gte]": since, "count": 60000})
    t = fetch("treatments.json",
              {"find[created_at][$gte]": ld(since + 7 * 3600000).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
               "count": 20000})
    bolus = sorted((ms_of(x), num(x, "insulin")) for x in t if num(x, "insulin") > 0 and ms_of(x))
    carbt = sorted(ms_of(x) for x in t if num(x, "carbs") >= 10 and ms_of(x))

    def ins_before(a, b): return sum(v for ms, v in bolus if a <= ms <= b)
    def carb_in(a, b):
        i = bisect.bisect_left(carbt, a); return i < len(carbt) and carbt[i] <= b

    bk = dd(list)
    for x in e:
        if x.get("type") == "sgv" and x.get("sgv"):
            bk[round(x["date"] / 300000)].append(x["sgv"])
    seq = sorted((b * 300000, sum(v) / len(v)) for b, v in bk.items())

    events, i = [], 0
    while i < len(seq) - 6:
        ms, v = seq[i]
        j = i
        while j < len(seq) - 1 and seq[j][0] - ms <= DROP_WIN * 60000:
            j += 1
        nadir = min(x[1] for x in seq[i:j + 1])
        nidx = next(k for k in range(i, j + 1) if seq[k][1] == nadir)
        nms = seq[nidx][0]
        if v - nadir >= DROP_MIN:
            reb_win = [x[1] for x in seq if nms + 15 * 60000 <= x[0] <= nms + 150 * 60000]
            ev = dict(ms=ms, start=v, nadir=nadir, drop=v - nadir, hr=lh(ms),
                      logged=ins_before(ms - 15 * 60000, nms),
                      rebound=(max(reb_win) - nadir) if reb_win else 0,
                      reb_carbs=carb_in(nms, nms + 150 * 60000))
            ev["class"] = classify(ev)
            events.append(ev)
            i = nidx + 3
            continue
        i += 1

    print(f"=== Fast-drop event classification: last {LOOKBACK}d "
          f"({ld(seq[0][0]):%b %d}->{ld(seq[-1][0]):%b %d}), {len(events)} drops ===\n")
    grp = dd(list)
    for ev in events:
        grp[ev["class"]].append(ev)
    print(f"{'class':28} {'n':>3} {'/day':>5} {'medStart':>8} {'medDrop':>7} {'medReb':>6}  peak hours")
    for k in ["unlogged Afrezza", "walk/exercise", "G7 compression",
              "logged-insulin correction", "ambiguous"]:
        a = grp.get(k, [])
        if not a:
            continue
        hrs = Counter(x["hr"] for x in a)
        top = " ".join(f"{h}h" for h, _ in sorted(hrs.items(), key=lambda z: -z[1])[:4])
        print(f"{k:28} {len(a):3d} {len(a)/LOOKBACK:5.1f} {st.median([x['start'] for x in a]):8.0f} "
              f"{st.median([x['drop'] for x in a]):7.0f} {st.median([x['rebound'] for x in a]):6.0f}  {top}")
    print("\nFor ISF/CR analysis, exclude windows around 'unlogged Afrezza' events; treat")
    print("'walk/exercise' as activity (not a settings issue) and 'G7 compression' as artifact.")


if __name__ == "__main__":
    main()
