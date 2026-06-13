#!/usr/bin/env python3
"""
Nightscout T1D data analysis (90-day pull from https://nightscout.cbrese.com).
Reads raw JSON from data/raw/ and prints a structured analysis.
Timezone: profile is ETC/GMT+7 => local = UTC-7 (Arizona/MST, no DST).
Entries are stored in UTC; we shift by -7h for time-of-day analysis.

Usage: python3 analyze.py
"""
import json, statistics as st, bisect, datetime, gzip, os
from collections import Counter, defaultdict as dd


def jload(name):
    """Load data/raw/<name>.json, transparently using .json.gz if present."""
    base = f"{RAW}/{name}.json"
    if os.path.exists(base):
        return json.load(open(base))
    return json.load(gzip.open(base + ".gz", "rt"))

TZ = -7 * 3600 * 1000  # local = UTC-7
DAYS = 90
RAW = "data/raw"


def num(x, k):
    v = x.get(k)
    return v if isinstance(v, (int, float)) else 0


def ms_of(x):
    if x.get("mills"):
        return x["mills"]
    try:
        return int(datetime.datetime.fromisoformat(x["created_at"].replace("Z", "+00:00")).timestamp() * 1000)
    except Exception:
        return None


def lhour(ms):
    return int(((ms + TZ) // 3600000) % 24)


def load():
    return jload("entries"), jload("treatments")


def dedup_5min(e):
    """Collapse overlapping devices (share2 + native Dexcom) into 5-min mean buckets."""
    bk = dd(list)
    for x in e:
        if x.get("type") == "sgv" and x.get("sgv") and x["sgv"] > 0:
            bk[round(x["date"] / 300000)].append(x["sgv"])
    return sorted((b * 300000, sum(v) / len(v)) for b, v in bk.items())


def main():
    e, t = load()
    seq = dedup_5min(e)
    vals = [v for _, v in seq]
    N = len(vals)
    span = (seq[-1][0] - seq[0][0]) / 86400000

    mean = st.mean(vals); sd = st.pstdev(vals); cv = 100 * sd / mean
    gmi = 3.31 + 0.02392 * mean
    print("=" * 60)
    print("NIGHTSCOUT 90-DAY ANALYSIS")
    print("=" * 60)
    print(f"Span {span:.0f}d | {N} 5-min readings | capture {100*N/(span*288):.0f}%")
    print(f"Mean {mean:.0f} mg/dL | GMI(est A1c) {gmi:.1f}% | SD {sd:.0f} | CV {cv:.0f}%")

    def p(lo, hi): return 100 * sum(1 for v in vals if lo <= v < hi) / N
    print("\nTIME IN RANGE (AGP):")
    print(f"  <54     {100*sum(1 for v in vals if v<54)/N:5.1f}%  (goal <1)")
    print(f"  54-69   {p(54,70):5.1f}%")
    print(f"  70-180  {p(70,181):5.1f}%  (goal >70)")
    print(f"  181-250 {p(181,251):5.1f}%")
    print(f"  >250    {100*sum(1 for v in vals if v>250)/N:5.1f}%")

    # Hourly percentiles
    hr = dd(list)
    for ms, v in seq:
        hr[lhour(ms)].append(v)
    print("\nHOURLY (local UTC-7): hr mean p10 p50 p90 %<70 %>180")
    for h in range(24):
        a = sorted(hr[h])
        q = lambda f: a[int(f * (len(a) - 1))]
        print(f"  {h:02d}  {st.mean(a):4.0f}  {q(.1):3.0f} {q(.5):3.0f} {q(.9):3.0f}  "
              f"{100*sum(1 for v in a if v<70)/len(a):4.1f} {100*sum(1 for v in a if v>180)/len(a):4.1f}")

    # Hypo episodes
    def episodes(th):
        eps = []; inep = False; start = None; nadir = 999; last = None
        for ms, v in seq:
            if v < th:
                if not inep: inep = True; start = ms; nadir = v
                nadir = min(nadir, v); last = ms
            elif inep and ms - last > 900000:
                eps.append((start, nadir)); inep = False
        if inep: eps.append((start, nadir))
        return eps
    print("\nHYPO EPISODES:")
    for th in (70, 54):
        eps = episodes(th)
        byhr = Counter(lhour(s) for s, _ in eps)
        print(f"  <{th}: {len(eps)} ep (~{len(eps)/DAYS*7:.1f}/wk) nadir {st.median([n for _,n in eps]):.0f} | "
              + ", ".join(f"{h:02d}h({n})" for h, n in sorted(byhr.items(), key=lambda x: -x[1])[:6]))

    # Treatments
    carbs = [x for x in t if num(x, "carbs") > 0]
    tc = sum(num(x, "carbs") for x in t); ti = sum(num(x, "insulin") for x in t)
    rescue = [x for x in carbs if num(x, "carbs") <= 20 and num(x, "insulin") == 0]
    print(f"\nTREATMENTS: carbs ~{tc/DAYS:.0f} g/d | bolus ~{ti/DAYS:.1f} U/d | "
          f"rescue carbs {len(rescue)} (~{len(rescue)/DAYS:.1f}/d)")

    # Post-meal
    sgv = sorted((x["date"], x["sgv"]) for x in e if x.get("type") == "sgv" and x.get("sgv"))
    times = [s[0] for s in sgv]
    def glu_at(ms):
        i = bisect.bisect_left(times, ms); best = None; bd = 1e18
        for j in (i - 1, i):
            if 0 <= j < len(sgv):
                d = abs(sgv[j][0] - ms)
                if d < bd: bd = d; best = sgv[j][1]
        return best if bd < 600000 else None
    meals = [x for x in carbs if num(x, "carbs") >= 25]
    per = dd(list)
    for m in meals:
        ms = ms_of(m)
        if not ms: continue
        g0 = glu_at(ms)
        if g0 is None: continue
        s = [glu_at(ms + k * 300000) for k in range(25)]
        s = [v for v in s if v is not None]
        if len(s) < 6: continue
        lh = lhour(ms)
        key = ('breakfast' if 5 <= lh < 10 else 'lunch' if 10 <= lh < 15
               else 'dinner' if 16 <= lh < 22 else 'other')
        per[key].append((g0, max(s), max(s) - g0))
    print("\nPOST-MEAL (>=25g): period n pre peak rise")
    for k in ['breakfast', 'lunch', 'dinner', 'other']:
        a = per[k]
        if a:
            print(f"  {k:10s} {len(a):3d}  {st.median([x[0] for x in a]):3.0f}  "
                  f"{st.median([x[1] for x in a]):3.0f}  +{st.median([x[2] for x in a]):3.0f}")


if __name__ == "__main__":
    main()
